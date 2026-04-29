import json
import threading
import paho.mqtt.client as mqtt

from database import SessionLocal
from models import MissionDB, RobotDB

BROKER_HOST = "10.164.94.237"
BROKER_PORT = 1883

# QoS utilisé pour les publications critiques — aligné avec mqtt_bridge_node.py
QOS_MISSION = 1


# ─────────────────────────────────────────────────────────────────────
# Publish mission to robot
# ─────────────────────────────────────────────────────────────────────

def publish_mission(robot_id: int, mission_id: int, start: str, end: str):
    """
    Publie une mission vers le robot via MQTT.
    Topic : robot/{robot_id}/mission
    Payload : { mission_id, robot_id, start, end }
    """
    topic = f"robot/{robot_id}/mission"

    payload = {
        "mission_id": mission_id,
        "robot_id":   robot_id,
        "start":      start,
        "end":        end,
    }

    # client_id unique par envoi pour éviter les conflits sur le broker
    client = mqtt.Client(client_id=f"server_pub_{robot_id}_{mission_id}")

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

        # loop_start() lance la boucle réseau en arrière-plan,
        # ce qui garantit que le PUBLISH est effectivement envoyé
        # avant que disconnect() ne ferme la socket.
        client.loop_start()

        result = client.publish(topic, json.dumps(payload), qos=QOS_MISSION)
        result.wait_for_publish()   # bloque jusqu'à l'acquittement QoS 1

        client.loop_stop()
        client.disconnect()

        print(f"[MQTT] Mission {mission_id} publiée → {topic}")
        return {
            "success": True,
            "topic":   topic,
            "payload": payload,
        }

    except Exception as e:
        print(f"[MQTT] Erreur publication mission {mission_id}: {e}")
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
        return {
            "success": False,
            "error":   str(e),
        }


# ─────────────────────────────────────────────────────────────────────
# MQTT subscriber callbacks
# ─────────────────────────────────────────────────────────────────────

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Connecté au broker")
        client.subscribe("robot/+/status", qos=QOS_MISSION)
        print("[MQTT] Abonné à robot/+/status")
    else:
        print(f"[MQTT] Échec connexion broker (code: {rc})")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[MQTT] Déconnexion inattendue (code: {rc}) — reconnexion automatique en cours...")
    else:
        print("[MQTT] Déconnecté proprement du broker")


def on_message(client, userdata, msg):
    print(f"[MQTT] Message reçu sur {msg.topic}: {msg.payload.decode('utf-8')}")

    try:
        data = json.loads(msg.payload.decode('utf-8'))

        mission_id = data.get("mission_id")
        robot_id   = data.get("robot_id")
        status     = data.get("status")

        if mission_id is None or robot_id is None or status is None:
            print("[MQTT] Message incomplet ignoré")
            return

        db = SessionLocal()
        try:
            mission = db.query(MissionDB).filter(MissionDB.id == mission_id).first()
            robot   = db.query(RobotDB).filter(RobotDB.id == robot_id).first()

            if not mission:
                print(f"[MQTT] Mission {mission_id} introuvable en base")
                return

            if not robot:
                print(f"[MQTT] Robot {robot_id} introuvable en base")
                return

            # ── Accusé de réception ──────────────────────────────────
            if status == "received":
                # Pas de changement d'état DB, juste un log de confirmation
                print(f"[MQTT] Mission {mission_id} accusée réception par robot {robot_id}")

            # ── Robot en route ───────────────────────────────────────
            elif status == "started":
                mission.status   = "assigned"
                robot.status     = "busy"
                print(f"[MQTT] Mission {mission_id} démarrée par robot {robot_id}")

            # ── Mission terminée ─────────────────────────────────────
            elif status == "completed":
                mission.status   = "completed"
                robot.status     = "available"
                print(f"[MQTT] Mission {mission_id} terminée par robot {robot_id}")

            # ── Échec / mission annulée ──────────────────────────────
            elif status == "failed":
                mission.status   = "pending"
                mission.robot_id = None
                robot.status     = "available"
                print(f"[MQTT] Mission {mission_id} échouée par robot {robot_id} — repassée en pending")

            # ── Chemin bloqué (nouveau statut du bridge) ─────────────
            # Le robot tente des recoveries ; on marque la mission en
            # "in_recovery" pour que le serveur puisse l'afficher.
            # Si le blocage persiste, le bridge enverra "failed".
            elif status == "path_blocked":
                mission.status = "in_recovery"
                print(f"[MQTT] Mission {mission_id} — chemin bloqué, robot {robot_id} en recovery")

            else:
                print(f"[MQTT] Statut inconnu ignoré: '{status}'")
                return

            # commit dans le try pour pouvoir rollback en cas d'erreur
            db.commit()

        except Exception as db_err:
            db.rollback()
            print(f"[MQTT] Erreur DB — rollback effectué: {db_err}")

        finally:
            db.close()

    except Exception as e:
        print(f"[MQTT] Erreur traitement message: {e}")


# ─────────────────────────────────────────────────────────────────────
# Start subscriber
# ─────────────────────────────────────────────────────────────────────

def start_mqtt_subscriber():
    # client_id distinct du publisher pour éviter tout conflit
    client = mqtt.Client(client_id="server_subscriber")
    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_disconnect = on_disconnect

    # reconnect_delay_set : paho attendra entre 1 s et 30 s avant de retenter
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    except Exception as e:
        print(f"[MQTT] Impossible de se connecter au broker: {e}")
        raise

    # loop_forever gère automatiquement les reconnexions
    client.loop_forever()


def start_mqtt_subscriber_in_background():
    thread = threading.Thread(target=start_mqtt_subscriber, daemon=True)
    thread.start()
    print("[MQTT] Subscriber démarré en arrière-plan")