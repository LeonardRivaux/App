from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import Base, MissionDB, RobotDB

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Robot App API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Pydantic Models
# -------------------------

class MissionCreate(BaseModel):
    start: str
    end: str


class MissionResponse(BaseModel):
    id: int
    start: str
    end: str
    status: str
    robot_id: int | None = None

    class Config:
        from_attributes = True


class RobotResponse(BaseModel):
    id: int
    name: str
    status: str
    ip_address: str | None = None

    class Config:
        from_attributes = True


# -------------------------
# Database dependency
# -------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------
# Core logic: assign pending missions to free robots
# Called whenever a robot becomes available
# -------------------------

def assign_pending_missions(db: Session):
    """
    Scans for pending missions (FIFO order) and assigns them
    to any available robots. Called after a robot is freed.
    """
    while True:
        robot = db.query(RobotDB).filter(RobotDB.status == "available").first()
        if not robot:
            break  # No free robot, stop

        mission = (
            db.query(MissionDB)
            .filter(MissionDB.status == "pending")
            .order_by(MissionDB.id.asc())  # FIFO
            .first()
        )
        if not mission:
            break  # No pending mission, stop

        # Assign robot to mission
        robot.status = "busy"
        mission.status = "assigned"
        mission.robot_id = robot.id
        db.commit()


# -------------------------
# Init robots
# -------------------------

def init_robots(db: Session):
    if db.query(RobotDB).count() == 0:
        robots = [
            RobotDB(name="Robot-1", status="available", ip_address="192.168.1.50"),
            RobotDB(name="Robot-2", status="available", ip_address="192.168.1.51"),
        ]
        db.add_all(robots)
        db.commit()


with SessionLocal() as db:
    init_robots(db)


# -------------------------
# Routes
# -------------------------

@app.get("/")
def root():
    return {"message": "Serveur OK"}


@app.get("/robots", response_model=list[RobotResponse])
def get_robots(db: Session = Depends(get_db)):
    return db.query(RobotDB).all()


@app.get("/missions", response_model=list[MissionResponse])
def get_missions(db: Session = Depends(get_db)):
    return db.query(MissionDB).all()


@app.get("/missions/{mission_id}", response_model=MissionResponse)
def get_mission(mission_id: int, db: Session = Depends(get_db)):
    mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")
    return mission


@app.post("/missions", response_model=MissionResponse, status_code=201)
def create_mission(mission: MissionCreate, db: Session = Depends(get_db)):
    # Try to assign an available robot immediately
    robot = db.query(RobotDB).filter(RobotDB.status == "available").first()

    if robot:
        robot.status = "busy"
        mission_status = "assigned"
        robot_id = robot.id
    else:
        mission_status = "pending"
        robot_id = None

    new_mission = MissionDB(
        start=mission.start,
        end=mission.end,
        status=mission_status,
        robot_id=robot_id,
    )
    db.add(new_mission)
    db.commit()
    db.refresh(new_mission)
    return new_mission


@app.put("/missions/{mission_id}", response_model=MissionResponse)
def update_mission(mission_id: int, mission: MissionCreate, db: Session = Depends(get_db)):
    db_mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
    if not db_mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")

    db_mission.start = mission.start
    db_mission.end = mission.end
    db.commit()
    db.refresh(db_mission)
    return db_mission


@app.post("/missions/{mission_id}/complete", response_model=MissionResponse)
def complete_mission(mission_id: int, db: Session = Depends(get_db)):
    """
    Mark a mission as completed and free its robot.
    Automatically reassigns any pending missions to the freed robot.
    """
    db_mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
    if not db_mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")

    if db_mission.status == "completed":
        raise HTTPException(status_code=400, detail="Mission déjà complétée")

    if db_mission.status not in ("assigned",):
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de compléter une mission au statut '{db_mission.status}'"
        )

    # Free the robot
    if db_mission.robot_id is not None:
        robot = db.query(RobotDB).filter(RobotDB.id == db_mission.robot_id).first()
        if robot:
            robot.status = "available"

    db_mission.status = "completed"
    db.commit()

    # Reassign pending missions now that a robot is free
    assign_pending_missions(db)

    db.refresh(db_mission)
    return db_mission


@app.post("/missions/{mission_id}/cancel", response_model=MissionResponse)
def cancel_mission(mission_id: int, db: Session = Depends(get_db)):
    """
    Cancel a mission (pending or assigned). Frees the robot if one was assigned.
    Automatically reassigns any remaining pending missions.
    """
    db_mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
    if not db_mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")

    if db_mission.status == "completed":
        raise HTTPException(status_code=400, detail="Impossible d'annuler une mission complétée")

    if db_mission.robot_id is not None:
        robot = db.query(RobotDB).filter(RobotDB.id == db_mission.robot_id).first()
        if robot:
            robot.status = "available"

    db_mission.status = "cancelled"
    db_mission.robot_id = None
    db.commit()

    assign_pending_missions(db)

    db.refresh(db_mission)
    return db_mission


@app.delete("/missions/{mission_id}")
def delete_mission(mission_id: int, db: Session = Depends(get_db)):
    db_mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
    if not db_mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")

    # Free the robot if the mission was active
    if db_mission.status == "assigned" and db_mission.robot_id is not None:
        robot = db.query(RobotDB).filter(RobotDB.id == db_mission.robot_id).first()
        if robot:
            robot.status = "available"

    db.delete(db_mission)
    db.commit()

    # Reassign pending missions
    assign_pending_missions(db)

    return {"message": "Mission supprimée avec succès"}