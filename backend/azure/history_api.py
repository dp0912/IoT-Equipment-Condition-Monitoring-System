
"""
PROJECT: IoT Equipment Condition Monitoring System
FILE: backend/azure/history_api.py

PURPOSE:
    Provide historical Azure Table Storage data to
    the local Grafana Infinity datasource.

ENDPOINTS:
    /api/health
    /api/history/summary
    /api/history/events

SECURITY:
    Runs on localhost only.
    Azure history routes remain read-only.
    Authorized ESP32 control routes share this same Flask server and process;
    there is no additional web server or startup command.
"""

from datetime import date, datetime, timezone
from pathlib import Path
import sys
from flask import jsonify, request

# Running python backend/azure/history_api.py puts azure/ in sys.path, not the
# repository root; add the root so the sibling backend.api module can be found.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from query_history import get_table_client, query_history
from backend.api import control_api

# One Flask server on 127.0.0.1:5001 owns both Azure history and secured
# Grafana controls. There is deliberately no control web service on port 5002.
app = control_api.app


# --------------------------------------------------
# Convert Azure records into Grafana-friendly JSON.
# --------------------------------------------------

def format_record(record, record_type):

    result = {
        "time": record.get("RecordedAt"),
        "device_id": record.get("PartitionKey"),
        "condition": record.get("Condition", ""),
    }

    if record_type == "SUMMARY":

        result.update({
            "temperature": record.get("TemperatureAvg"),
            "humidity": record.get("HumidityAvg"),
            "vibration": record.get("VibrationAvg"),
            "temperature_min": record.get("TemperatureMin"),
            "temperature_max": record.get("TemperatureMax"),
            "humidity_min": record.get("HumidityMin"),
            "humidity_max": record.get("HumidityMax"),
            "vibration_min": record.get("VibrationMin"),
            "vibration_max": record.get("VibrationMax"),
            "sample_count": record.get("SampleCount"),
            "worst_condition": record.get("WorstCondition"),
        })

    elif record_type == "EVENT":

        result.update({
            "event_type": record.get("EventType"),
            "previous_condition": record.get(
                "PreviousCondition"
            ),
            "temperature": record.get("Temperature"),
            "humidity": record.get("Humidity"),
            "vibration": record.get("Vibration"),
        })

    return result


# --------------------------------------------------
# Health check.
# --------------------------------------------------

# --------------------------------------------------
# Shared Azure history retrieval.
# --------------------------------------------------

def retrieve_records(record_type):

    device_id = request.args.get(
        "device", "ESP32-001"
    )

    start_text = request.args.get("from")
    end_text = request.args.get("to")

    try:
        start_date = (
            date.fromisoformat(start_text)
            if start_text else None
        )

        end_date = (
            date.fromisoformat(end_text)
            if end_text else None
        )

        limit = int(
            request.args.get("limit", "25000")
        )

        if not 1 <= limit <= 25000:
            raise ValueError("Invalid limit")

        if (
            start_date is not None
            and end_date is not None
            and start_date > end_date
        ):
            raise ValueError("Invalid date range")

    except ValueError:

        return jsonify({
            "error": (
                "Use YYYY-MM-DD dates, a valid date "
                "range, and a limit between 1 and 25000."
            )
        }), 400

    try:

        table_client = get_table_client()

        records = query_history(
            table_client=table_client,
            device_id=device_id,
            record_type=record_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        formatted = [
            format_record(record, record_type)
            for record in records
        ]

        return jsonify(formatted)

    except Exception as error:

        # Log the error type locally.
        # Do not expose Azure credentials to HTTP clients.
        app.logger.error(
            "Azure history request failed: %s",
            type(error).__name__
        )

        return jsonify({
            "error": "Unable to retrieve Azure history"
        }), 500


# --------------------------------------------------
# Historical 30-second sensor summaries.
# --------------------------------------------------

@app.route("/api/history/summary")
def historical_summaries():

    return retrieve_records("SUMMARY")


# --------------------------------------------------
# Historical equipment condition events.
# --------------------------------------------------

@app.route("/api/history/events")
def historical_events():

    return retrieve_records("EVENT")


# --------------------------------------------------
# Start the local API server.
# --------------------------------------------------

if __name__ == "__main__":

    print("--------------------------------------")
    print("IoT Historical Azure Data API")
    print("Host: 127.0.0.1")
    print("Port: 5001")
    print("Mode: Azure history + authorized Grafana equipment controls")
    print("--------------------------------------")

    # Control MQTT starts in-process; invalid/missing control secrets fail closed
    # and do not stop the existing historical dashboard from working.
    control_api.start_control_mqtt()
    try:
        app.run(
            host="127.0.0.1",
            port=5001,
            debug=False,
            threaded=True,
        )
    finally:
        control_api.stop_control_mqtt()
