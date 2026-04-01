from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import Base, MissionDB, RobotDB

# Création des tables au démarrage si elles n'existent pas
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


@app.get("/robots")
def get_robots(db: Session = Depends(get_db)):
    robots = db.query(RobotDB).all()

    return [
        {
            "id": robot.id,
            "name": robot.name,
            "status": robot.status,
            "ip_address": robot.ip_address
        }
        for robot in robots
    ]


@app.get("/missions")
def get_missions(db: Session = Depends(get_db)):
    missions = db.query(MissionDB).all()

    return [
        {
            "id": mission.id,
            "start": mission.start,
            "end": mission.end,
            "status": mission.status,
            "robot_id": mission.robot_id
        }
        for mission in missions
    ]


@app.get("/missions/{mission_id}", response_model=MissionResponse)
def get_mission(mission_id: int, db: Session = Depends(get_db)):
    mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()

    if not mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")

    return mission


@app.post("/missions")
def create_mission(mission: MissionCreate, db: Session = Depends(get_db)):
    # Chercher un robot disponible
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
        robot_id=robot_id
    )

    db.add(new_mission)
    db.commit()
    db.refresh(new_mission)

    return {
        "message": "Mission créée",
        "mission": {
            "id": new_mission.id,
            "start": new_mission.start,
            "end": new_mission.end,
            "status": new_mission.status,
            "robot_id": new_mission.robot_id
        }
    }


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


@app.delete("/missions/{mission_id}")
def delete_mission(mission_id: int, db: Session = Depends(get_db)):
    db_mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()

    if not db_mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")

    # Si la mission avait un robot assigné, le libérer
    if db_mission.robot_id is not None:
        robot = db.query(RobotDB).filter(RobotDB.id == db_mission.robot_id).first()
        if robot:
            robot.status = "available"

    db.delete(db_mission)
    db.commit()

    return {"message": "Mission supprimée avec succès"}

# # Test communication with backend server

# @app.put("/missions/{mission_id}", response_model=MissionResponse)
# def update_mission(mission_id: int, mission: MissionCreate, db: Session = Depends(get_db)):
#     db_mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()

#     if not db_mission:
#         raise HTTPException(status_code=404, detail="Mission non trouvée")

#     db_mission.start = mission.start
#     db_mission.end = mission.end

#     db.commit()
#     db.refresh(db_mission)

#     return db_mission