
# ================================================================
# PROJECT: IoT Equipment Condition Monitoring System
# FILE: backend/mqtt/subscriber.py
# ================================================================
#
# PURPOSE:
#   Receive real-time ESP32 sensor readings through MQTT
#   and automatically save selected readings to Azure.
#
# SYSTEM FLOW:
#   ESP32
#      |
#      v
#   Mosquitto MQTT Broker (Mac)
#      |
#      v
#   Python MQTT Subscriber
#      |
#      v
#   Azure Table Storage
#
# UPLOAD STRATEGY:
#   - Receive MQTT telemetry approximately every 2 seconds.
#   - Upload the first reading immediately.
#   - Upload subsequent readings every 30 seconds.
#   - Upload immediately when the condition changes.
#
# WHY NOT UPLOAD EVERY MESSAGE?
#   To reduce Azure transactions and unnecessary storage.
#
# IMPORTANT:
#   This program must be running for Azure uploads to occur.
# ================================================================


# ------------------------------------------------
# STEP 1: Import Python libraries
# ------------------------------------------------

import json
import os
import sys
import time
import getpass

from datetime import datetime
from pathlib import Path

# Paho MQTT lets Python connect to our Mosquitto broker.
import paho.mqtt.client as mqtt


# ------------------------------------------------
# STEP 2: Import our Azure storage function
# ------------------------------------------------

# Locate the main project directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Add the Azure module folder to Python's import path.
# This lets us import storage.py from another directory.
sys.path.insert(
    0,
    str(PROJECT_ROOT / "backend" / "azure")
)

# Import the function that uploads readings to Azure.
from storage import save_telemetry


# ------------------------------------------------
# STEP 3: Configure MQTT connection settings
# ------------------------------------------------

# IP address of the Mac running Mosquitto.
#
# IMPORTANT:
#   10.0.0.149 is your previously configured home IP.
#   If your Mac's IP changes, update MQTT_HOST.
BROKER_HOST = os.getenv("MQTT_HOST", "10.0.0.149")

# Standard unencrypted MQTT port.
# This connection is intended for your trusted local network.
BROKER_PORT = 1883

# MQTT username configured in Mosquitto.
MQTT_USERNAME = "esp32_monitor"

# Topic containing ESP32 sensor readings.
TELEMETRY_TOPIC = "equipment/ESP32-001/telemetry"

# Topic containing ONLINE/OFFLINE device messages.
STATUS_TOPIC = "equipment/ESP32-001/status"


# ------------------------------------------------
# STEP 4: Configure Azure upload frequency
# ------------------------------------------------

# Save normal telemetry approximately every 30 seconds.
UPLOAD_INTERVAL = 30

# Time when the most recent successful upload occurred.
#
# 0 means no reading has been uploaded yet.
last_upload_time = 0.0

# Tracks the equipment condition from the last saved reading.
#
# Example:
#   NORMAL -> WARNING -> CRITICAL
#
# A condition change triggers an immediate Azure upload.
last_condition = None


# ------------------------------------------------
# STEP 5: Handle MQTT broker connections
# ------------------------------------------------

def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties
):
    """
    Runs when the MQTT client connects to the broker.

    If the connection succeeds, subscribe to:
      1. ESP32 telemetry
      2. ESP32 online/offline status

    Subscriptions are also restored after reconnection.
    """

    # MQTT reason code 0 means successful connection.
    if reason_code == 0:

        print("[MQTT] Connected to broker")

        # Subscribe to both topics using QoS 0.
        client.subscribe([
            (TELEMETRY_TOPIC, 0),
            (STATUS_TOPIC, 0),
        ])

        print(
            "[MQTT] Subscribed to ESP32 telemetry and status"
        )

    else:
        # Display connection errors for troubleshooting.
        print(
            f"[MQTT ERROR] Connection failed: {reason_code}"
        )


# ------------------------------------------------
# STEP 6: Handle incoming MQTT messages
# ------------------------------------------------

def on_message(client, userdata, message):
    """
    Runs whenever a subscribed MQTT message arrives.

    Responsibilities:
      1. Identify the MQTT topic.
      2. Decode JSON telemetry.
      3. Check required fields.
      4. Display readings.
      5. Decide whether Azure upload is required.
      6. Save selected readings to Azure.
    """

    # We modify these variables across multiple messages.
    global last_upload_time, last_condition

    # Create a readable local timestamp for logging.
    timestamp = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    # Convert MQTT message bytes into a Python string.
    payload = message.payload.decode(
        "utf-8",
        errors="replace"
    )

    # ------------------------------------------------
    # STEP 6A: Handle ONLINE/OFFLINE status messages
    # ------------------------------------------------

    if message.topic == STATUS_TOPIC:

        # Device status messages are plain text.
        print(
            f"[{timestamp}] Device status: {payload}"
        )

        # Status messages are not telemetry records.
        return

    # ------------------------------------------------
    # STEP 6B: Decode the ESP32 JSON message
    # ------------------------------------------------

    try:
        # Convert the JSON string into a Python dictionary.
        data = json.loads(payload)

        # Ensure the payload contains a JSON object.
        if not isinstance(data, dict):
            raise ValueError(
                "Telemetry must be a JSON object"
            )

        # These fields must exist before saving data.
        required_fields = (
            "device_id",
            "temperature",
            "humidity",
            "condition",
        )

        # Find any missing required fields.
        missing_fields = [
            field
            for field in required_fields
            if field not in data
        ]

        # Reject incomplete telemetry messages.
        if missing_fields:
            raise ValueError(
                f"Missing fields: {missing_fields}"
            )

        # ------------------------------------------------
        # STEP 6C: Extract and display sensor readings
        # ------------------------------------------------

        # Current condition reported by the ESP32.
        condition = str(data["condition"])

        # Monotonic time is reliable for measuring intervals.
        current_time = time.monotonic()

        # Show a compact summary in the VS Code terminal.
        print(
            f"[MQTT] Device: {data['device_id']} | "
            f"Temp: {data['temperature']} C | "
            f"Humidity: {data['humidity']}% | "
            f"Vibration: {data.get('vibration')} | "
            f"Condition: {condition}"
        )

        # ------------------------------------------------
        # STEP 6D: Decide whether to upload to Azure
        # ------------------------------------------------

        # Upload immediately if this is the first reading.
        first_reading = last_upload_time == 0

        # Upload when at least 30 seconds have elapsed.
        interval_elapsed = (
            current_time - last_upload_time
            >= UPLOAD_INTERVAL
        )

        # Upload immediately if the condition changed.
        condition_changed = (
            condition != last_condition
        )

        # Only one of these conditions needs to be true.
        should_upload = (
            first_reading
            or interval_elapsed
            or condition_changed
        )

        # ------------------------------------------------
        # STEP 6E: Upload selected telemetry to Azure
        # ------------------------------------------------

        if should_upload:

            try:
                # Call our Azure storage module.
                #
                # This creates a new row in EquipmentTelemetry.
                row_key = save_telemetry(data)

                # Update upload tracking ONLY after success.
                #
                # This allows a later MQTT message to retry
                # if the Azure upload fails.
                last_upload_time = current_time
                last_condition = condition

                # Confirm successful cloud storage.
                print(
                    "[AZURE] Telemetry saved successfully"
                )

                print(
                    f"[AZURE] RowKey: {row_key}"
                )

            except Exception as error:

                # An Azure failure should not stop the
                # entire MQTT subscriber.
                print(
                    "[AZURE ERROR] Could not save telemetry"
                )

                print(
                    f"[AZURE ERROR] "
                    f"{type(error).__name__}: {error}"
                )

    # ------------------------------------------------
    # STEP 6F: Handle invalid MQTT telemetry
    # ------------------------------------------------

    except (json.JSONDecodeError, ValueError) as error:

        # Display malformed or incomplete JSON errors.
        print(
            f"[MQTT ERROR] Invalid telemetry: {error}"
        )


# ------------------------------------------------
# STEP 7: Start the MQTT subscriber
# ------------------------------------------------

def main():
    """
    Main entry point of our Python backend.

    Responsibilities:
      1. Read the MQTT password securely.
      2. Create the MQTT client.
      3. Register message handlers.
      4. Connect to Mosquitto.
      5. Continuously receive ESP32 readings.
    """

    # Read MQTT password from an environment variable,
    # or prompt the user securely in the terminal.
    #
    # The password is NOT stored in this Python file.
    password = (
        os.getenv("MQTT_PASSWORD")
        or getpass.getpass("Enter MQTT password: ")
    )

    # Create an MQTT client using Paho callback API v2.
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="equipment-monitor-backend"
    )

    # Configure username/password authentication.
    client.username_pw_set(
        MQTT_USERNAME,
        password
    )

    # Register our connection handler.
    client.on_connect = on_connect

    # Register our message handler.
    client.on_message = on_message

    print(
        f"[MQTT] Connecting to "
        f"{BROKER_HOST}:{BROKER_PORT}"
    )

    try:
        # Connect to the local Mosquitto broker.
        client.connect(
            BROKER_HOST,
            BROKER_PORT,
            keepalive=60
        )

        # Keep receiving messages until the user stops
        # the program or an unrecoverable error occurs.
        client.loop_forever()

    except KeyboardInterrupt:

        # Ctrl+C lets us stop the program normally.
        print("\n[MQTT] Stopping subscriber")

    except OSError as error:

        # Display network connection failures.
        print(
            f"[MQTT ERROR] Network failure: {error}"
        )

    finally:

        # Disconnect cleanly when the program exits.
        client.disconnect()


# ------------------------------------------------
# STEP 8: Run main() when this file is executed
# ------------------------------------------------

if __name__ == "__main__":
    main()
