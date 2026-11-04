# IoT Equipment Condition Monitoring System

**ESP32 • DHT11 • MPU6050/MPU6500 • Mosquitto MQTT • Python • Azure Table Storage • Grafana • Isolation Forest • Email**

SOFE 4610U educational IoT prototype for **monitoring** equipment conditions, not physically controlling machinery. One `ESP32-001` runs one selectable equipment profile at a time. Profiles: **MOTOR, PUMP, COMPRESSOR, FAN, CONDENSER, HEAT_EXCHANGER, AHU, CHILLER**. These names select demonstration threshold sets; they do not mean eight real machines are attached.

## Features

- Temperature and humidity (DHT11 ambient sensor) and vibration RMS (MPU accelerometer).
- Local NORMAL/WARNING/CRITICAL classification; green/yellow/red LED indicators.
- GPIO23 critical audible alarm (200 ms on, 800 ms off); GPIO13 button acknowledges and mutes sound **without clearing the condition**.
- MQTT live telemetry, connectivity, sensor health, alert events, command acknowledgement and current configuration.
- Grafana dashboard with live readings, sensor trends, sensor health, equipment/alarm state, confirmed thresholds, ML anomaly status and Azure history.
- Authenticated local Flask operator API for profile and threshold updates, with ESP32 acknowledgements.
- Python subscriber with approximately 30-second aggregation, Isolation Forest inference and optional cloud history storage.
- Email alerts for WARNING, CRITICAL and RECOVERY, including current equipment type. Optional connectivity emails are supported.

> **Safety:** thresholds are educational examples, not manufacturer-approved limits. This system is not a certified safety controller. No physical motor, LCD, IR remote or sound sensor is used.

## Architecture

```text
ESP32 (DHT11 + MPU, LEDs, buzzer, acknowledge button)
    | MQTT
Mosquitto broker
    |-- Grafana MQTT live dashboard
    |-- Python subscriber
          |-- Azure Table Storage (SUMMARY / EVENT)
          |      `-- Flask History API -- Grafana Azure history panels
          |-- Isolation Forest inference -- MQTT ML panel
          |-- SMTP notifications (warning / critical / recovery)
    `-- Flask local operator-control API -- signed MQTT commands -- ESP32 ACK
```

For the current system data flow, see [architecture](docs/architecture/system_architecture.md) and [wiring](docs/wiring/esp32_wiring.md).

## Hardware

See [hardware/components.md](hardware/components.md) and [ESP32 wiring](docs/wiring/esp32_wiring.md). Arduino sketch: `firmware/esp32/equipment_monitor/equipment_monitor.ino`. Its private `secrets.h` is intentionally **not** stored in GitHub.

## Repository layout

```text
backend/
  api/control_api.py                 # Local operator login, profile/threshold commands
  azure/history_api.py              # Flask history + control API integration
  azure/storage.py                  # Azure Table Storage history
  azure/query_history.py            # History troubleshooting CLI
  azure/log_analytics.py            # Optional Log Analytics
  mqtt/subscriber.py                # MQTT processing, alerts, ML and notifications
  mqtt/telemetry_aggregator.py      # Time-window summary
  notifications/email_notifier.py   # Gmail SMTP queue
dashboard/grafana/iot-equipment-live-dashboard.json
firmware/esp32/equipment_monitor/equipment_monitor.ino
hardware/components.md
docs/wiring/esp32_wiring.md
docs/testing/current_validation.md
ml/training/  ml/inference/  ml/models/
tests/test_monitoring_rebuild_contract.py
.env.example  .gitignore  requirements.txt
```

## Local setup

1. Clone this repository and open in VS Code. Create Python environment: `python3 -m venv .venv && source .venv/bin/activate` then `python -m pip install -r requirements.txt`.
2. Copy `.env.example` to `.env`, fill in **your own** MQTT, Azure, SMTP and control values. Never commit `.env`. Use a strong, unique operator password and random session secret.
3. Set up Mosquitto locally with the broker credentials matching `.env` and `secrets.h`; see [Mosquitto docs](https://mosquitto.org/documentation/).
4. Create `firmware/esp32/equipment_monitor/secrets.h` locally containing the `WIFI_SSID`, `WIFI_PASSWORD`, `MQTT_SERVER`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD` definitions expected by the sketch. Use Arduino IDE with ESP32 core, DHT library, PubSubClient and ArduinoJson 7. Verify before uploading.
5. Start Mosquitto, then from project root run `python backend/mqtt/subscriber.py` and `python backend/azure/history_api.py` in separate terminals. Start Grafana via your existing installed service.
6. Import `dashboard/grafana/iot-equipment-live-dashboard.json` into Grafana. Install/configure the MQTT and Infinity data sources and the Dynamic Text/Business Forms panels used by this dashboard. Existing local data-source UIDs may need reassignment.
7. Sign in to the local operator panel before applying threshold or profile changes. Confirm the dashboard's **Confirmed Thresholds** panel reflects the ESP32 response.

Only the two Azure historical panels use Grafana's dashboard time range; the real-time MQTT panels use their own short live windows.

## MQTT topics

`equipment/ESP32-001/{telemetry,status,config,sensor_health,control_status,commands,command_ack}` — device topics. Python also publishes `{alerts,connectivity,ml}`. MQTT command IDs and expiry protect operator writes.

## Operator dashboard

The dashboard has 22 panels, including device online state, temperature/humidity/vibration stats, condition, live trends and readings, alerts, Azure history, ML predictions, sensor health, equipment/alarm, confirmed thresholds, operator login and threshold/profile controls. Debug fields are not shown as normal operator data.

## Verification

Run `python -m unittest discover -s tests -v`, then use [current validation checklist](docs/testing/current_validation.md) for live testing. Python syntax and dashboard JSON validation do **not** substitute for compiling the ESP32 sketch or checking live Grafana.

## Scaling

The current prototype monitors one profile on one ESP32. Future expansion can introduce distinct equipment IDs (`FAN-01`, `FAN-02`, `MOTOR-01`) with device IDs (`ESP32-001`, etc.), topics and data processing adjusted accordingly. Multi-device support is **planned, not currently implemented**.

## Security and privacy

Keep `.env`, `secrets.h`, session secrets, Azure connection strings, SMTP app passwords, local virtual environments and Git metadata out of uploads and commits. The Flask API is for local use; do not expose it to the public Internet. If any credential was previously committed, rotate it; `.gitignore` alone does not erase Git history.
