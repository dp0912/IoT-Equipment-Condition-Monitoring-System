
"""
IoT Equipment Condition Monitoring System
FILE: ml/training/inspect_data.py

PURPOSE:
    Inspect ALL historical SUMMARY records stored in Azure.

    - No 500-record limit
    - Automatic Azure SDK pagination
    - Count Condition and WorstCondition
    - Validate ML sensor features
    - Show per-day record totals

    This script is READ-ONLY.
"""

import math
import sys

from collections import Counter
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AZURE_FOLDER = PROJECT_ROOT / "backend" / "azure"

sys.path.insert(0, str(AZURE_FOLDER))

from query_history import get_table_client


DEVICE_ID = "ESP32-001"

START_DATE = date(2026, 10, 10)
END_DATE = date(2026, 10, 13)


def main():

    print("\nAI/ML - Complete Historical Data Inspection")
    print("=" * 55)

    print(f"Device: {DEVICE_ID}")
    print(f"Date range: {START_DATE} to {END_DATE}")
    print("Record type: SUMMARY")
    print("Record limit: None (retrieve all matching records)")

    table_client = get_table_client()

    start_key = START_DATE.strftime("%Y%m%d")

    end_exclusive = END_DATE + timedelta(days=1)
    end_key = end_exclusive.strftime("%Y%m%d")

    query_filter = (
        "PartitionKey eq @device "
        "and RowKey ge @start "
        "and RowKey lt @end "
        "and RecordType eq @type"
    )

    parameters = {
        "device": DEVICE_ID,
        "start": start_key,
        "end": end_key,
        "type": "SUMMARY",
    }

    records = table_client.query_entities(
        query_filter=query_filter,
        parameters=parameters,
        results_per_page=500,
    )

    total_records = 0
    usable_records = 0

    conditions = Counter()
    worst_conditions = Counter()
    daily_counts = Counter()

    samples = []

    for record in records:

        total_records += 1

        condition = str(
            record.get("Condition") or "UNKNOWN"
        ).upper()

        worst_condition = str(
            record.get("WorstCondition") or "UNKNOWN"
        ).upper()

        conditions[condition] += 1
        worst_conditions[worst_condition] += 1

        recorded_at = str(
            record.get("RecordedAt") or ""
        )

        day = recorded_at[:10] or "UNKNOWN"
        daily_counts[day] += 1

        values = (
            record.get("TemperatureAvg"),
            record.get("HumidityAvg"),
            record.get("VibrationAvg"),
        )

        valid = all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in values
        )

        if valid:
            usable_records += 1

            if len(samples) < 5:
                samples.append(record)

        if total_records % 500 == 0:
            print(
                f"Processed {total_records} records..."
            )

    print("\n" + "=" * 55)
    print("COMPLETE DATASET RESULTS")
    print("=" * 55)

    print(f"Total SUMMARY records: {total_records}")
    print(f"Usable ML records: {usable_records}")
    print(
        f"Unusable records: "
        f"{total_records - usable_records}"
    )

    print("\nLatest Condition distribution:")

    for condition, count in sorted(conditions.items()):
        print(f"  {condition}: {count}")

    print("\nWorst Condition distribution:")

    for condition, count in sorted(
        worst_conditions.items()
    ):
        print(f"  {condition}: {count}")

    print("\nRecords by date:")

    for day, count in sorted(daily_counts.items()):
        print(f"  {day}: {count}")

    print("\nFirst 5 usable sensor records:")

    for record in samples:

        print(
            f"  {record.get('RecordedAt')} | "
            f"Temp={record.get('TemperatureAvg')} | "
            f"Humidity={record.get('HumidityAvg')} | "
            f"VibrationAvg={record.get('VibrationAvg')} | "
            f"VibrationMax={record.get('VibrationMax')} | "
            f"Condition={record.get('Condition')} | "
            f"Worst={record.get('WorstCondition')}"
        )

    print("\nInspection completed successfully.")
    print("No Azure records were modified.")


if __name__ == "__main__":
    main()
