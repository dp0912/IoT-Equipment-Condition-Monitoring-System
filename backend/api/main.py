
"""
IoT Equipment Condition Monitoring System
=========================================

File: backend/api/main.py

Purpose:
    Provide a REST API that reads equipment telemetry
    from Microsoft Azure Table Storage.

How this file works:
    1. Loads Azure credentials from the private .env file.
    2. Connects to the EquipmentTelemetry table in Azure.
    3. Retrieves sensor measurements stored by our MQTT backend.
    4. Converts Azure records into JSON responses.
    5. Makes those responses available to our future dashboard.

Important:
    This API reads historical data from Azure.
    It does not control the motor or change ESP32 firmware.

    Azure credentials must NEVER be placed directly in this file.
"""

import os
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from azure.data.tables import TableServiceClient
from azure.core.exceptions import AzureError


# ------------------------------------------------------------
# SECTION 1: LOAD PRIVATE AZURE CONFIGURATION
# ------------------------------------------------------------

# Locate the main project directory.
#
# __file__ points to:
# backend/api/main.py
#
# parents[2] points to the project root directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load environment variables from the project's private .env.
# The .env file must remain excluded from GitHub.
load_dotenv(PROJECT_ROOT / ".env")

# Read Azure settings without exposing their actual values.
AZURE_CONNECTION_STRING = os.getenv(
    "AZURE_STORAGE_CONNECTION_STRING"
)

AZURE_TABLE_NAME = os.getenv(
    "AZURE_TABLE_NAME",
    "EquipmentTelemetry"
)


# ------------------------------------------------------------
# SECTION 2: CREATE THE FASTAPI APPLICATION
# ------------------------------------------------------------

# FastAPI automatically creates interactive API documentation.
#
# Once the server is running:
# http://127.0.0.1:8000/docs
app = FastAPI(
    title="IoT Equipment Condition Monitoring API",
    description=(
        "REST API for reading equipment telemetry "
        "stored in Microsoft Azure Table Storage."
    ),
    version="1.0.0"
)


# ------------------------------------------------------------
# SECTION 3: CONNECT TO AZURE TABLE STORAGE
# ------------------------------------------------------------

def get_table_client():
    """
    Create an authenticated connection to our Azure table.

    Returns:
        Azure TableClient object.

    Raises:
        HTTPException:
            If credentials are missing or Azure cannot be reached.

    Note:
        The connection is created when an API request needs it.
        This prevents the whole API from failing immediately
        when Azure is temporarily unavailable.
    """

    # Check that our private connection string was loaded.
    if not AZURE_CONNECTION_STRING:
        raise HTTPException(
            status_code=503,
            detail="Azure storage configuration is missing."
        )

    try:
        # Authenticate using the private Azure connection string.
        service_client = TableServiceClient.from_connection_string(
            conn_str=AZURE_CONNECTION_STRING
        )

        # Select our existing EquipmentTelemetry table.
        table_client = service_client.get_table_client(
            table_name=AZURE_TABLE_NAME
        )

        return table_client

    except (AzureError, ValueError) as error:
        # Avoid displaying Azure credentials or sensitive details.
        print(
            "[API] Unable to initialize Azure Table Storage:",
            type(error).__name__
        )

        raise HTTPException(
            status_code=503,
            detail="Unable to connect to Azure Table Storage."
        ) from error


# ------------------------------------------------------------
# SECTION 4: CONVERT AZURE DATA INTO JSON
# ------------------------------------------------------------

def serialize_entity(entity):
    """
    Convert one Azure Table Storage entity into a JSON-safe dict.

    Azure may return datetime objects that cannot be directly
    represented in ordinary JSON without conversion.

    We convert datetime values into ISO 8601 strings.

    Example:
        2026-10-10T22:38:20+00:00
    """

    result = {}

    for key, value in dict(entity).items():

        # Convert Python datetime values into readable strings.
        if isinstance(value, datetime):
            result[key] = value.isoformat()

        else:
            result[key] = value

    return result


# ------------------------------------------------------------
# SECTION 5: READ TELEMETRY FROM AZURE
# ------------------------------------------------------------

def read_telemetry(device_id=None, limit=50):
    """
    Retrieve equipment telemetry from Azure Table Storage.

    Parameters:
        device_id:
            Optional ESP32 device identifier.
            When provided, only that device's data is returned.

        limit:
            Maximum number of recent records to return.

    Important:
        Azure Table Storage does not automatically return
        records in chronological order.

        For this initial project implementation, we read
        matching records, sort them by RowKey, and return
        the newest records.

        Our existing RowKeys start with UTC timestamps, so
        sorting them gives us chronological ordering.

    Note:
        This approach is suitable for our current small
        student-project dataset. A production-scale system
        should use a query/indexing strategy optimized for
        retrieving recent records.
    """

    table_client = get_table_client()

    try:
        # Query one device if an ID was supplied.
        if device_id is not None:

            # Parameterized queries safely handle user input.
            entities = table_client.query_entities(
                query_filter="PartitionKey eq @device",
                parameters={"device": device_id}
            )

        else:
            # Otherwise retrieve records across all devices.
            entities = table_client.list_entities()

        # Convert Azure entities into regular dictionaries.
        records = [
            serialize_entity(entity)
            for entity in entities
        ]

        # Newest timestamp-based RowKey first.
        records.sort(
            key=lambda record: record.get("RowKey", ""),
            reverse=True
        )

        # Return only the requested number of records.
        return records[:limit]

    except AzureError as error:
        # Log the error type without exposing secret values.
        print(
            "[API] Azure telemetry query failed:",
            type(error).__name__
        )

        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve telemetry from Azure."
        ) from error


# ------------------------------------------------------------
# SECTION 6: API HEALTH ENDPOINT
# ------------------------------------------------------------

@app.get("/health")
def health():
    """
    Check whether the FastAPI application is running.

    This does not check Azure connectivity.
    It only confirms that the API server is responding.
    """

    return {
        "status": "running",
        "service": "IoT Equipment Monitoring API",
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    }


# ------------------------------------------------------------
# SECTION 7: RECENT TELEMETRY ENDPOINT
# ------------------------------------------------------------

@app.get("/api/telemetry")
def get_recent_telemetry(
    limit: int = Query(default=50, ge=1, le=500)
):
    """
    Retrieve the most recent sensor readings.

    Example:
        GET /api/telemetry?limit=10

    The limit parameter controls how many records we return.
    """

    records = read_telemetry(limit=limit)

    return {
        "count": len(records),
        "data": records
    }


# ------------------------------------------------------------
# SECTION 8: LATEST TELEMETRY ENDPOINT
# ------------------------------------------------------------

@app.get("/api/telemetry/latest")
def get_latest_telemetry():
    """
    Retrieve the latest available sensor measurement.

    This will eventually be useful for dashboard cards
    showing the latest temperature, humidity and vibration.
    """

    records = read_telemetry(limit=1)

    if not records:
        raise HTTPException(
            status_code=404,
            detail="No telemetry records found."
        )

    return records[0]


# ------------------------------------------------------------
# SECTION 9: DEVICE-SPECIFIC TELEMETRY ENDPOINT
# ------------------------------------------------------------

@app.get("/api/devices/{device_id}/telemetry")
def get_device_telemetry(
    device_id: str,
    limit: int = Query(default=50, ge=1, le=500)
):
    """
    Retrieve telemetry for one specific ESP32 device.

    Example:
        GET /api/devices/ESP32-001/telemetry?limit=10

    This allows us to support multiple ESP32 devices later.
    """

    records = read_telemetry(
        device_id=device_id,
        limit=limit
    )

    return {
        "device_id": device_id,
        "count": len(records),
        "data": records
    }


# ------------------------------------------------------------
# END OF FILE
# ------------------------------------------------------------
