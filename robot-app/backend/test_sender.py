import paho.mqtt.client as mqtt
import json
import time

BROKER = "10.164.94.237"
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