
# ================================================================
# PROJECT: IoT Equipment Condition Monitoring System
# FILE: backend/azure/storage.py
# ================================================================
#
# PURPOSE:
#   Save real equipment telemetry from our ESP32 into
#   Microsoft Azure Table Storage.
#
# WHY THIS FILE EXISTS:
#   The MQTT subscriber receives sensor data, but MQTT itself
#   is not our historical database.
#
#   This module takes validated sensor readings and stores
#   them permanently in our Azure table.
#
# DATA FLOW:
#   ESP32 -> Mosquitto -> subscriber.py -> storage.py -> Azure
#
# AZURE RESOURCES:
#   Storage account: stiotequipmentmonitor01
#   Table:           EquipmentTelemetry
#
# SECURITY:
#   The Azure connection string is loaded from the private
#   .env file. Never put the connection string in Python code
#   or upload .env to GitHub.
# ================================================================


# ------------------------------------------------
# STEP 1: Import the libraries we need
# ------------------------------------------------

import os

# Used to create accurate UTC timestamps for readings.
from datetime import datetime, timezone

# Used to locate our project's root folder.
from pathlib import Path

# Used to generate unique IDs for Azure records.
from uuid import uuid4

# Microsoft Azure SDK for Table Storage.
from azure.data.tables import TableServiceClient

# Reads private configuration values from our .env file.
from dotenv import load_dotenv


# ------------------------------------------------
# STEP 2: Load our private Azure configuration
# ------------------------------------------------

# This file lives in:
#   project/backend/azure/storage.py
#
# parents[2] points to the main project directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load variables from the project's .env file.
load_dotenv(PROJECT_ROOT / ".env")

# Read the Azure connection string without printing it.
CONNECTION_STRING = os.getenv(
    "AZURE_STORAGE_CONNECTION_STRING"
)

# Read the table name.
# EquipmentTelemetry is used if no name is provided.
TABLE_NAME = os.getenv(
    "AZURE_TABLE_NAME",
    "EquipmentTelemetry"
)

# Stop immediately if Azure credentials are missing.
if not CONNECTION_STRING:
    raise RuntimeError(
        "Azure connection string is missing from .env"
    )


# ------------------------------------------------
# STEP 3: Connect to Azure Table Storage
# ------------------------------------------------

# Create the Azure service client using our credentials.
service_client = TableServiceClient.from_connection_string(
    conn_str=CONNECTION_STRING
)

# Select the table we already created in Azure.
#
# This does NOT create another table or storage account.
table_client = service_client.get_table_client(
    table_name=TABLE_NAME
)


# ------------------------------------------------
# STEP 4: Define the function that saves sensor data
# ------------------------------------------------

def save_telemetry(data):
    """
    Save one ESP32 telemetry message to Azure.

    Parameters
    ----------
    data : dict
        Validated JSON data received from the ESP32.

    Returns
    -------
    str
        Unique RowKey assigned to the saved record.

    Raises
    ------
    Exception
        Azure errors are passed to the MQTT subscriber,
        which logs them without stopping the entire app.
    """

    # Get the current date and time in UTC.
    # UTC is useful when devices operate in different regions.
    now = datetime.now(timezone.utc)

    # Create a unique RowKey using:
    #   1. Current UTC timestamp
    #   2. A short random identifier
    #
    # Example:
    #   20261010T220000123456Z-a1b2c3d4
    #
    # This prevents two readings from overwriting each other.
    row_key = (
        f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-"
        f"{uuid4().hex[:8]}"
    )

    # ------------------------------------------------
    # STEP 5: Build an Azure Table entity
    # ------------------------------------------------
    #
    # Azure Table Storage requires:
    #   PartitionKey -> Groups records by device.
    #   RowKey       -> Uniquely identifies each record.
    #
    # Other fields store our actual sensor readings.

    entity = {
        # Device identification.
        "PartitionKey": str(data["device_id"]),
        "RowKey": row_key,

        # Timestamp when the backend received the reading.
        "RecordedAt": now.isoformat(),

        # DHT11 sensor readings.
        "Temperature": float(data["temperature"]),
        "Humidity": float(data["humidity"]),

        # MPU6500 vibration measurement.
        "Vibration": float(data.get("vibration") or 0),

        # Equipment condition and operating mode.
        "Condition": str(data["condition"]),
        "SensorCondition": str(
            data.get("sensor_condition", "")
        ),
        "Mode": str(data.get("mode", "")),

        # Motor and safety-related operating states.
        "MotorRunning": bool(
            data.get("motor_running", False)
        ),
        "MotorArmed": bool(
            data.get("motor_armed", False)
        ),
        "StopLatched": bool(
            data.get("stop_latched", False)
        ),

        # Sensor validity indicators.
        "DHTValid": bool(data.get("dht_valid", False)),
        "VibrationValid": bool(
            data.get("vibration_valid", False)
        ),

        # ESP32 uptime in milliseconds.
        "UptimeMs": int(data.get("uptime_ms") or 0),
    }

    # ------------------------------------------------
    # STEP 6: Upload the record to Microsoft Azure
    # ------------------------------------------------

    # Send one entity to the EquipmentTelemetry table.
    #
    # create_entity() inserts a new record.
    # If Azure rejects the request, it raises an exception.
    table_client.create_entity(entity=entity)

    # Return the saved record's unique identifier.
    return row_key
