import json
import paho.mqtt.client as mqtt

BROKER_HOST = "10.164.94.237"
BROKER_PORT = 1883

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