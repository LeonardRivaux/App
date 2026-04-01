# from fastapi import FastAPI

# app = FastAPI()


# @app.get("/")
# def root():
#     return {"message": "Serveur OK"}


# @app.get("/robots")
# def get_robots():
#     return [
#         {"id": 1, "name": "Robot-1", "status": "available"},
#         {"id": 2, "name": "Robot-2", "status": "busy"}
#     ]


# @app.post("/missions")
# def create_mission():
#     return {
#         "message": "Mission créée",
#         "mission": {
#             "id": 1,
#             "start": "Salle A",
#             "end": "Salle B",
#             "status": "pending"
#         }
#     }

# from fastapi import FastAPI
# from pydantic import BaseModel

# app = FastAPI()

# # 👉 modèle de données (IMPORTANT)
# class Mission(BaseModel):
#     start: str
#     end: str


# @app.get("/")
# def root():
#     return {"message": "Serveur OK"}


# @app.get("/robots")
# def get_robots():
#     return [
#         {"id": 1, "name": "Robot-1", "status": "available"},
#         {"id": 2, "name": "Robot-2", "status": "busy"}
#     ]


# # 👉 nouvelle vraie route POST
# @app.post("/missions")
# def create_mission(mission: Mission):
#     return {
#         "message": "Mission créée",
#         "mission": {
#             "id": 1,
#             "start": mission.start,
#             "end": mission.end,
#             "status": "pending"
#         }
#     }

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Mission(BaseModel):
    start: str
    end: str

missions = []
mission_id_counter = 1

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
def get_missions():
    return missions

@app.post("/missions")
def create_mission(mission: Mission):
    global mission_id_counter

    new_mission = {
        "id": mission_id_counter,
        "start": mission.start,
        "end": mission.end,
        "status": "pending"
    }

    missions.append(new_mission)
    mission_id_counter += 1

    return {
        "message": "Mission créée",
        "mission": new_mission
    }