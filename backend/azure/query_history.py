
"""
PROJECT: IoT Equipment Condition Monitoring System
FILE: backend/azure/query_history.py

PURPOSE:
    Retrieve previously stored ESP32 telemetry from
    Azure Table Storage without modifying any records.

SUPPORTED RECORD TYPES:
    SUMMARY - Aggregated sensor statistics.
    EVENT   - Condition changes and recovery events.
    LEGACY  - Earlier individual telemetry records.

USED BY:
    Flask History API and machine learning training scripts.

SECURITY:
    Azure credentials are loaded from the private .env file.
    Credentials are never displayed.
"""

# ============================================================
# STEP 1: Import dependencies.
# ============================================================

import argparse
import os

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from azure.data.tables import TableServiceClient
from dotenv import load_dotenv


# ============================================================
# STEP 2: Load configuration.
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

CONNECTION_STRING = os.getenv(
    "AZURE_STORAGE_CONNECTION_STRING"
)

TABLE_NAME = os.getenv(
    "AZURE_TABLE_NAME",
    "EquipmentTelemetry"
)

DEFAULT_DEVICE = "ESP32-001"

RECORD_TYPES = (
    "ALL",
    "SUMMARY",
    "EVENT",
    "LEGACY",
)


# ============================================================
# STEP 3: Connect to Azure Table Storage.
# ============================================================

def get_table_client():
    """
    Create a read-only workflow for querying the table.

    This script performs query operations only.
    It does not insert, update or delete entities.
    """

    if not CONNECTION_STRING:
        raise RuntimeError(
            "AZURE_STORAGE_CONNECTION_STRING is missing "
            "from the project's .env file."
        )

    service = TableServiceClient.from_connection_string(
        CONNECTION_STRING
    )

    return service.get_table_client(
        table_name=TABLE_NAME
    )


# ============================================================
# STEP 4: Validate optional dates.
# ============================================================

def parse_date(value):
    """
    Accept a calendar date in YYYY-MM-DD format.
    """

    try:
        return date.fromisoformat(value)

    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Date must use YYYY-MM-DD format."
        ) from error


def start_of_day_utc(day):
    """
    Interpret supplied dates as UTC calendar dates.
    """

    return datetime(
        day.year,
        day.month,
        day.day,
        tzinfo=timezone.utc
    )


# ============================================================
# STEP 5: Query historical records.
# ============================================================

def query_history(
    table_client,
    device_id,
    record_type="ALL",
    start_date=None,
    end_date=None,
    limit=20,
):
    """
    Query records for one ESP32 device.

    Filtering by PartitionKey and RowKey is useful
    because the existing RowKey begins with a UTC
    timestamp such as 20261011T022721...

    The script also supports older stored records.
    """

    conditions = [
        "PartitionKey eq @device"
    ]

    parameters = {
        "device": device_id
    }

    # Inclusive starting day.
    if start_date is not None:

        start = start_of_day_utc(
            start_date
        )

        conditions.append(
            "RowKey ge @start_key"
        )

        parameters["start_key"] = (
            start.strftime("%Y%m%dT%H%M%S%fZ")
        )

    # Exclusive beginning of the day after end_date.
    if end_date is not None:

        end = start_of_day_utc(
            end_date + timedelta(days=1)
        )

        conditions.append(
            "RowKey lt @end_key"
        )

        parameters["end_key"] = (
            end.strftime("%Y%m%dT%H%M%S%fZ")
        )

    # Filter SUMMARY/EVENT/LEGACY server-side.
    #
    # A few old entities may not have RecordType.
    # They are displayed when ALL is selected.
    if record_type != "ALL":

        conditions.append(
            "RecordType eq @record_type"
        )

        parameters["record_type"] = record_type

    filter_expression = " and ".join(
        conditions
    )

    results = table_client.query_entities(
        query_filter=filter_expression,
        parameters=parameters,
    )

    records = []

    # This limit avoids downloading an unlimited
    # amount of historical data.
    for entity in results:

        records.append(
            dict(entity)
        )

        if len(records) >= limit:
            break

    return records
