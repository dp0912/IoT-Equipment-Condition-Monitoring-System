
"""
Azure Log Analytics telemetry integration.

Purpose:
    Prepare ESP32 telemetry for Azure Monitor Logs ingestion.

Data flow:
    ESP32 -> MQTT -> Python subscriber -> Azure Log Analytics

Safety:
    Actual uploads are disabled unless
    AZURE_LOG_ANALYTICS_ENABLED=true in the root .env file.

Authentication:
    Microsoft Entra ID application using a client ID,
    tenant ID, and client secret stored in .env.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from azure.monitor.ingestion import LogsIngestionClient


# ---------------------------------------------------------
# STEP 1: Load environment variables from the project root.
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------
# STEP 2: Read Azure configuration.
#
# These values are stored in .env, not in the Python code.
# ---------------------------------------------------------

TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")

MONITOR_ENDPOINT = os.getenv("AZURE_MONITOR_ENDPOINT", "")
DCR_IMMUTABLE_ID = os.getenv("AZURE_DCR_IMMUTABLE_ID", "")
MONITOR_STREAM = os.getenv("AZURE_MONITOR_STREAM", "")

# Uploads remain disabled unless explicitly enabled.
LOG_ANALYTICS_ENABLED = (
    os.getenv("AZURE_LOG_ANALYTICS_ENABLED", "false")
    .strip()
    .lower()
    == "true"
)


# ---------------------------------------------------------
# STEP 3: Validate required configuration.
# ---------------------------------------------------------

def validate_configuration():
    """
    Check whether the required Azure settings exist.

    This function does not connect to Azure,
    request authentication tokens, or upload data.

    Returns:
        A list of missing environment variable names.
    """

    required_settings = {
        "AZURE_TENANT_ID": TENANT_ID,
        "AZURE_CLIENT_ID": CLIENT_ID,
        "AZURE_CLIENT_SECRET": CLIENT_SECRET,
        "AZURE_MONITOR_ENDPOINT": MONITOR_ENDPOINT,
        "AZURE_DCR_IMMUTABLE_ID": DCR_IMMUTABLE_ID,
        "AZURE_MONITOR_STREAM": MONITOR_STREAM,
    }

    missing = []

    for name, value in required_settings.items():
        if not value.strip():
            missing.append(name)

    return missing


# ---------------------------------------------------------
# STEP 4: Convert ESP32 MQTT telemetry into the schema
# expected by our Azure Data Collection Rule (DCR).
#
# MQTT uses lowercase/snake_case property names.
# Azure Log Analytics uses the column names we created
# in Custom-EquipmentTelemetry_CL.
# ---------------------------------------------------------

def prepare_telemetry(telemetry):
    """
    Convert one ESP32 MQTT telemetry dictionary into
    a Log Analytics-compatible dictionary.

    Args:
        telemetry: Dictionary received from MQTT.

    Returns:
        Dictionary matching the Azure DCR stream schema.
    """

    if not isinstance(telemetry, dict):
        raise ValueError("Telemetry must be a dictionary.")

    # Use the current UTC time as the ingestion timestamp.
    timestamp = datetime.now(timezone.utc).isoformat()

    # Match the exact column names and types in the DCR.
    return {
        "TimeGenerated": timestamp,
        "DeviceId": str(telemetry["device_id"]),
        "Temperature": float(telemetry["temperature"]),
        "Humidity": int(telemetry["humidity"]),
        "Vibration": float(telemetry["vibration"]),
        "Condition": str(telemetry["condition"]),
        "SensorCondition": str(
            telemetry.get("sensor_condition", "UNKNOWN")
        ),
        "Mode": str(telemetry.get("mode", "UNKNOWN")),
        "MotorRunning": bool(
            telemetry.get("motor_running", False)
        ),
        "MotorArmed": bool(
            telemetry.get("motor_armed", False)
        ),
        "StopLatched": bool(
            telemetry.get("stop_latched", False)
        ),
        "DHTValid": bool(
            telemetry.get("dht_valid", False)
        ),
        "VibrationValid": bool(
            telemetry.get("vibration_valid", False)
        ),
        "UptimeMs": int(telemetry.get("uptime_ms", 0)),
    }


# ---------------------------------------------------------
# STEP 5: Create the Azure Logs Ingestion client.
#
# This uses application credentials rather than an
# interactive Microsoft Authenticator login.
# ---------------------------------------------------------

def create_ingestion_client():
    """
    Create an authenticated Azure Logs Ingestion client.

    Returns:
        LogsIngestionClient instance.
    """

    missing = validate_configuration()

    if missing:
        raise ValueError(
            "Missing Azure settings: " + ", ".join(missing)
        )

    # Authenticate the registered application.
    credential = ClientSecretCredential(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )

    # Connect to the Azure Monitor ingestion endpoint.
    return LogsIngestionClient(
        endpoint=MONITOR_ENDPOINT,
        credential=credential,
    )


# ---------------------------------------------------------
# STEP 6: Upload telemetry to Azure Log Analytics.
#
# IMPORTANT:
# This function never uploads while the feature is disabled.
# ---------------------------------------------------------

def upload_telemetry(telemetry):
    """
    Upload one ESP32 telemetry record to Log Analytics.

    Returns:
        True  -> Azure accepted the upload.
        False -> Upload disabled or failed.
    """

    # Prevent accidental cloud ingestion and charges.
    if not LOG_ANALYTICS_ENABLED:
        print("[LOG ANALYTICS] Upload disabled.")
        return False

    # Convert the MQTT message to the DCR schema.
    record = prepare_telemetry(telemetry)

    try:
        # Authenticate with Microsoft Entra ID.
        client = create_ingestion_client()

        # Upload one telemetry record.
        client.upload(
            rule_id=DCR_IMMUTABLE_ID,
            stream_name=MONITOR_STREAM,
            logs=[record],
        )

        print("[LOG ANALYTICS] Telemetry uploaded.")
        return True

    except Exception as error:
        # Do not print raw exception details because they
        # might contain sensitive request information.
        print(
            "[LOG ANALYTICS] Upload failed:",
            type(error).__name__,
        )
        return False


# ---------------------------------------------------------
# STEP 7: Local configuration check.
#
# Running this file directly only validates settings.
# It never sends data to Azure.
# ---------------------------------------------------------

if __name__ == "__main__":

    print("\nAzure Log Analytics Configuration Check")
    print("---------------------------------------")

    missing = validate_configuration()

    if missing:
        print("Configuration: INCOMPLETE")
        print("Missing settings:", ", ".join(missing))
    else:
        print("Configuration: COMPLETE")

    print(
        "Cloud uploads:",
        "ENABLED" if LOG_ANALYTICS_ENABLED else "DISABLED",
    )

    print("No Azure telemetry was uploaded.\n")
