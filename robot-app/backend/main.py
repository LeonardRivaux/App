from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import MissionDB
from models import Base

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

# Pydantic Models
class MissionCreate(BaseModel):
    start: str
    end: str

class MissionResponse(BaseModel):
    id: int
    start: str
    end: str
    status: str

    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "Serveur OK"}

@app.get("/robots")
def get_robots():
    return [
        {"id": 1, "name": "Robot-1", "status": "available"},
        {"id": 2, "name": "Robot-2", "status": "busy"}
    ]

@app.get("/missions")
def get_missions(db: Session = Depends(get_db)):
    missions = db.query(MissionDB).all()

    return [
        {
            "id": mission.id,
            "start": mission.start,
            "end": mission.end,
            "status": mission.status
        }
        for mission in missions
    ]

@app.post("/missions", response_model=MissionResponse)
def create_mission(mission: MissionCreate, db: Session = Depends(get_db)):
    new_mission = MissionDB(
        start=mission.start,
        end=mission.end,
        status="pending"
    )
    db.add(new_mission)
    db.commit()
    db.refresh(new_mission)
    return new_mission

@app.get("/missions/{mission_id}", response_model=MissionResponse)
def get_mission(mission_id: int, db: Session = Depends(get_db)):
    mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission non trouvée")
    return mission

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
    
    db.delete(db_mission)
    db.commit()
    return {"message": "Mission supprimée avec succès"}