
# IoT-Based Equipment Condition Monitoring System with AI/ML

**Real-Time Equipment Monitoring | ESP32 | MQTT | Python | Azure | Grafana | Machine Learning**

**Course:** SOFE 4610U – Design & Analysis of IoT  
**University:** Ontario Tech University  
**Term:** Fall 2026  
**Status:** Functional Prototype – Final Development and Testing in Progress

## Overview

An end-to-end IoT system designed to monitor equipment health using temperature, humidity, and vibration sensors.

An **ESP32** collects sensor readings and classifies equipment conditions as **NORMAL, WARNING, or CRITICAL** using configurable thresholds. Data is transmitted through **MQTT** to a Python backend for validation, aggregation, cloud storage, and machine-learning anomaly detection.

**Microsoft Azure Table Storage** maintains historical equipment records, while **Grafana** provides real-time and historical dashboards.

A trained **Isolation Forest** model analyzes sensor patterns and identifies unusual behavior as **NORMAL or ANOMALY**.

## System Architecture

```text
              DC Motor / Fan
                    |
          ESP32 + Sensors
       (DHT11 + MPU6500)
                    |
          Local Processing
     (Thresholds, LEDs, LCD,
       Buzzer, Motor Control)
                    |
                Wi-Fi
                    |
             MQTT Broker
              (Mosquitto)
                    |
          +---------+---------+
          |                   |
     Grafana Live        Python Backend
       Monitoring              |
                        +------+------+
                        |             |
                   Validation    30s Aggregation
                                      |
                              +-------+-------+
                              |               |
                         Azure Table     Isolation Forest
                           Storage             ML
                              |               |
                         Flask API        MQTT /ml
                              |               |
                         Grafana           Grafana
                         History           AI/ML
```

## Technology Stack

| Layer | Technologies |
|---|---|
| Hardware | ESP32, DHT11, MPU6500, DC Motor, LCD, LEDs, Buzzer, IR Remote |
| Firmware | C++, Arduino Framework |
| Communication | Wi-Fi, MQTT, Mosquitto |
| Backend | Python, Paho MQTT, Flask |
| Cloud | Microsoft Azure Table Storage, Azure Monitor |
| Machine Learning | scikit-learn, Isolation Forest, pandas, joblib |
| Visualization | Grafana, MQTT Datasource, Infinity, Business Text |
| Development | VS Code, Arduino IDE, Git, GitHub |

## Implemented Features

- **Sensor Monitoring:** Continuous temperature, humidity, and vibration measurements.
- **Condition Classification:** Configurable NORMAL, WARNING, and CRITICAL thresholds.
- **Local Control:** LCD, LEDs, buzzer, IR remote, motor control, and software interlocks.
- **MQTT Communication:** ESP32 telemetry published approximately every 2 seconds.
- **Python Backend:** Telemetry validation, condition-change detection, and connectivity monitoring.
- **Data Aggregation:** Statistical summaries generated approximately every 30 seconds.
- **Azure Storage:** Persistent SUMMARY and EVENT records.
- **Historical API:** Flask REST endpoints for retrieving Azure equipment history.
- **Grafana Dashboard:** Live telemetry, equipment alerts, connectivity, and historical trends.
- **Machine Learning:** Trained Isolation Forest model with real-time NORMAL/ANOMALY predictions.
- **AI/ML Visualization:** Live anomaly status and score displayed in Grafana.

## Grafana Dashboard

![Equipment Monitoring Dashboard](dashboard/screenshot/live-dashboard.png)

The dashboard includes live sensor readings, equipment conditions, historical Azure trends, equipment alerts, and AI/ML anomaly detection.

**Dashboard Configuration:** [Grafana JSON](dashboard/grafana/iot-equipment-live-dashboard.json)

> The screenshot may represent an earlier dashboard revision. The exported JSON contains the updated dashboard configuration.

## Machine Learning

The system uses an **Isolation Forest** model trained on historical Azure sensor summaries.

**Input Features:**
- Average temperature
- Average humidity
- Average vibration
- Maximum vibration

**Model Configuration:**

| Parameter | Value |
|---|---|
| Algorithm | Isolation Forest |
| Estimators | 200 |
| Contamination | 0.05 |
| Output | NORMAL / ANOMALY |
| Inference Interval | Approximately 30 seconds |

The model operates independently of ESP32 threshold classification.

**Rule-Based Detection:** NORMAL / WARNING / CRITICAL  
**ML Detection:** NORMAL / ANOMALY

A positive anomaly score indicates anomalous behavior under the current model's decision rule; the score is not a failure probability.

**Model:** [`ml/models/isolation_forest.joblib`](ml/models/isolation_forest.joblib)

## Azure Integration

**Storage Account:** `stiotequipmentmonitor01`  
**Table:** `EquipmentTelemetry`

| Record | Purpose |
|---|---|
| SUMMARY | Aggregated sensor measurements |
| EVENT | Equipment condition transitions |

The Flask History API retrieves Azure records for Grafana historical visualization.

**API Endpoints:**

```text
GET /api/health
GET /api/history/summary
GET /api/history/events
```

**Local API:** `http://127.0.0.1:5001`

Azure Monitor Log Analytics integration is also available as an optional backend feature.

## Running the Project

### 1. Clone and set up Python

```bash
git clone https://github.com/dp0912/IoT-Equipment-Condition-Monitoring-System.git
cd IoT-Equipment-Condition-Monitoring-System

python3 -m venv .venv
source .venv/bin/activate

pip install paho-mqtt python-dotenv azure-data-tables \
azure-identity azure-monitor-ingestion flask \
scikit-learn pandas numpy joblib
```

### 2. Configure environment variables

Create a private `.env` file:

```dotenv
MQTT_HOST=YOUR_BROKER_IP
MQTT_PASSWORD=YOUR_MQTT_PASSWORD

AZURE_STORAGE_CONNECTION_STRING=YOUR_CONNECTION_STRING
AZURE_TABLE_NAME=EquipmentTelemetry

AZURE_LOG_ANALYTICS_ENABLED=false
```

Configure the ESP32 Wi-Fi and MQTT credentials separately using the local `secrets.h` file.

**Never commit credentials, `.env`, or `secrets.h` to GitHub.**

### 3. Start services

Start Mosquitto and Grafana:

```bash
brew services start mosquitto
brew services start grafana
```

Start the Python subscriber:

```bash
python backend/mqtt/subscriber.py
```

In another terminal, activate the virtual environment and start the historical API:

```bash
source .venv/bin/activate
python backend/azure/history_api.py
```

Power the ESP32 with the monitoring firmware installed.

Open Grafana at **http://localhost:3000**.

The MQTT, Infinity, and Business Text plugins and corresponding datasources must be configured.

### 4. Stop services

Stop the Python processes using `Ctrl+C`, then run:

```bash
brew services stop grafana
brew services stop mosquitto
```

## Repository Structure

```text
IoT-Equipment-Condition-Monitoring-System/
├── firmware/
│   └── esp32/equipment_monitor/
├── backend/
│   ├── mqtt/
│   │   ├── subscriber.py
│   │   └── telemetry_aggregator.py
│   └── azure/
│       ├── storage.py
│       ├── query_history.py
│       ├── history_api.py
│       └── log_analytics.py
├── ml/
│   ├── training/
│   ├── inference/
│   └── models/isolation_forest.joblib
├── dashboard/
│   ├── grafana/
│   └── screenshot/
├── hardware/
├── docs/
├── .gitignore
└── README.md
```

## Project Completion Status

| Component | Status |
|---|---|
| ESP32 Sensors and Classification | ✅ Working |
| MQTT Communication | ✅ Working |
| Python Backend and Aggregation | ✅ Working |
| Azure SUMMARY / EVENT Storage | ✅ Working |
| Historical Retrieval API | ✅ Working |
| Grafana Live and Historical Dashboard | ✅ Working |
| Isolation Forest Training and Inference | ✅ Working |
| Live Grafana AI/ML Panel | ✅ Working |
| Historical ML Prediction Storage | ⏳ Pending |
| Email and SMS Notifications | ⏳ Pending |
| Offline / Reconnection Reliability Testing | ⏳ Final Validation |
| Final Testing Evidence and Documentation | ⏳ In Progress |

## Remaining Work

1. **Historical ML Storage:** Persist anomaly predictions and scores in Azure.
2. **Remote Notifications:** Implement email, critical SMS, recovery, and offline-device alerts.
3. **Reliability Testing:** Verify MQTT reconnections, Azure failures, invalid sensor readings, and service recovery.
4. **Documentation:** Update dashboard screenshots and finalize test evidence.

## Important Notes

This is an academic proof-of-concept, not a certified industrial protection system. The ESP32 software interlocks are not safety-rated, MQTT/TLS is not yet implemented, and ML predictions are not verified equipment-failure probabilities.

## Project Information

**Project:** IoT-Based Configurable Multi-Sensor Equipment Condition Monitoring System with AI/ML Integration  
**Institution:** Ontario Tech University  
**Course:** SOFE 4610U – Design & Analysis of IoT  
**Term:** Fall 2026

**Repository:** https://github.com/dp0912/IoT-Equipment-Condition-Monitoring-System

---

Developed as an academic IoT project demonstrating **embedded systems, MQTT networking, Python backend processing, Azure cloud integration, Grafana visualization, and machine-learning anomaly detection**.
