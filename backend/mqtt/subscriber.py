
"""
PROJECT: IoT Equipment Condition Monitoring System
FILE: backend/mqtt/subscriber.py

PURPOSE:
    Receive ESP32 telemetry through MQTT and save:
    1. A statistical SUMMARY approximately every 30 seconds.
    2. An EVENT immediately when equipment condition changes.
    3. Optional Azure Log Analytics telemetry.

    Also publish live dashboard messages:
    4. Equipment condition-change alerts.
    5. Online/offline connectivity status.
    6. Isolation Forest NORMAL/ANOMALY predictions every 30 seconds.

DATA FLOW:
    ESP32 -> Mosquitto MQTT -> Python Subscriber
                                  |
                                  +-> Azure Table Storage
                                  |   - SUMMARY records
                                  |   - EVENT records
                                  |
                                  +-> Azure Log Analytics (optional)
                                  |
                                  +-> Live MQTT Alerts
                                  +-> Live MQTT Connectivity

IMPORTANT:
    FastAPI is NOT required.

    Azure Log Analytics is disabled unless
    AZURE_LOG_ANALYTICS_ENABLED=true in .env.

    The MQTT subscriber receives approximately one
    sensor message every 2 seconds.
"""

# ============================================================
# STEP 1: Import Python libraries.
# ============================================================

import getpass
import json
import math
import os
import sys
import threading
import time

from collections import deque
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

from dotenv import load_dotenv


# ============================================================
# STEP 2: Load the project's private configuration.
# ============================================================

# Locate the main project directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load environment variables from .env.
load_dotenv(PROJECT_ROOT / ".env")

# Allow imports from the Azure and MQTT directories.
sys.path.insert(
    0,
    str(PROJECT_ROOT / "backend" / "azure")
)

sys.path.insert(
    0,
    str(PROJECT_ROOT / "backend" / "mqtt")
)

# Import the Azure functions created previously.
from storage import save_event, save_summary

# Import our tested 30-second statistics calculator.
from telemetry_aggregator import TelemetryAggregator

# Load the local inference module, without changing ESP32 logic.
sys.path.insert(0, str(PROJECT_ROOT / "ml" / "inference"))
from predict_anomaly import AnomalyDetector

# Load once at startup, not for every incoming MQTT reading.
anomaly_detector = AnomalyDetector()

# Preserve the optional Log Analytics integration.
from log_analytics import (
    LOG_ANALYTICS_ENABLED,
    prepare_telemetry,
    upload_telemetry,
)


# ============================================================
# STEP 3: Configure the existing MQTT connection.
# ============================================================

# Mac IP address running the Mosquitto broker.
# MQTT_HOST in .env can override this address.
BROKER_HOST = os.getenv(
    "MQTT_HOST",
    "10.0.0.149"
)

# Standard MQTT TCP port.
BROKER_PORT = 1883

# Existing MQTT account.
MQTT_USERNAME = "esp32_monitor"

# Topics published by the physical ESP32.
TELEMETRY_TOPIC = "equipment/ESP32-001/telemetry"

STATUS_TOPIC = "equipment/ESP32-001/status"

# Dashboard-only topics; do not overwrite the ESP32 status topic.
LIVE_ALERT_TOPIC = "equipment/ESP32-001/alerts"
LIVE_CONNECTIVITY_TOPIC = "equipment/ESP32-001/connectivity"

# New dashboard topic: independent of all existing ESP32/status topics.
LIVE_ML_TOPIC = "equipment/ESP32-001/ml"

# If valid telemetry stops for 10 seconds, mark device offline.
OFFLINE_TIMEOUT_SECONDS = 10

# Publish connectivity snapshots approximately every 2 seconds.
CONNECTIVITY_CHECK_SECONDS = 2

# Track when the last valid telemetry message was received.
last_telemetry_monotonic = None
last_telemetry_wall_time = None

# Protect shared timestamps accessed by two threads.
connectivity_lock = threading.Lock()


# ============================================================
# STEP 4: Configure storage intervals and tracking.
# ============================================================

# Create a summary for each 30-second window.
SUMMARY_INTERVAL_SECONDS = 30

# Keep the previous optional Log Analytics interval.
LOG_INTERVAL_SECONDS = 30

# Each device receives its own aggregation window.
aggregators = {}

# Remember each device's last known equipment condition.
last_seen_condition = {}

# Track Log Analytics uploads separately from Table Storage.
last_logs_upload_time = {}
last_logs_condition = {}


# ============================================================
# STEP 5: Queue Azure writes for retry.
# ============================================================

# Keep unsuccessful Azure writes temporarily in memory.
#
# IMPORTANT:
# This queue is not persistent. Pending records can be lost
# when Python exits or the Mac restarts.
#
# We can add disk-based persistence in a later phase.

MAX_PENDING_WRITES = 1000

pending_writes = deque()


def queue_write(record_type, data, previous_condition=None):
    """
    Add a SUMMARY or EVENT to the Azure upload queue.

    Parameters:
        record_type:
            Either "SUMMARY" or "EVENT".

        data:
            Dictionary containing the record.

        previous_condition:
            Used for condition-change EVENT records.
    """

    # Prevent unlimited memory consumption during outages.
    if len(pending_writes) >= MAX_PENDING_WRITES:

        print(
            "[AZURE TABLE WARNING] "
            "Pending queue full; oldest unsaved record dropped"
        )

        pending_writes.popleft()

    # Store the record for the next upload attempt.
    pending_writes.append(
        (record_type, data, previous_condition)
    )


def flush_pending_writes(max_attempts=3):
    """
    Attempt to upload queued records to Azure.

    Successfully uploaded records are removed.

    Failed records remain queued for another attempt.

    Only a few writes are attempted per call to avoid
    excessive Azure requests.

    Note:
        Azure SDK calls are synchronous and may briefly
        delay processing incoming MQTT messages.
    """

    attempts = 0

    while pending_writes and attempts < max_attempts:

        # Examine the oldest queued record.
        record_type, data, previous_condition = (
            pending_writes[0]
        )

        try:

            # Upload a completed statistical summary.
            if record_type == "SUMMARY":

                row_key = save_summary(data)

            # Upload a condition-change event.
            elif record_type == "EVENT":

                row_key = save_event(
                    data,
                    previous_condition
                )

            else:
                raise ValueError(
                    f"Unsupported record type: {record_type}"
                )

        except Exception as error:

            # Keep the failed record in the queue.
            print(
                f"[AZURE TABLE ERROR] "
                f"{record_type} upload failed: "
                f"{type(error).__name__}"
            )

            return

        # Remove the record only after successful upload.
        pending_writes.popleft()

        print(
            f"[AZURE TABLE] {record_type} saved | "
            f"RowKey: {row_key}"
        )

        attempts += 1


# ============================================================
# STEP 6: Validate incoming ESP32 telemetry.
# ============================================================

def validate_telemetry(data):
    """
    Validate one MQTT JSON telemetry message.

    Reject:
        - Non-dictionary JSON.
        - Missing required fields.
        - Empty device identifiers.
        - Non-numeric sensor readings.
        - NaN or infinite sensor readings.
        - Unknown equipment conditions.

    Return:
        Normalized telemetry dictionary.
    """

    if not isinstance(data, dict):

        raise ValueError(
            "Telemetry must be a JSON object."
        )

    # Required fields published by the ESP32.
    required_fields = (
        "device_id",
        "temperature",
        "humidity",
        "vibration",
        "condition",
    )

    missing_fields = [
        field
        for field in required_fields
        if field not in data
    ]

    if missing_fields:

        raise ValueError(
            f"Missing fields: {missing_fields}"
        )

    # Ensure a meaningful device identifier.
    if not str(data["device_id"]).strip():

        raise ValueError(
            "Device ID cannot be empty."
        )

    # Validate all three physical sensor measurements.
    for field in (
        "temperature",
        "humidity",
        "vibration",
    ):

        try:

            value = float(data[field])

        except (TypeError, ValueError) as error:

            raise ValueError(
                f"Invalid numeric value: {field}"
            ) from error

        # Reject booleans and non-finite numbers.
        if (
            isinstance(data[field], bool)
            or not math.isfinite(value)
        ):

            raise ValueError(
                f"Invalid numeric value: {field}"
            )

        # Normalize the number for downstream processing.
        data[field] = value

    # Normalize the equipment condition.
    condition = str(
        data["condition"]
    ).upper()

    if condition not in (
        "NORMAL",
        "WARNING",
        "CRITICAL",
    ):

        raise ValueError(
            f"Unknown equipment condition: {condition}"
        )

    data["condition"] = condition

    return data


# ============================================================
# STEP 7: Handle optional Azure Log Analytics uploads.
# ============================================================

def maybe_upload_logs(data, now):
    """
    Preserve the existing Log Analytics integration.

    This function does nothing when
    AZURE_LOG_ANALYTICS_ENABLED=false.

    Log Analytics uses independent upload timing.
    """

    if not LOG_ANALYTICS_ENABLED:
        return

    device_id = data["device_id"]

    condition = data["condition"]

    previous_time = last_logs_upload_time.get(
        device_id
    )

    previous_condition = last_logs_condition.get(
        device_id
    )

    # Upload on first reading, after 30 seconds,
    # or when the equipment condition changes.
    upload_needed = (
        previous_time is None
        or now - previous_time >= LOG_INTERVAL_SECONDS
        or condition != previous_condition
    )

    if not upload_needed:
        return

    try:

        success = upload_telemetry(data)

        if success:

            last_logs_upload_time[device_id] = now

            last_logs_condition[device_id] = condition

            print(
                "[LOG ANALYTICS] "
                "Upload confirmed by ingestion API"
            )

        else:

            print(
                "[LOG ANALYTICS] "
                "Upload not completed"
            )

    except Exception as error:

        print(
            "[LOG ANALYTICS ERROR] "
            f"{type(error).__name__}"
        )


# ============================================================
# STEP 8: Publish live Grafana alerts.
# ============================================================

def publish_live_alert(client, device_id, old_condition, data):
    """
    Publish one MQTT alert when the equipment condition changes.

    This is separate from Azure Table Storage event saving.

    Example:
        NORMAL -> WARNING
        WARNING -> CRITICAL
        CRITICAL -> NORMAL

    The alert is NOT retained by MQTT.
    """

    severity = data["condition"]

    event = {
        "device_id": device_id,
        "timestamp": (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        ),
        "previous_condition": old_condition,
        "condition": severity,
        "severity": (
            "RECOVERY"
            if severity == "NORMAL"
            else severity
        ),
        "message": (
            f"Equipment condition changed: "
            f"{old_condition} -> {severity}"
        ),
        "temperature": data["temperature"],
        "humidity": data["humidity"],
        "vibration": data["vibration"],
    }

    result = client.publish(
        LIVE_ALERT_TOPIC,
        json.dumps(event),
        qos=0,
        retain=False
    )

    if result.rc != mqtt.MQTT_ERR_SUCCESS:

        print(
            f"[LIVE ALERT ERROR] "
            f"Publish failed: {result.rc}"
        )

    else:

        print(
            f"[LIVE ALERT] "
            f"{old_condition} -> {severity}"
        )


# ============================================================
# AI/ML: Publish an independent prediction for a completed window.
# ============================================================

def publish_ml_prediction(client, summary):
    """Run Isolation Forest on a full 30-second summary and publish to MQTT.

    A failed ML inference must not interrupt existing SUMMARY uploads,
    alerts, or live connectivity monitoring.
    """
    try:
        prediction = anomaly_detector.predict(summary)
    except Exception as error:
        print(f"[ML ERROR] Prediction failed: {type(error).__name__}: {error}")
        return

    if prediction is None:
        print("[ML] Skipping prediction: summary contains missing/invalid measurements")
        return

    # Use both Grafana-friendly names and the complete sensor feature values.
    payload = {
        "device_id": prediction["device_id"],
        "time": prediction["recorded_at"],
        "timestamp": prediction["recorded_at"],
        "status": prediction["status"],
        "anomaly_score": prediction["anomaly_score"],
        "model": prediction["model"],
        "features": prediction["features"],
    }

    result = client.publish(
        LIVE_ML_TOPIC,
        json.dumps(payload),
        qos=1,
        retain=True,
    )

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(
            f"[ML] {prediction['device_id']} | "
            f"{prediction['status']} | "
            f"Anomaly score: {prediction['anomaly_score']:.6f}"
        )
    else:
        print(f"[ML ERROR] MQTT publish failed: {result.rc}")


# ============================================================
# STEP 9: Publish live connectivity for Grafana.
# ============================================================

def connectivity_worker(client, stop_event):
    """
    Publish retained connectivity snapshots every 2 seconds.

    ONLINE:
        Valid ESP32 telemetry was received within 10 seconds.

    OFFLINE:
        No valid ESP32 telemetry received within 10 seconds.

    UNKNOWN:
        The Python subscriber disconnected unexpectedly.
        This is handled by the MQTT Last Will message.

    This worker runs independently from the telemetry callback.
    """

    previous_state = None

    while not stop_event.is_set():

        # Read the last telemetry timestamp safely.
        with connectivity_lock:

            seen_at = last_telemetry_monotonic

            seen_wall = last_telemetry_wall_time

        # Calculate time since the last valid message.
        age = (
            None
            if seen_at is None
            else max(
                0,
                time.monotonic() - seen_at
            )
        )

        online = (
            age is not None
            and age <= OFFLINE_TIMEOUT_SECONDS
        )

        state = (
            "ONLINE"
            if online
            else "OFFLINE"
        )

        payload = {
            "device_id": "ESP32-001",
            "status": state,
            "online": online,
            "last_seen": seen_wall,
            "seconds_since_last_message": (
                round(age, 1)
                if age is not None
                else None
            ),
            "checked_at": (
                datetime.now()
                .astimezone()
                .isoformat(timespec="seconds")
            ),
        }

        # Retain the latest status for new Grafana subscribers.
        result = client.publish(
            LIVE_CONNECTIVITY_TOPIC,
            json.dumps(payload),
            qos=1,
            retain=True
        )

        # Print only when the state changes.
        if (
            result.rc == mqtt.MQTT_ERR_SUCCESS
            and state != previous_state
        ):

            print(
                f"[CONNECTIVITY] {state}"
            )

            previous_state = state

        # Wait without blocking the main MQTT thread.
        stop_event.wait(
            CONNECTIVITY_CHECK_SECONDS
        )


# ============================================================
# STEP 10: Handle MQTT connection and reconnection.
# ============================================================

def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties,
):
    """
    Called when the subscriber connects to Mosquitto.

    Subscribe again after reconnection.
    """

    if reason_code == 0:

        print(
            "[MQTT] Connected to broker"
        )

        client.subscribe([
            (TELEMETRY_TOPIC, 0),
            (STATUS_TOPIC, 0),
        ])

        print(
            "[MQTT] Subscribed to telemetry and status"
        )

    else:

        print(
            "[MQTT ERROR] "
            f"Connection failed: {reason_code}"
        )


# ============================================================
# STEP 11: Process incoming MQTT messages.
# ============================================================

def on_message(client, userdata, message):
    """
    Called whenever Mosquitto delivers a message.

    Processing:
        1. Handle ONLINE/OFFLINE messages.
        2. Decode and validate sensor telemetry.
        3. Print actual sensor readings.
        4. Detect equipment condition transitions.
        5. Publish live condition-change alerts.
        6. Add readings to the statistics calculator.
        7. Upload completed summaries and events to Azure.
        8. Optionally upload to Log Analytics.
    """

    # Create a readable local timestamp.
    timestamp = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    # Convert MQTT message bytes into text.
    payload = message.payload.decode(
        "utf-8",
        errors="replace"
    )

    # --------------------------------------------------------
    # STEP 11A: Handle device connectivity messages.
    # --------------------------------------------------------

    if message.topic == STATUS_TOPIC:

        print(
            f"[{timestamp}] "
            f"Device status: {payload}"
        )

        return

    # Ignore unexpected topics.
    if message.topic != TELEMETRY_TOPIC:
        return

    # --------------------------------------------------------
    # STEP 11B: Validate sensor telemetry.
    # --------------------------------------------------------

    try:

        # Convert JSON text to a Python dictionary.
        data = validate_telemetry(
            json.loads(payload)
        )

        # Validate Log Analytics field mapping locally.
        # This does not send data to Azure Log Analytics.
        prepare_telemetry(data)

    except (
        json.JSONDecodeError,
        ValueError,
        TypeError,
        KeyError,
        OverflowError,
    ) as error:

        print(
            "[MQTT ERROR] "
            f"Invalid telemetry: {error}"
        )

        return

    # Use monotonic time for reliable interval tracking.
    now = time.monotonic()

    # Update last-seen timestamps only for valid telemetry.
    global last_telemetry_monotonic
    global last_telemetry_wall_time

    with connectivity_lock:

        last_telemetry_monotonic = now

        last_telemetry_wall_time = timestamp

    device_id = str(
        data["device_id"]
    )

    condition = data["condition"]

    # --------------------------------------------------------
    # STEP 11C: Print live sensor readings.
    # --------------------------------------------------------

    print(
        f"[MQTT] Device: {device_id} | "
        f"Temp: {data['temperature']} C | "
        f"Humidity: {data['humidity']}% | "
        f"Vibration: {data['vibration']} | "
        f"Condition: {condition}"
    )

    # --------------------------------------------------------
    # STEP 11D: Detect equipment condition changes.
    # --------------------------------------------------------

    previous_condition = last_seen_condition.get(
        device_id
    )

    # The first reading establishes the initial condition.
    # It is not considered a recovery event.
    if (
        previous_condition is not None
        and condition != previous_condition
    ):

        # Preserve the exact sensor snapshot at transition.
        queue_write(
            record_type="EVENT",
            data=dict(data),
            previous_condition=previous_condition,
        )

        print(
            f"[EVENT] "
            f"{previous_condition} -> {condition}"
        )

        # Send the event immediately to Grafana via MQTT.
        publish_live_alert(
            client,
            device_id,
            previous_condition,
            data
        )

    # Update condition tracking after processing transition.
    last_seen_condition[device_id] = condition

    # --------------------------------------------------------
    # STEP 11E: Aggregate every valid MQTT reading.
    # --------------------------------------------------------

    # Create an aggregator for a device when first seen.
    if device_id not in aggregators:

        aggregators[device_id] = TelemetryAggregator(
            device_id,
            SUMMARY_INTERVAL_SECONDS,
        )

    aggregator = aggregators[device_id]

    # Add this reading to the current window.
    summary = aggregator.add_reading(
        data,
        now,
    )

    if summary is not None:

        # Queue the completed summary for Azure.
        queue_write(
            record_type="SUMMARY",
            data=summary,
        )

        # Predict on exactly the same completed window used for training.
        # Separate ML behavior from rule-based WARNING/CRITICAL logic.
        publish_ml_prediction(client, summary)

        print(
            f"[SUMMARY] {device_id} | "
            f"Samples: {summary['sample_count']} | "
            f"Vibration avg: "
            f"{summary['vibration']['avg']} | "
            f"max: {summary['vibration']['max']} | "
            f"Worst: {summary['worst_condition']}"
        )

    # --------------------------------------------------------
    # STEP 11F: Upload queued records to Azure Table Storage.
    # --------------------------------------------------------

    flush_pending_writes()

    # --------------------------------------------------------
    # STEP 11G: Optional Azure Log Analytics upload.
    # --------------------------------------------------------

    maybe_upload_logs(
        data,
        now,
    )


# ============================================================
# STEP 12: Start the MQTT subscriber.
# ============================================================

def main():
    """
    Connect to the password-protected Mosquitto broker.

    Continue receiving messages until Ctrl+C is pressed.
    """

    # Read the MQTT password without displaying it.
    password = (
        os.getenv("MQTT_PASSWORD")
        or getpass.getpass(
            "Enter MQTT password: "
        )
    )

    # Use Paho MQTT callback API version 2.
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="equipment-monitor-backend",
    )

    # Authenticate with the existing broker.
    client.username_pw_set(
        MQTT_USERNAME,
        password,
    )

    # If the subscriber disconnects unexpectedly,
    # publish UNKNOWN as its MQTT Last Will message.
    client.will_set(
        LIVE_CONNECTIVITY_TOPIC,
        json.dumps({
            "device_id": "ESP32-001",
            "status": "UNKNOWN",
            "online": False,
        }),
        qos=1,
        retain=True,
    )

    # Register MQTT callback functions.
    client.on_connect = on_connect
    client.on_message = on_message

    print(
        f"[MQTT] Connecting to "
        f"{BROKER_HOST}:{BROKER_PORT}"
    )

    print(
        "[AZURE TABLE] "
        "30-second SUMMARY + condition-change EVENT mode"
    )

    print(f"[ML] Isolation Forest enabled | MQTT topic: {LIVE_ML_TOPIC}")

    print(
        "[LOG ANALYTICS] "
        + (
            "ENABLED"
            if LOG_ANALYTICS_ENABLED
            else "DISABLED - no log ingestion"
        )
    )

    stop_event = threading.Event()

    connectivity_thread = None

    try:

        # Connect to Mosquitto.
        client.connect(
            BROKER_HOST,
            BROKER_PORT,
            keepalive=60,
        )

        # Run MQTT networking in the background.
        client.loop_start()

        # Start independent connectivity monitoring.
        connectivity_thread = threading.Thread(
            target=connectivity_worker,
            args=(client, stop_event),
            daemon=True,
        )

        connectivity_thread.start()

        # Keep the program running until Ctrl+C.
        while True:
            time.sleep(1)

    except KeyboardInterrupt:

        print(
            "\n[MQTT] Stopping subscriber"
        )

    except OSError as error:

        print(
            f"[MQTT ERROR] Network failure: {error}"
        )

    finally:

        # Stop connectivity monitoring.
        stop_event.set()

        if connectivity_thread is not None:

            connectivity_thread.join(
                timeout=3
            )

        # Disconnect cleanly.
        client.disconnect()

        client.loop_stop()

        # Warn if unsaved Azure records remain in memory.
        if pending_writes:

            print(
                "[AZURE TABLE WARNING] "
                f"{len(pending_writes)} unsaved records "
                "remain in memory"
            )


# ============================================================
# STEP 13: Program entry point.
# ============================================================

if __name__ == "__main__":
    main()
