
"""
IoT Equipment Condition Monitoring System
FILE: ml/inference/predict_anomaly.py

PURPOSE:
    Load the trained Isolation Forest model and make
    predictions using completed 30-second sensor summaries.

OUTPUT:
    NORMAL or ANOMALY, plus anomaly decision score.

    This module does not connect to MQTT or Azure.
"""

import math
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


class AnomalyDetector:

    def __init__(self, model_path=MODEL_PATH):

        self.model_path = Path(model_path)

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Trained model not found: {self.model_path}"
            )

        # Load only our own trusted, locally trained model.
        bundle = joblib.load(self.model_path)

        self.model = bundle["model"]
        self.features = bundle["features"]

        print("Isolation Forest model loaded")
        print(f"Model features: {self.features}")

    def predict(self, summary):
        """
        Predict using a TelemetryAggregator summary.

        Returns:
            status: NORMAL or ANOMALY
            anomaly_score: positive means anomalous
            features: numerical values used in prediction

        Returns None if required measurements are missing.
        """

        try:
            measurements = {
                "TemperatureAvg": summary["temperature"]["avg"],
                "HumidityAvg": summary["humidity"]["avg"],
                "VibrationAvg": summary["vibration"]["avg"],
                "VibrationMax": summary["vibration"]["max"],
            }

        except (KeyError, TypeError):
            return None

        for value in measurements.values():

            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                return None

        # Preserve the feature ordering used during training.
        input_data = pd.DataFrame(
            [measurements],
            columns=self.features,
        )

        prediction = int(
            self.model.predict(input_data)[0]
        )

        anomaly_score = float(
            -self.model.decision_function(input_data)[0]
        )

        status = (
            "ANOMALY"
            if prediction == -1
            else "NORMAL"
        )

        return {
            "device_id": summary["device_id"],
            "recorded_at": summary["recorded_at"],
            "status": status,
            "anomaly_score": round(anomaly_score, 6),
            "model": "IsolationForest",
            "features": measurements,
        }


if __name__ == "__main__":

    detector = AnomalyDetector()

    # Synthetic test summary using typical sensor values.
    test_summary = {
        "device_id": "ESP32-001",
        "recorded_at": "2026-10-13T18:00:00+00:00",
        "temperature": {"avg": 26.2},
        "humidity": {"avg": 49.0},
        "vibration": {
            "avg": 0.0734,
            "max": 0.244,
        },
    }

    result = detector.predict(test_summary)

    print("\nML prediction result:")
    print(result)
