import paho.mqtt.client as mqtt
import json
import time

BROKER = "192.168.137.1"
PORT = 1883

client = mqtt.Client()
client.connect(BROKER, PORT, 60)

mission = {
    "mission_id": 1,
    "start": "Salle A",
    "end": "Salle B"
}

# petit délai pour être sûr que la connexion est OK
time.sleep(1)

client.publish("robot/mission", json.dumps(mission))

print("Mission envoyée")

client.disconnect()