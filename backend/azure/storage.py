
"""
PROJECT: IoT Equipment Condition Monitoring System
FILE: backend/azure/storage.py

PURPOSE:
    Store ESP32 equipment monitoring records in Azure Table Storage.

SUPPORTED RECORD TYPES:
    LEGACY  - Original individual telemetry records.
    SUMMARY - 30-second aggregated sensor statistics.
    EVENT   - Equipment condition transitions and alerts.

AZURE RESOURCES:
    Storage account: stiotequipmentmonitor01
    Table: EquipmentTelemetry

SECURITY:
    Credentials are loaded from the private project .env file.
    Never commit .env or print the connection string.
"""

# ---------------------------------------------------------
# STEP 1: Import required Python libraries.
# ---------------------------------------------------------

import os

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from azure.data.tables import TableServiceClient
from dotenv import load_dotenv


# ---------------------------------------------------------
# STEP 2: Load the existing Azure configuration.
# ---------------------------------------------------------

# storage.py is inside backend/azure.
# parents[2] points to the project root directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load private configuration from the existing .env file.
load_dotenv(PROJECT_ROOT / ".env")

# Keep the existing environment variable names.
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

TABLE_NAME = os.getenv(
    "AZURE_TABLE_NAME",
    "EquipmentTelemetry",
)

# Do not continue if the connection string is missing.
if not CONNECTION_STRING:
    raise RuntimeError(
        "AZURE_STORAGE_CONNECTION_STRING is missing."
    )


# ---------------------------------------------------------
# STEP 3: Initialize the existing Azure Table client.
# ---------------------------------------------------------

# Reuse the existing storage account.
service_client = TableServiceClient.from_connection_string(
    conn_str=CONNECTION_STRING
)

# Reuse the existing EquipmentTelemetry table.
table_client = service_client.get_table_client(
    table_name=TABLE_NAME
)


# ---------------------------------------------------------
# STEP 4: Helper functions shared by all record types.
# ---------------------------------------------------------

def create_row_key():
    """
    Generate a unique, chronologically sortable Azure RowKey.

    Example:
        20261011T020420074879Z-a1b2c3d4
    """

    now = datetime.now(timezone.utc)

    return (
        f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-"
        f"{uuid4().hex[:8]}"
    )


def create_base_entity(device_id, record_type):
    """
    Build the fields required for every Azure Table record.

    PartitionKey:
        Identifies the ESP32 device.

    RowKey:
        Identifies one unique record.

    RecordType:
        Distinguishes LEGACY, SUMMARY, and EVENT.
    """

    now = datetime.now(timezone.utc)

    return {
        "PartitionKey": str(device_id),
        "RowKey": create_row_key(),
        "RecordedAt": now.isoformat(),
        "RecordType": record_type,
    }


def upload_entity(entity):
    """
    Insert a completed entity into the existing Azure table.

    Azure SDK errors are allowed to propagate to the caller,
    so the MQTT subscriber can handle them independently.
    """

    table_client.create_entity(entity=entity)

    return entity["RowKey"]


# ---------------------------------------------------------
# STEP 5: Preserve the original telemetry function.
# ---------------------------------------------------------

def save_telemetry(data):
    """
    Save one original ESP32 telemetry reading.

    This function remains available for existing code.
    The upgraded subscriber will eventually use
    save_summary() and save_event() instead.
    """

    entity = create_base_entity(
        device_id=data["device_id"],
        record_type="LEGACY",
    )

    # Keep the same field names expected by the existing API.
    entity.update({
        "Temperature": float(data["temperature"]),
        "Humidity": float(data["humidity"]),
        "Vibration": float(data.get("vibration") or 0),

        "Condition": str(data["condition"]),
        "SensorCondition": str(
            data.get("sensor_condition", "")
        ),
        "Mode": str(data.get("mode", "")),

        "MotorRunning": bool(
            data.get("motor_running", False)
        ),
        "MotorArmed": bool(
            data.get("motor_armed", False)
        ),
        "StopLatched": bool(
            data.get("stop_latched", False)
        ),

        "DHTValid": bool(data.get("dht_valid", False)),
        "VibrationValid": bool(
            data.get("vibration_valid", False)
        ),

        "UptimeMs": int(data.get("uptime_ms") or 0),
    })

    return upload_entity(entity)


# ---------------------------------------------------------
# STEP 6: Save 30-second sensor statistics.
# ---------------------------------------------------------

def save_summary(summary):
    """
    Save one completed 30-second aggregation window.

    Expected summary:
        Output from TelemetryAggregator.build_summary().

    Fields include:
        Average, minimum, maximum, and latest values
        for temperature, humidity, and vibration.

    Also includes:
        Number of samples, latest condition,
        and worst condition observed in the window.
    """

    entity = create_base_entity(
        device_id=summary["device_id"],
        record_type="SUMMARY",
    )

    # Window information.
    entity.update({
        "WindowSeconds": int(summary["window_seconds"]),
        "SampleCount": int(summary["sample_count"]),

        "Condition": str(
            summary["latest_condition"]
        ),
        "WorstCondition": str(
            summary["worst_condition"]
        ),
    })

    # Store statistics for each physical sensor.
    #
    # Azure Table Storage stores scalar properties.
    # Nested dictionaries cannot be saved directly,
    # so we flatten each measurement into columns.

    sensor_columns = {
        "temperature": "Temperature",
        "humidity": "Humidity",
        "vibration": "Vibration",
    }

    for sensor_name, column_prefix in sensor_columns.items():

        statistics = summary[sensor_name]

        # A sensor can have zero valid readings.
        # Azure Table Storage should not receive None
        # values for numeric measurements.
        for statistic_name, column_suffix in (
            ("avg", "Avg"),
            ("min", "Min"),
            ("max", "Max"),
            ("latest", "Latest"),
        ):

            value = statistics.get(statistic_name)

            if value is not None:
                entity[
                    f"{column_prefix}{column_suffix}"
                ] = float(value)

        entity[
            f"{column_prefix}SampleCount"
        ] = int(statistics.get("count", 0))

    # Preserve latest operating state from the ESP32.
    latest = summary["latest_telemetry"]

    entity.update({
        "Temperature": float(
            latest.get("temperature") or 0
        ),
        "Humidity": float(
            latest.get("humidity") or 0
        ),
        "Vibration": float(
            latest.get("vibration") or 0
        ),
        "SensorCondition": str(
            latest.get("sensor_condition", "")
        ),
        "Mode": str(latest.get("mode", "")),
        "MotorRunning": bool(
            latest.get("motor_running", False)
        ),
        "MotorArmed": bool(
            latest.get("motor_armed", False)
        ),
        "StopLatched": bool(
            latest.get("stop_latched", False)
        ),
        "DHTValid": bool(
            latest.get("dht_valid", False)
        ),
        "VibrationValid": bool(
            latest.get("vibration_valid", False)
        ),
        "UptimeMs": int(latest.get("uptime_ms") or 0),
    })

    return upload_entity(entity)


# ---------------------------------------------------------
# STEP 7: Save equipment condition-change events.
# ---------------------------------------------------------

def save_event(data, previous_condition):
    """
    Save a condition transition as a separate Azure event.

    Examples:
        NORMAL -> WARNING
        WARNING -> CRITICAL
        CRITICAL -> NORMAL (recovery)

    The complete sensor snapshot at the transition
    is saved with the event.
    """

    current_condition = str(data["condition"]).upper()

    previous_condition = (
        str(previous_condition).upper()
        if previous_condition is not None
        else "UNKNOWN"
    )

    # Identify the event category.
    if current_condition == "CRITICAL":
        event_type = "CRITICAL"

    elif current_condition == "WARNING":
        event_type = "WARNING"

    elif current_condition == "NORMAL":
        event_type = "RECOVERY"

    else:
        event_type = "CONDITION_CHANGE"

    entity = create_base_entity(
        device_id=data["device_id"],
        record_type="EVENT",
    )

    entity.update({
        "EventType": event_type,
        "PreviousCondition": previous_condition,
        "Condition": current_condition,

        # Actual readings at the transition.
        "Temperature": float(data["temperature"]),
        "Humidity": float(data["humidity"]),
        "Vibration": float(data.get("vibration") or 0),

        # Equipment operating state.
        "SensorCondition": str(
            data.get("sensor_condition", "")
        ),
        "Mode": str(data.get("mode", "")),
        "MotorRunning": bool(
            data.get("motor_running", False)
        ),
        "MotorArmed": bool(
            data.get("motor_armed", False)
        ),
        "StopLatched": bool(
            data.get("stop_latched", False)
        ),
        "DHTValid": bool(
            data.get("dht_valid", False)
        ),
        "VibrationValid": bool(
            data.get("vibration_valid", False)
        ),
        "UptimeMs": int(data.get("uptime_ms") or 0),
    })

    return upload_entity(entity)


# ---------------------------------------------------------
# STEP 8: Local configuration check.
# ---------------------------------------------------------

if __name__ == "__main__":

    print("Azure Table Storage configuration")
    print("---------------------------------")
    print(f"Table: {TABLE_NAME}")
    print("Client initialized successfully")
    print("No telemetry uploaded")
