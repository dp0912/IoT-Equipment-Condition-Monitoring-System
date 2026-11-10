# IoT Equipment Condition Monitoring System
## Technical Project Guide · SOFE 4610U · 4 November 2026

**Repository:** https://github.com/dp0912/IoT-Equipment-Condition-Monitoring-System  
**Implementation:** ESP32-WROOM-32 · DHT11 · MPU6050/MPU6500 · MQTT/Mosquitto · Python · Azure Table Storage · Grafana · Isolation Forest · Gmail SMTP  
**Status:** Working prototype under final monitoring-only integration validation. This document describes source-code functionality; it does not certify all live hardware and cloud paths.

## 1. Purpose and boundaries

This project monitors ambient temperature, relative humidity, and acceleration-derived vibration for an operator-selected equipment profile. The ESP32 performs local threshold assessment and drives green, yellow and red status LEDs and an audible critical alarm. It publishes telemetry over authenticated MQTT to a Mosquitto broker on a Mac. A Python subscriber performs validation, aggregation, event processing, Azure storage, ML inference and email notifications. Grafana displays live data and cloud history. An authenticated Flask control service forwards authorized threshold and profile updates to the ESP32.

**Important scope:** The eight equipment types are selectable **simulation/monitoring profiles** for one physical ESP32, not eight monitored machines. The current build has **no physical motor, motor driver, LCD, IR remote or sound sensor**. There is no machine start/stop function or industrial emergency-stop function. Ambient sensors are not direct measurements of internal bearing or winding temperatures.

## 2. Architecture and component responsibilities

**Edge:** DHT11 at GPIO27; MPU I²C at SDA21/SCL22; green/yellow/red LEDs at GPIO25/26/33; active buzzer/driver at GPIO23; momentary acknowledge button GPIO13→GND. The firmware samples sensors, calculates vibration RMS, applies profile-specific threshold limits, emits local indicators, remembers configuration using ESP32 Preferences and accepts MQTT commands.

**Local messaging and processing:** Mosquitto MQTT broker on the trusted local network, normally TCP 1883. Grafana's MQTT datasource receives live streams. `backend/mqtt/subscriber.py` accepts and validates telemetry, identifies condition changes and connectivity, builds approximately 30-second summaries, calls ML inference and queues cloud and email work.

**Cloud/history:** `backend/azure/storage.py` writes `SUMMARY` and `EVENT` entities to Azure Table Storage. `backend/azure/history_api.py` supplies local JSON history endpoints, while `backend/api/control_api.py` attaches authenticated operator-control endpoints to that same Flask application on `127.0.0.1:5001`.

**Visualization:** Local Grafana on `http://localhost:3000`; MQTT panels are live, Infinity/HTTP panels fetch the stored Azure history from Flask; Business Forms and Business Text/Dynamic Text are used for operator interactions and displays.

**Notifications:** `backend/notifications/email_notifier.py` delivers best-effort Gmail SMTP notifications on condition and connectivity transitions, with equipment-profile identification in WARNING, CRITICAL and RECOVERY messages.

**Reference images:** `docs/images/system-architecture.png` and `docs/images/grafana-dashboard.png` in the repository are illustrative, not new empirical screenshots. Refer to the current implementation for actual behavior.

## 3. Equipment profiles and threshold logic

The firmware exposes eight profiles: `MOTOR`, `PUMP`, `COMPRESSOR`, `FAN`, `CONDENSER`, `HEAT_EXCHANGER`, `AHU`, and `CHILLER`. One profile is active at a time. Switching profiles loads that profile's demonstration thresholds; subsequent edits are stored locally. Profile names identify the monitoring context and do not control any powered machine.

For temperature and humidity, limits have four ordered values: **critical low < warning low < warning high < critical high**. Values outside warning limits indicate WARNING, and outside critical limits indicate CRITICAL. For vibration the firmware uses **warning high** and **critical high** only; `low_enabled=false` is descriptive and low vibration is not independently an alarm. Highest detected severity wins. Invalid or disconnected sensors are tracked separately using health flags; consult firmware for exact resulting condition and faults. All included values are illustrative demo settings, **not certified machinery operating limits**.

**Local response:** NORMAL = green LED; WARNING = yellow LED; CRITICAL = red LED and repeating buzzer, configured at **200 ms ON / 800 ms OFF**. GPIO13 acknowledges/silences the audible alert without falsely changing the equipment condition. The alarm can become active on a new critical incident. Acknowledgement is not repair or recovery.

## 4. MQTT data contract

The current device is `ESP32-001`; topics use prefix `equipment/ESP32-001/`.

| Topic suffix | Source → consumer | Meaning |
|---|---|---|
| `telemetry` | ESP32 → Python/Grafana | Live readings, profile and condition |
| `status` | ESP32 → consumers | Firmware connection/status |
| `config` | ESP32 → Flask/Grafana | Retained confirmed profile and thresholds |
| `sensor_health` | ESP32 → Flask/Grafana | Sensor validity information |
| `control_status` | ESP32 → Flask/Grafana | Condition and acknowledged alarm state |
| `commands` | Flask → ESP32 | Authorized updates and acknowledgements requests |
| `command_ack` | ESP32 → Flask | Applied/rejected result correlated by command ID |
| `alerts` | Python → Grafana | Equipment condition transitions |
| `connectivity` | Python → Grafana | Backend-derived ONLINE/OFFLINE information |
| `ml` | Python → Grafana | Isolation Forest result and anomaly score |

An example telemetry payload (illustrative, not a measured capture):

```json
{"device_id":"ESP32-001","profile":"MOTOR","temperature":24.8,"humidity":60.0,"vibration":0.062,"condition":"NORMAL","dht_valid":true,"vibration_valid":true,"sensor_fault":false}
```

**Command sequence:** Operator signs in → Business Forms POST to Flask API → Flask checks session, CSRF token, request and threshold/profile validation → Flask publishes MQTT command with unique ID/expiration → ESP32 validates/applies or rejects → ESP32 publishes `command_ack` → API reports `APPLIED` only on matching acknowledgement. A timeout does **not** mean success. `config` reflects the actual ESP32-confirmed settings.

## 5. Backend, historical data and AI/ML

The subscriber checks message structure and usable numeric values, recognizes severity changes and device freshness, and feeds a separate aggregator. At approximately 30-second intervals it creates `SUMMARY` rows containing sample counts and average/minimum/maximum/latest sensor statistics. It saves condition transitions as `EVENT` rows. Azure Table Storage requires `PartitionKey` and `RowKey`; the device ID groups records and sortable timestamp-based keys support historical queries.

The history API returns JSON from `/api/history/summary` and `/api/history/events`. Its `/api/health` checks the running service. Query parameters support `device`, UTC-date `from`, UTC-date `to`, and `limit`; date scopes are whole calendar days rather than guaranteed second-precision intervals. Only stored data appears. If the subscriber or Azure path is stopped, live MQTT panels may still display but cloud-history panels can be empty or stale.

The saved local **Isolation Forest** model uses four statistics: `TemperatureAvg`, `HumidityAvg`, `VibrationAvg` and `VibrationMax`. Its result is `NORMAL` or `ANOMALY`, published on the MQTT `/ml` topic with an anomaly decision score. **An anomaly is not a confirmed hardware fault or a probability of failure.** The current model was trained from earlier normal-classified summary windows, not independent labeled industrial failure cases. Do not retrain without reviewing the date range in `ml/training/train_model.py` and the data source.

## 6. Operator controls, alerts and security

The single Flask server binds to loopback `127.0.0.1:5001` and incorporates both historical API and control routes. Relevant control endpoints include `POST /api/session` (login), `GET /api/session`, `DELETE /api/session`, `GET /api/config`, `GET /api/control/status`, `GET /api/audit`, `POST /api/config` (thresholds), `POST /api/profile`, `POST /api/alarm/ack`, and `POST /api/config/refresh`. Authenticated writes require a session cookie and the `X-CSRF-Token` header. The control password must be at least 12 characters and session secret at least 32 characters. Operator login is separate from Grafana account authentication.

Email notifications include WARNING, CRITICAL, RECOVERY, and device OFFLINE/ONLINE transitions, subject to the subscriber and SMTP configuration actually running. WARNING/CRITICAL/RECOVERY subjects include the active equipment profile. Email processing and Azure writes use **in-memory** queues; process termination, network failure or queue overflow can lose pending items. Neither email nor software threshold logic is an industrial safety system.

Local MQTT on port 1883 uses broker authentication but, **unless separately configured for TLS**, does not encrypt traffic. Keep this development system on a trusted LAN. Never commit `.env`, `secrets.h`, credentials or private tokens to GitHub. Restrict Grafana and Flask to appropriate access and rotate any exposed secrets.

## 7. Source map and engineering limitations

| Path | Function |
|---|---|
| `firmware/esp32/equipment_monitor/equipment_monitor.ino` | ESP32 sensing, profile logic, LEDs, buzzer, MQTT commands |
| `backend/mqtt/subscriber.py` | Telemetry pipeline, connectivity, events, Azure and ML integration |
| `backend/mqtt/telemetry_aggregator.py` | 30-second sensor statistics |
| `backend/api/control_api.py` | Authenticated operator commands and configuration APIs |
| `backend/azure/storage.py` | Azure SUMMARY and EVENT writes |
| `backend/azure/history_api.py` | Single Flask app and history endpoints |
| `backend/notifications/email_notifier.py` | Email worker and equipment alerts |
| `ml/training/train_model.py` | Offline Isolation Forest model training |
| `ml/inference/predict_anomaly.py` | Anomaly inference on summary features |
| `dashboard/grafana/iot-equipment-live-dashboard.json` | Importable Grafana dashboard definition |
| `docs/wiring/esp32_wiring.md` | Current hardware GPIO reference |

**Limitations:** Single sensing unit and one active profile; non-calibrated ambient and vibration measurements; no physical equipment control or certified safety hardware; dependence on Mac/local services; no MQTT transport TLS in default LAN setup; cloud write and email queues are not durable; cloud-record completeness depends on service uptime; the current model is experimental; SMS is not implemented; regenerated dashboard images are design illustrations. All system-level acceptance cases must be rechecked on the final firmware and active services.

---

## Current Docker Compose Deployment

The primary development deployment now uses Docker Compose on a Mac.

The repository-root `compose.yaml` defines four services:

| Service | Purpose |
|---|---|
| `mosquitto` | Authenticated MQTT broker, host port 1883 |
| `subscriber` | Python telemetry processing, aggregation, Isolation Forest, Azure writes and email alerts |
| `api` | Flask/Waitress history retrieval, authentication and control endpoints on localhost:5001 |
| `grafana` | Live and historical dashboard on localhost:3000 |

The subscriber and API containers communicate with Mosquitto using the Docker service hostname `mosquitto` on port 1883. The ESP32 connects to the Mac's current LAN IP.

Docker persistent volumes retain MQTT data, Grafana data and private configuration. The `.env`, ESP32 `secrets.h` and private Docker secrets must remain outside GitHub.

Start the complete stack:

```bash
docker compose up -d --build
docker compose ps
```

Check the API:

```bash
curl http://127.0.0.1:5001/api/health
```

Stop the stack without deleting persistent volumes:

```bash
docker compose down
```

The older Homebrew/manual-Python deployment remains an alternative, but should not be run simultaneously on conflicting ports.

### Current Data Paths

- Live: ESP32 → Mosquitto → Grafana MQTT datasource.
- Processing: Mosquitto → Python subscriber → aggregation, ML and alerts.
- Historical: Python subscriber → Azure Table Storage → Flask History API → Grafana Infinity datasource.
- Controls: Grafana → authenticated Flask API → MQTT → ESP32 → command acknowledgement.

Azure `SUMMARY` and `EVENT` are logical record types in the configured Azure table, not necessarily separate tables.

The current system supports SMTP email alert functionality; actual email delivery requires validation. SMS/text notifications are a planned enhancement, not an implemented feature.

The architecture diagram is available at `docs/images/system-architecture.png`.
