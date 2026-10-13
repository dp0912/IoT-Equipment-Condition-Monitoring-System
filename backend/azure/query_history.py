
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

EXAMPLE:
    python backend/azure/query_history.py --type SUMMARY

SECURITY:
    Azure credentials are loaded from the private .env file.
    Credentials are never displayed.
"""

# ============================================================
# STEP 1: Import dependencies.
# ============================================================

import argparse
import os
import sys

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from azure.core.exceptions import AzureError
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


# ============================================================
# STEP 6: Display records clearly.
# ============================================================

def display_summary(record):
    """
    Print one 30-second aggregated record.
    """

    print(
        f"  Samples: {record.get('SampleCount', '-')}"
        f" | Window: {record.get('WindowSeconds', '-')}s"
    )

    print(
        f"  Temperature avg: "
        f"{record.get('TemperatureAvg', '-')} C"
        f" | Min: {record.get('TemperatureMin', '-')}"
        f" | Max: {record.get('TemperatureMax', '-')}"
    )

    print(
        f"  Humidity avg: "
        f"{record.get('HumidityAvg', '-')}%"
        f" | Min: {record.get('HumidityMin', '-')}"
        f" | Max: {record.get('HumidityMax', '-')}"
    )

    print(
        f"  Vibration avg: "
        f"{record.get('VibrationAvg', '-')}"
        f" | Min: {record.get('VibrationMin', '-')}"
        f" | Max: {record.get('VibrationMax', '-')}"
    )

    print(
        f"  Latest condition: "
        f"{record.get('Condition', '-')}"
        f" | Worst: {record.get('WorstCondition', '-')}"
    )


def display_event(record):
    """
    Print one condition-change event.
    """

    print(
        f"  Event: {record.get('EventType', '-')}"
    )

    print(
        f"  Transition: "
        f"{record.get('PreviousCondition', '-')}"
        f" -> {record.get('Condition', '-')}"
    )

    print(
        f"  Temperature: {record.get('Temperature', '-')}"
        f" C | Humidity: {record.get('Humidity', '-')}%"
        f" | Vibration: {record.get('Vibration', '-')}"
    )


def display_legacy(record):
    """
    Print an earlier individual telemetry record.
    """

    print(
        f"  Temperature: {record.get('Temperature', '-')}"
        f" C | Humidity: {record.get('Humidity', '-')}%"
        f" | Vibration: {record.get('Vibration', '-')}"
    )

    print(
        f"  Condition: {record.get('Condition', '-')}"
    )


def display_records(records):
    """
    Display retrieved Azure entities.
    """

    if not records:
        print(
            "\nNo matching historical records found."
        )
        return

    print(
        f"\nSuccessfully retrieved "
        f"{len(records)} historical record(s).\n"
    )

    for number, record in enumerate(
        records,
        start=1,
    ):

        record_type = record.get(
            "RecordType",
            "LEGACY"
        )

        print("=" * 65)

        print(
            f"Record {number} | {record_type}"
        )

        print(
            f"Device: {record.get('PartitionKey', '-')}"
        )

        print(
            f"Recorded at (UTC): "
            f"{record.get('RecordedAt', '-')}"
        )

        if record_type == "SUMMARY":
            display_summary(record)

        elif record_type == "EVENT":
            display_event(record)

        else:
            display_legacy(record)

    print("=" * 65)


# ============================================================
# STEP 7: Command-line interface.
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Retrieve ESP32 historical records "
            "from Azure Table Storage."
        )
    )

    parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE,
        help="Device identifier (default: ESP32-001)"
    )

    parser.add_argument(
        "--type",
        choices=RECORD_TYPES,
        default="SUMMARY",
        help="Record type (default: SUMMARY)"
    )

    parser.add_argument(
        "--from-date",
        type=parse_date,
        default=None,
        help="Start date in UTC (YYYY-MM-DD)"
    )

    parser.add_argument(
        "--to-date",
        type=parse_date,
        default=None,
        help="End date in UTC (YYYY-MM-DD)"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum records to retrieve (default: 20)"
    )

    args = parser.parse_args()

    if args.limit < 1 or args.limit > 500:

        parser.error(
            "--limit must be between 1 and 500."
        )

    if (
        args.from_date is not None
        and args.to_date is not None
        and args.from_date > args.to_date
    ):

        parser.error(
            "--from-date must be on or before --to-date."
        )

    print("\nAzure Historical Telemetry Query")
    print("-" * 45)

    print(f"Table: {TABLE_NAME}")
    print(f"Device: {args.device}")
    print(f"Record type: {args.type}")

    try:

        table_client = get_table_client()

        records = query_history(
            table_client=table_client,
            device_id=args.device,
            record_type=args.type,
            start_date=args.from_date,
            end_date=args.to_date,
            limit=args.limit,
        )

        display_records(records)

    except (AzureError, RuntimeError, OSError) as error:

        print(
            "\nAzure historical query failed: "
            f"{type(error).__name__}"
        )

        print(
            "Check your Azure connection, .env settings, "
            "and table permissions."
        )

        sys.exit(1)


# ============================================================
# STEP 8: Run the program.
# ============================================================

if __name__ == "__main__":
    main()
