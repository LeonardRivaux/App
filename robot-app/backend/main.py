import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import Base, MissionDB, RobotDB
from mqtt_client import publish_mission, start_mqtt_subscriber_in_background

Base.metadata.create_all(bind=engine)

# Intervalle entre chaque tentative de retry (secondes)
MQTT_RETRY_INTERVAL = 30


# ─────────────────────────────────────────────────────────────────────
# Tâche de retry : relance les missions pending sans robot assigné
# ─────────────────────────────────────────────────────────────────────

async def retry_pending_missions_task():
    """
    Tâche asyncio qui tourne en arrière-plan toute la durée de vie du serveur.
    Toutes les MQTT_RETRY_INTERVAL secondes, elle cherche les missions 'pending'
    sans robot assigné et tente de les envoyer si un robot est disponible.
    Utile lorsque le broker MQTT était inaccessible lors de la création initiale.
    """
    while True:
        await asyncio.sleep(MQTT_RETRY_INTERVAL)
        db = SessionLocal()
        try:
            pending = (
                db.query(MissionDB)
                .filter(MissionDB.status == "pending", MissionDB.robot_id == None)
                .order_by(MissionDB.id.asc())
                .all()
            )
            if pending:
                print(f"[RETRY] {len(pending)} mission(s) pending détectée(s) — tentative d'assignation")
                assign_pending_missions(db)
            else:
                print("[RETRY] Aucune mission pending en attente")
        except Exception as e:
            print(f"[RETRY] Erreur pendant le retry : {e}")
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarre le subscriber MQTT en tâche de fond dès le lancement
    start_mqtt_subscriber_in_background()

    # Initialise les robots si la table est vide
    db = SessionLocal()
    try:
        init_robots(db)
    finally:
        db.close()

    # Lance la tâche de retry en arrière-plan
    retry_task = asyncio.create_task(retry_pending_missions_task())

    yield

    # Arrêt propre de la tâche au shutdown
    retry_task.cancel()
    try:
        await retry_task
    except asyncio.CancelledError:
        pass


# ─────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Robot App API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────
# Database dependency
# ─────────────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# MQTT helpers
# ─────────────────────────────────────────────────────────────────────

def assign_mission_to_robot(db: Session, mission: MissionDB, robot: RobotDB):
    """
    Assigne une mission à un robot :
    1. Modifie les objets en mémoire (pas encore de commit)
    2. Envoie via MQTT (wait_for_publish QoS 1)
    3. Commit DB uniquement si l'envoi MQTT a réussi
       → le robot n'est jamais marqué 'busy' en DB si le message n'est pas parti
    """
    robot.status     = "busy"
    mission.status   = "assigned"
    mission.robot_id = robot.id

    result = publish_mission(
        robot_id=robot.id,
        mission_id=mission.id,
        start=mission.start,
        end=mission.end,
    )

    if not result["success"]:
        # Annule les changements en mémoire sans toucher la DB
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Échec envoi MQTT : {result['error']}",
        )

    # MQTT OK → on persiste maintenant
    db.commit()
    db.refresh(mission)
    db.refresh(robot)


def assign_pending_missions(db: Session):
    """
    Boucle d'attribution : assigne les missions en attente
    aux robots disponibles, dans l'ordre d'arrivée (id asc).
    S'arrête dès qu'il n'y a plus de robot ou de mission disponible,
    ou en cas d'échec MQTT.
    """
    while True:
        robot = db.query(RobotDB).filter(RobotDB.status == "available").first()
        if not robot:
            break

        mission = (
            db.query(MissionDB)
            .filter(MissionDB.status == "pending", MissionDB.robot_id == None)
            .order_by(MissionDB.id.asc())
            .first()
        )
        if not mission:
            break

        try:
            assign_mission_to_robot(db, mission, robot)
        except HTTPException:
            # Échec MQTT — inutile de retenter les autres missions maintenant,
            # la tâche de retry s'en chargera dans MQTT_RETRY_INTERVAL secondes
            break


# ─────────────────────────────────────────────────────────────────────
# Init robots
# ─────────────────────────────────────────────────────────────────────

def init_robots(db: Session):
    if db.query(RobotDB).count() == 0:
        robots = [
            RobotDB(name="Robot-1", status="available", ip_address="192.168.1.50"),
            RobotDB(name="Robot-2", status="available", ip_address="192.168.1.51"),
        ]
        db.add_all(robots)
        db.commit()
        print("[DB] Robots initialisés")


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "Serveur OK"}


# ── Robots ────────────────────────────────────────────────────────────

@app.get("/robots", response_model=list[RobotResponse])
def get_robots(db: Session = Depends(get_db)):
    return db.query(RobotDB).all()


@app.get("/robots/{robot_id}", response_model=RobotResponse)
def get_robot(robot_id: int, db: Session = Depends(get_db)):
    robot = db.query(RobotDB).filter(RobotDB.id == robot_id).first()
    if not robot:
        raise HTTPException(status_code=404, detail="Robot non trouvé")
    return robot


# ── Missions ──────────────────────────────────────────────────────────

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
    new_mission = MissionDB(
        start=mission.start,
        end=mission.end,
        status="pending",
        robot_id=None,
    )
    db.add(new_mission)
    db.commit()
    db.refresh(new_mission)

    robot = db.query(RobotDB).filter(RobotDB.status == "available").first()
    if robot:
        try:
            assign_mission_to_robot(db, new_mission, robot)
        except HTTPException:
            # MQTT indisponible — la mission reste pending,
            # la tâche de retry tentera à nouveau dans MQTT_RETRY_INTERVAL secondes
            pass
        db.refresh(new_mission)

    return new_mission


@app.put("/missions/{mission_id}", response_model=MissionResponse)
def update_mission(mission_id: int, mission: MissionCreate, db: Session = Depends(get_db)):
    db_mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
    if not db_mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")

    if db_mission.status not in ("pending",):
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de modifier une mission au statut '{db_mission.status}'. "
                   f"Seules les missions 'pending' peuvent être modifiées.",
        )

    db_mission.start = mission.start
    db_mission.end   = mission.end
    db.commit()
    db.refresh(db_mission)
    return db_mission


@app.post("/missions/{mission_id}/complete", response_model=MissionResponse)
def complete_mission(mission_id: int, db: Session = Depends(get_db)):
    db_mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
    if not db_mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")

    if db_mission.status == "completed":
        raise HTTPException(status_code=400, detail="Mission déjà complétée")

    if db_mission.status not in ("assigned", "in_recovery"):
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de compléter une mission au statut '{db_mission.status}'",
        )

    if db_mission.robot_id is not None:
        robot = db.query(RobotDB).filter(RobotDB.id == db_mission.robot_id).first()
        if robot:
            robot.status = "available"

    db_mission.status = "completed"
    db.commit()

    assign_pending_missions(db)

    db.refresh(db_mission)
    return db_mission


@app.post("/missions/{mission_id}/cancel", response_model=MissionResponse)
def cancel_mission(mission_id: int, db: Session = Depends(get_db)):
    db_mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
    if not db_mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")

    if db_mission.status == "completed":
        raise HTTPException(status_code=400, detail="Impossible d'annuler une mission complétée")

    if db_mission.status == "cancelled":
        raise HTTPException(status_code=400, detail="Mission déjà annulée")

    if db_mission.robot_id is not None:
        robot = db.query(RobotDB).filter(RobotDB.id == db_mission.robot_id).first()
        if robot:
            robot.status = "available"

    db_mission.status   = "cancelled"
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

    if db_mission.status == "assigned" and db_mission.robot_id is not None:
        robot = db.query(RobotDB).filter(RobotDB.id == db_mission.robot_id).first()
        if robot:
            robot.status = "available"

    db.delete(db_mission)
    db.commit()

    assign_pending_missions(db)

    return {"message": "Mission supprimée avec succès"}