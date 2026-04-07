import json
import threading
import paho.mqtt.client as mqtt

from database import SessionLocal
from models import MissionDB, RobotDB

BROKER_HOST = "10.164.94.237"
BROKER_PORT = 1883


# -------------------------
# Publish mission to robot
# -------------------------

def publish_mission(robot_id: int, mission_id: int, start: str, end: str):
    topic = f"robot/{robot_id}/mission"

    payload = {
        "mission_id": mission_id,
        "robot_id": robot_id,
        "start": start,
        "end": end
    }

    client = mqtt.Client()

    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.publish(topic, json.dumps(payload))
        client.disconnect()

        return {
            "success": True,
            "topic": topic,
            "payload": payload
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# -------------------------
# MQTT subscriber callbacks
# -------------------------

def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connecté au broker avec code {rc}")
    client.subscribe("robot/+/status")
    print("[MQTT] Abonné à robot/+/status")


def on_message(client, userdata, msg):
    print(f"[MQTT] Message reçu sur {msg.topic}: {msg.payload.decode()}")

    try:
        data = json.loads(msg.payload.decode())

        mission_id = data.get("mission_id")
        robot_id = data.get("robot_id")
        status = data.get("status")

        if mission_id is None or robot_id is None or status is None:
            print("[MQTT] Message incomplet ignoré")
            return

        db = SessionLocal()
        try:
            mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
            robot = db.query(RobotDB).filter(RobotDB.id == robot_id).first()

            if not mission:
                print(f"[MQTT] Mission {mission_id} introuvable")
                return

            if not robot:
                print(f"[MQTT] Robot {robot_id} introuvable")
                return

            # Robot a bien reçu la mission
            if status == "received":
                print(f"[MQTT] Mission {mission_id} reçue par robot {robot_id}")

            # Robot a commencé la mission
            elif status == "started":
                mission.status = "assigned"
                robot.status = "busy"
                print(f"[MQTT] Mission {mission_id} démarrée par robot {robot_id}")

            # Robot a terminé la mission
            elif status == "completed":
                mission.status = "completed"
                robot.status = "available"
                print(f"[MQTT] Mission {mission_id} terminée par robot {robot_id}")

            # Robot a échoué
            elif status == "failed":
                mission.status = "pending"
                mission.robot_id = None
                robot.status = "available"
                print(f"[MQTT] Mission {mission_id} échouée par robot {robot_id}")

            else:
                print(f"[MQTT] Statut inconnu: {status}")
                return

            db.commit()

        finally:
            db.close()

    except Exception as e:
        print(f"[MQTT] Erreur traitement message: {e}")


# -------------------------
# Start subscriber
# -------------------------

def start_mqtt_subscriber():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_forever()


def start_mqtt_subscriber_in_background():
    thread = threading.Thread(target=start_mqtt_subscriber, daemon=True)
    thread.start()