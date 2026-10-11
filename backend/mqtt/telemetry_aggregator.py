
"""
IoT Equipment Condition Monitoring System
FILE: backend/mqtt/telemetry_aggregator.py

PURPOSE:
    Collect ESP32 sensor readings and calculate summary
    statistics for a configurable time window.

    For temperature, humidity, and vibration, calculate:
        - Average
        - Minimum
        - Maximum
        - Latest

    This module does NOT connect to Azure or MQTT.
    It can be tested independently before integration.
"""

from datetime import datetime, timezone
from statistics import mean


class TelemetryAggregator:
    """
    Collects readings for one equipment device.

    A completed window is returned as a dictionary.
    The caller is responsible for storing it in Azure.
    """

    def __init__(self, device_id, interval_seconds=30):
        # Device whose readings are being summarized.
        self.device_id = device_id

        # Duration of each aggregation window.
        self.interval_seconds = interval_seconds

        # Start with an empty collection.
        self.readings = []
        self.window_start = None

    def add_reading(self, telemetry, received_at):
        """
        Add one valid ESP32 telemetry message.

        Args:
            telemetry: Dictionary received from MQTT.
            received_at: Monotonic timestamp in seconds.

        Returns:
            A completed summary when the current window
            has reached its duration, otherwise None.
        """

        # The first reading starts the aggregation window.
        if self.window_start is None:
            self.window_start = received_at

        # If 30 seconds have elapsed, finish the previous
        # window before adding the new reading.
        completed_summary = None

        if (
            received_at - self.window_start
            >= self.interval_seconds
        ):
            # Summarize only the readings actually received
            # during the previous window.
            completed_summary = self.build_summary()

            # Start a new window with the incoming reading.
            self.readings = []
            self.window_start = received_at

        # Store a copy to avoid accidental modification.
        self.readings.append(dict(telemetry))

        return completed_summary

    def build_summary(self):
        """
        Calculate statistics for the current readings.

        Returns None when the window has no readings.
        """

        if not self.readings:
            return None

        # Last received reading provides current device state.
        latest = self.readings[-1]

        # Include only valid numerical measurements.
        # Sensor validity flags prevent invalid measurements
        # from influencing averages.
        measurements = {}

        for field in ("temperature", "humidity", "vibration"):

            # Associate each sensor with its validity flag.
            validity_flag = (
                "vibration_valid"
                if field == "vibration"
                else "dht_valid"
            )

            values = []

            for reading in self.readings:

                # Missing validity flags are treated as valid
                # for compatibility with older sample records.
                if reading.get(validity_flag, True) is False:
                    continue

                value = reading.get(field)

                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    import math

                    if math.isfinite(value):
                        values.append(float(value))

            # No valid samples means no statistics for this
            # sensor, rather than inventing a zero value.
            if values:
                measurements[field] = {
                    "avg": round(mean(values), 4),
                    "min": round(min(values), 4),
                    "max": round(max(values), 4),
                    "latest": round(values[-1], 4),
                    "count": len(values),
                }
            else:
                measurements[field] = {
                    "avg": None,
                    "min": None,
                    "max": None,
                    "latest": None,
                    "count": 0,
                }

        # Preserve the most severe condition observed.
        # This is important because the latest condition
        # may have recovered to NORMAL.
        severity = {
            "NORMAL": 0,
            "WARNING": 1,
            "CRITICAL": 2,
        }

        worst_condition = max(
            (
                str(item.get("condition", "NORMAL")).upper()
                for item in self.readings
            ),
            key=lambda condition: severity.get(condition, 0),
        )

        return {
            "record_type": "SUMMARY",
            "device_id": self.device_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "window_seconds": self.interval_seconds,
            "sample_count": len(self.readings),
            "latest_condition": latest.get("condition"),
            "worst_condition": worst_condition,
            "temperature": measurements["temperature"],
            "humidity": measurements["humidity"],
            "vibration": measurements["vibration"],
            "latest_telemetry": latest,
        }
