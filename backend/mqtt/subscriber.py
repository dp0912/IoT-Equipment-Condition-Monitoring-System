import json
import os
import getpass
from datetime import datetime

import paho.mqtt.client as mqtt

BROKER_HOST = os.getenv("MQTT_HOST", "10.0.0.149")
BROKER_PORT = 1883
MQTT_USERNAME = "esp32_monitor"

TELEMETRY_TOPIC = "equipment/ESP32-001/telemetry"
STATUS_TOPIC = "equipment/ESP32-001/status"


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("[MQTT] Connected to broker")
        client.subscribe([
            (TELEMETRY_TOPIC, 0),
            (STATUS_TOPIC, 0),
        ])
        print("[MQTT] Subscribed to ESP32 telemetry and status")
    else:
        print(f"[MQTT] Connection failed: {reason_code}")


def on_message(client, userdata, message):
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = message.payload.decode("utf-8", errors="replace")

    if message.topic == STATUS_TOPIC:
        print(f"[{timestamp}] Device status: {payload}")
        return

    try:
        data = json.loads(payload)

        if not isinstance(data, dict):
            raise ValueError("Telemetry must be a JSON object")

        required = ("device_id", "temperature", "humidity", "condition")

        missing = [field for field in required if field not in data]
        if missing:
            raise ValueError(f"Missing fields: {missing}")

        print(f"\n[{timestamp}] Telemetry received")
        print(f"Device:       {data['device_id']}")
        print(f"Temperature:  {data['temperature']} °C")
        print(f"Humidity:     {data['humidity']} %")
        print(f"Vibration:    {data.get('vibration')} RMS")
        print(f"Condition:    {data['condition']}")
        print(f"Motor running: {data.get('motor_running')}")
        print(f"STOP latched:  {data.get('stop_latched')}")

    except (json.JSONDecodeError, ValueError) as error:
        print(f"[ERROR] Invalid telemetry: {error}")


def main():
    password = os.getenv("MQTT_PASSWORD") or getpass.getpass(
        "Enter MQTT password: "
    )

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="equipment-monitor-backend",
    )

    client.username_pw_set(MQTT_USERNAME, password)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[MQTT] Connecting to {BROKER_HOST}:{BROKER_PORT}")

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[MQTT] Stopping subscriber")
    except OSError as error:
        print(f"[ERROR] Network connection failed: {error}")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()