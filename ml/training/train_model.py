
"""
PROJECT: IoT Equipment Condition Monitoring System
FILE: ml/training/train_model.py

PURPOSE:
    Train an Isolation Forest anomaly-detection model
    using historical Azure equipment sensor summaries.

MODEL OUTPUT:
    NORMAL  - Typical operating behavior.
    ANOMALY - Unusual operating behavior.

IMPORTANT:
    ESP32 rule-based WARNING/CRITICAL classifications
    remain separate from machine-learning predictions.

    This script reads Azure data but does not modify
    Azure Table Storage or the MQTT subscriber.
"""

import math
import sys

from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import IsolationForest


# ==========================================================
# 1. Project configuration
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AZURE_FOLDER = PROJECT_ROOT / "backend" / "azure"

sys.path.insert(0, str(AZURE_FOLDER))

from query_history import get_table_client


DEVICE_ID = "ESP32-001"

START_DATE = date(2026, 10, 10)
END_DATE = date(2026, 10, 13)

FEATURES = [
    "TemperatureAvg",
    "HumidityAvg",
    "VibrationAvg",
    "VibrationMax",
]

MODEL_FOLDER = PROJECT_ROOT / "ml" / "models"
MODEL_PATH = MODEL_FOLDER / "isolation_forest.joblib"

TRAIN_SPLIT = 0.75
RANDOM_STATE = 42


# ==========================================================
# 2. Retrieve complete historical Azure dataset
# ==========================================================

def load_azure_data():

    print("\nConnecting to Azure Table Storage...")

    table_client = get_table_client()

    start_key = START_DATE.strftime("%Y%m%d")
    end_key = (
        END_DATE + timedelta(days=1)
    ).strftime("%Y%m%d")

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

    entities = table_client.query_entities(
        query_filter=query_filter,
        parameters=parameters,
        results_per_page=500,
    )

    rows = []

    for entity in entities:

        row = {
            "RecordedAt": entity.get("RecordedAt"),
            "WorstCondition": str(
                entity.get("WorstCondition", "UNKNOWN")
            ).upper(),
        }

        for feature in FEATURES:
            row[feature] = entity.get(feature)

        rows.append(row)

    print(f"Retrieved {len(rows)} SUMMARY records")

    return pd.DataFrame(rows)


# ==========================================================
# 3. Validate and prepare training features
# ==========================================================

def prepare_data(df):

    if df.empty:
        raise RuntimeError(
            "No historical SUMMARY records were found."
        )

    df["RecordedAt"] = pd.to_datetime(
        df["RecordedAt"],
        utc=True,
        errors="coerce",
    )

    for feature in FEATURES:

        df[feature] = pd.to_numeric(
            df[feature],
            errors="coerce",
        )

    df = df.dropna(
        subset=["RecordedAt"] + FEATURES
    )

    # Exclude invalid infinity values.
    valid_rows = pd.Series(True, index=df.index)

    for feature in FEATURES:
        valid_rows &= df[feature].map(math.isfinite)

    df = df.loc[valid_rows].copy()

    # Sort before splitting to prevent future readings
    # from appearing in the training period.
    df = df.sort_values(
        "RecordedAt"
    ).reset_index(drop=True)

    print(f"Valid ML records: {len(df)}")

    return df


# ==========================================================
# 4. Train and evaluate Isolation Forest
# ==========================================================

def train_model(df):

    if len(df) < 150:
        raise RuntimeError(
            "Not enough valid historical records "
            "for this initial training experiment."
        )

    split_index = int(
        len(df) * TRAIN_SPLIT
    )

    earlier_data = df.iloc[:split_index].copy()
    test_data = df.iloc[split_index:].copy()

    # Train ONLY on earlier windows that were NORMAL
    # throughout the entire aggregation window.
    normal_training = earlier_data[
        earlier_data["WorstCondition"] == "NORMAL"
    ].copy()

    if len(normal_training) < 100:
        raise RuntimeError(
            "Insufficient NORMAL training windows."
        )

    print("\nDataset split")
    print("-" * 50)

    print(
        f"Earlier records: {len(earlier_data)}"
    )

    print(
        f"NORMAL training records: "
        f"{len(normal_training)}"
    )

    print(
        f"Unseen test records: {len(test_data)}"
    )

    print("\nTraining Isolation Forest...")

    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    model.fit(
        normal_training[FEATURES]
    )

    print("Model trained successfully!")

    # scikit-learn prediction meanings:
    #  1 = normal
    # -1 = anomaly

    test_data["MLPrediction"] = model.predict(
        test_data[FEATURES]
    )

    # Higher value = more anomalous.
    # Score > 0 indicates an anomaly for this model.
    test_data["AnomalyScore"] = (
        -model.decision_function(
            test_data[FEATURES]
        )
    )

    test_data["MLStatus"] = test_data[
        "MLPrediction"
    ].map({
        1: "NORMAL",
        -1: "ANOMALY",
    })

    return model, normal_training, test_data


# ==========================================================
# 5. Display evaluation results
# ==========================================================

def evaluate_model(test_data):

    print("\n" + "=" * 55)
    print("ISOLATION FOREST EVALUATION")
    print("=" * 55)

    print("\nML prediction distribution:")

    predictions = Counter(
        test_data["MLStatus"]
    )

    for status, count in sorted(predictions.items()):
        print(f"  {status}: {count}")

    print("\nComparison with ESP32 rule labels:")
    print(
        "(Rule labels are comparison references, "
        "not independently verified fault labels.)"
    )

    for condition in (
        "NORMAL",
        "WARNING",
        "CRITICAL",
    ):

        subset = test_data[
            test_data["WorstCondition"] == condition
        ]

        total = len(subset)

        anomalies = int(
            (subset["MLStatus"] == "ANOMALY").sum()
        )

        rate = (
            (anomalies / total) * 100
            if total > 0
            else None
        )

        rate_text = (
            f"{rate:.1f}%"
            if rate is not None
            else "N/A"
        )

        print(
            f"  {condition}: "
            f"{total} records, "
            f"{anomalies} predicted ANOMALY, "
            f"rate={rate_text}"
        )

    print("\nSample ML predictions:")

    print(
        test_data[
            [
                "RecordedAt",
                "WorstCondition",
                "VibrationAvg",
                "VibrationMax",
                "MLStatus",
                "AnomalyScore",
            ]
        ].head(10).to_string(index=False)
    )


# ==========================================================
# 6. Save trained model
# ==========================================================

def save_model(model, training_data):

    MODEL_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Store the model and feature ordering together.
    # Predictions must use the exact same features.
    bundle = {
        "model": model,
        "features": FEATURES,
        "device_id": DEVICE_ID,
        "training_records": len(training_data),
        "algorithm": "IsolationForest",
        "score_definition": (
            "-decision_function; "
            "greater than zero means ANOMALY"
        ),
    }

    joblib.dump(
        bundle,
        MODEL_PATH,
    )

    print("\nSaved model:")
    print(MODEL_PATH)


# ==========================================================
# 7. Run training workflow
# ==========================================================

def main():

    print("\nIoT Equipment AI/ML Model Training")
    print("=" * 55)

    df = load_azure_data()

    df = prepare_data(df)

    model, training_data, test_data = train_model(df)

    evaluate_model(test_data)

    save_model(model, training_data)

    print("\nTraining workflow completed!")
    print("Azure records were not modified.")
    print("MQTT subscriber was not modified.")
    print("Grafana dashboard was not modified.")


if __name__ == "__main__":
    main()
