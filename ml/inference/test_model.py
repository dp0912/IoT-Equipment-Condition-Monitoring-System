
"""
IoT Equipment Condition Monitoring System
FILE: ml/inference/test_model.py

PURPOSE:
    Test the trained Isolation Forest model locally.

    This script does not connect to MQTT, Azure, or Grafana.
"""

from pathlib import Path

import joblib
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    PROJECT_ROOT
    / "ml"
    / "models"
    / "isolation_forest.joblib"
)


def main():

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Trained model not found: {MODEL_PATH}"
        )

    bundle = joblib.load(MODEL_PATH)

    model = bundle["model"]
    features = bundle["features"]

    print("\nIsolation Forest - Local Prediction Test")
    print("=" * 55)
    print("Model loaded successfully")
    print(f"Features: {features}")

    # Illustrative sensor measurements.
    # These are test inputs, NOT actual live readings.
    test_readings = [
        {
            "TemperatureAvg": 26.2,
            "HumidityAvg": 49.0,
            "VibrationAvg": 0.0734,
            "VibrationMax": 0.244,
        },
        {
            "TemperatureAvg": 26.2,
            "HumidityAvg": 49.0,
            "VibrationAvg": 0.0734,
            "VibrationMax": 0.244,
        },
        {
            "TemperatureAvg": 45.0,
            "HumidityAvg": 80.0,
            "VibrationAvg": 2.5,
            "VibrationMax": 4.5,
        },
    ]

    df = pd.DataFrame(
        test_readings,
        columns=features,
    )

    predictions = model.predict(df)

    scores = -model.decision_function(df)

    for index, (prediction, score) in enumerate(
        zip(predictions, scores),
        start=1,
    ):

        status = (
            "NORMAL"
            if prediction == 1
            else "ANOMALY"
        )

        print(f"\nTest {index}")
        print(f"  Input: {test_readings[index - 1]}")
        print(f"  ML Prediction: {status}")
        print(f"  Anomaly Score: {score:.6f}")

    print("\nTest completed.")


if __name__ == "__main__":
    main()
