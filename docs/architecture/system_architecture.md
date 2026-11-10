# System Architecture — IoT Equipment Condition Monitoring

**Course:** SOFE 4610U — Design and Analysis of IoT Software
**Deployment:** ESP32 + Mac (Docker Compose) + Microsoft Azure

![Current System Architecture](../images/system-architecture.png)

## 1. Edge Layer — ESP32

The project uses an ESP32-WROOM-32 connected to:

| Hardware | ESP32 GPIO | Function |
|---|---|---|
| DHT11 | 27 | Temperature and humidity |
| MPU6050/MPU6500 | SDA 21, SCL 22 | Vibration measurement |
| Green LED | 25 | NORMAL indication |
| Yellow LED | 26 | WARNING indication |
| Red LED | 33 | CRITICAL indication |
| Active buzzer | 23 | Audible critical alert |
| Push button | 13 | Alarm acknowledgement |

The ESP32 collects measurements approximately every 2.5 seconds, applies configurable equipment thresholds, classifies conditions, operates LEDs and buzzer, and publishes MQTT telemetry.

Eight monitoring profiles are supported: MOTOR, PUMP, COMPRESSOR, FAN, CONDENSER, HEAT_EXCHANGER, AHU and CHILLER.

One monitoring profile is active at a time. Profiles represent monitoring scenarios, not eight physically connected machines. The project does not control a physical motor or industrial equipment.

Wi-Fi and MQTT settings are read from the private, Git-ignored `secrets.h` file. The firmware does not use WiFiManager.

## 2. Local Monitoring Layer — Docker Compose

The Mac hosts four Docker Compose services defined in the repository-root `compose.yaml`.

| Docker service | Purpose |
|---|---|
| mosquitto | Authenticated MQTT broker on port 1883 |
| subscriber | Python telemetry ingestion, aggregation, Isolation Forest ML, Azure storage writes and email notifications |
| api | Flask/Waitress history retrieval, authentication and remote-control API on localhost:5001 |
| grafana | Live/historical dashboard and operator controls on localhost:3000 |

The ESP32 connects to the Mac's LAN IP on MQTT port 1883. Python services connect to `mosquitto:1883` inside the Docker network.

### Processing

The Python subscriber validates incoming measurements, builds approximately 30-second summaries, detects condition transitions, runs Isolation Forest anomaly inference and publishes derived MQTT messages.

ML anomaly detection is separate from the ESP32 threshold classification. An ML anomaly can be reported while the equipment condition remains NORMAL.

### MQTT Topics

The current device ID is `ESP32-001`.

- `equipment/ESP32-001/telemetry`
- `equipment/ESP32-001/status`
- `equipment/ESP32-001/config`
- `equipment/ESP32-001/sensor_health`
- `equipment/ESP32-001/control_status`
- `equipment/ESP32-001/commands`
- `equipment/ESP32-001/command_ack`
- `equipment/ESP32-001/alerts`
- `equipment/ESP32-001/connectivity`
- `equipment/ESP32-001/ml`

## 3. Cloud Layer — Microsoft Azure

The Python backend writes processed records to Azure Table Storage.

The application distinguishes two logical record types within the configured Azure table:

- **SUMMARY:** Aggregated measurements, sample counts and statistics.
- **EVENT:** Condition transitions and related monitoring events.

The table is configured using `AZURE_TABLE_NAME`, and access uses `AZURE_STORAGE_CONNECTION_STRING`.

The Flask History API retrieves historical records through:

- `GET /api/history/summary`
- `GET /api/history/events`

The current code does not establish a mandatory seven-day retention policy.

## 4. Visualization and Alerts Layer

### Grafana Live Dashboard

Grafana uses its MQTT data source to receive real-time telemetry directly from Mosquitto. Live monitoring does not require the data to pass through Azure first.

### Grafana Historical Dashboard

Grafana uses an HTTP/Infinity data source to request stored records from the Flask History API, which queries Azure Table Storage.

### Remote Configuration

1. Operator signs in through Grafana.
2. Flask authenticates the operator and validates protected requests.
3. The API publishes a profile, threshold or alarm command through MQTT.
4. The ESP32 validates and applies or rejects the command.
5. The ESP32 publishes `command_ack` and confirmed configuration.
6. The application reports success only after matching acknowledgement.

### Notifications

The Python backend contains SMTP email notifications for WARNING, CRITICAL, RECOVERY and connectivity events. Delivery requires valid SMTP credentials.

SMS/text notifications are planned, not implemented.

## 5. Security and Reliability

- Mosquitto requires username/password authentication.
- MQTT broker data is stored using a Docker persistent volume.
- Flask operator controls use sessions and request protection.
- The ESP32 supports Wi-Fi and MQTT reconnection.
- Flask and Grafana host bindings use localhost.
- Sensitive settings remain in untracked files or private Docker volumes.

MQTT port 1883 is not TLS-encrypted in this deployment. It should only be used on a trusted local network.
