<div align="center">

# ⚙️ IoT Equipment Condition Monitoring System

**A secure, end-to-end ESP32 monitoring platform — from physical sensors to Azure cloud analytics.**

**ESP32** · **MQTT over TLS** · **Docker** · **Python** · **Azure Table Storage** · **Isolation Forest** · **Grafana OSS**

[Architecture](#-system-architecture) · [Features](#-what-it-does) · [Quick start](#-run-the-existing-deployment) · [Wi-Fi onboarding](#-esp32-wi-fi-setup) · [Project structure](#-repository-structure)

*SOFE 4610U — Internet of Things · Ontario Tech University*

</div>

---

## 🌟 Project overview

This project monitors the condition of an equipment **profile** using one real **ESP32-WROOM-32**, a **DHT11** temperature/humidity sensor, and an **MPU6050/MPU6500** accelerometer for vibration estimation. The ESP32 classifies measurements against configurable limits, drives local indicators, and sends JSON telemetry to an authenticated **Mosquitto broker on an Azure Ubuntu VM** over **MQTT/TLS (port 8883)**.

An Azure-hosted Python subscriber validates incoming readings, creates **30-second historical summaries**, runs an **Isolation Forest** anomaly detector, records events in **Azure Table Storage**, and sends configured **email alerts**. A separate Flask API supports history retrieval and authenticated control commands.

One free **Grafana OSS** dashboard runs on the Mac, showing **live MQTT**, **Azure historical data**, **ML status**, **device health**, **alerts**, and **operator controls**. Grafana does **not** run as a paid Azure Managed Grafana service.

## 🏗️ System architecture

![Current Azure system architecture](docs/images/system-architecture-azure.png)

**How data moves**

1. **Sense and classify — ESP32:** Samples temperature, humidity and vibration approximately every **2.5 seconds**; classifies `NORMAL`, `WARNING`, or `CRITICAL`; operates local LEDs and buzzer.
2. **Publish securely — Azure Mosquitto:** ESP32 connects through Wi-Fi to the Azure hostname over **TLS + MQTT username/password** on public **TCP 8883**. Mosquitto exposes **TCP 1883 only inside Docker** for backend services.
3. **Process — Python subscriber:** Checks sensor validity, detects condition changes and connectivity, aggregates measurements into **30-second windows**, and runs ML predictions on suitable windows.
4. **Store and notify:** Saves `SUMMARY` and `EVENT` entities to **Azure Table Storage**; publishes live status, alerts and ML updates to MQTT; queues configured SMTP email notifications.
5. **Visualize — one Grafana dashboard:** Live panels subscribe directly to Azure MQTT/TLS. Historical panels query the Flask API using the **Infinity** data source via an **SSH tunnel**. Operator forms use the same API to send authenticated commands back to the ESP32 over MQTT.

See the [detailed architecture](docs/architecture/system_architecture.md).

## ✨ What it does

| Capability | Implementation |
|---|---|
| Real sensors | DHT11 temperature/humidity and MPU6050/MPU6500 vibration estimate |
| Device condition | Threshold-based `NORMAL`, `WARNING`, `CRITICAL` at the edge |
| Local indicators | Green/yellow/red LEDs, active buzzer, acknowledgment button |
| Equipment modes | Eight **monitoring profiles**, each with adjustable limits |
| Portable Wi-Fi setup | WiFiManager captive portal and manual `W` command |
| Cloud MQTT | Azure-hosted Mosquitto 2, encrypted TLS client connections |
| Cloud processing | Python subscriber with validation and retry queue |
| Machine learning | Scikit-learn **Isolation Forest** anomaly status and score |
| Cloud persistence | Azure Table Storage `SUMMARY` and `EVENT` records |
| Notifications | SMTP email on configured equipment and connectivity changes |
| Single dashboard | Live metrics, trends, alerts, ML, health, status and controls |
| Remote operations | Operator sign-in, thresholds, profile changes and buzzer acknowledgment |

**Scope:** The eight equipment types are monitoring configurations. This project does **not** physically operate or protect an industrial motor, pump, chiller or other machine.

## 🧰 Technology stack

| Layer | Technologies |
|---|---|
| Device | ESP32 (Arduino C++), DHT11, MPU6050/MPU6500, LEDs, buzzer, button |
| Network and security | WiFiManager, PubSubClient, MQTT, TLS, private CA, password authentication |
| Cloud VM | Microsoft Azure Ubuntu 24.04, Docker Compose, Eclipse Mosquitto 2 |
| Backend | Python 3.12, paho-mqtt, Flask, Waitress |
| Data and ML | Azure Table Storage, pandas, scikit-learn, joblib |
| Dashboard | Grafana OSS on macOS, MQTT data source, Infinity data source, Grafana form panels |
| Notifications | SMTP email |

## 🔌 Hardware and pins

| Component | ESP32 GPIO | Description |
|---|---:|---|
| DHT11 DATA | 27 | Ambient temperature + relative humidity |
| MPU SDA / SCL | 21 / 22 | I²C acceleration-derived vibration RMS |
| Green LED | 25 | `NORMAL` |
| Yellow LED | 26 | `WARNING` |
| Red LED | 33 | `CRITICAL` |
| Active buzzer / driver | 23 | Audible critical alarm |
| Pushbutton | 13 | Silence/acknowledge buzzer (`INPUT_PULLUP`) |

All sensors share a common ground. Use LED current-limiting resistors, and a transistor driver when a buzzer's current exceeds safe GPIO output. More detail: [ESP32 wiring guide](docs/wiring/esp32_wiring.md).

## 📡 MQTT topics

All topics use the prefix `equipment/ESP32-001/`.

| Topic | Main producer | Purpose |
|---|---|---|
| `telemetry` | ESP32 | Live sensor JSON + validity flags + condition |
| `status` | ESP32 | Retained online state / last will |
| `sensor_health` | ESP32 | Sensor health and fault reason |
| `config` | ESP32 | Current confirmed profile and thresholds |
| `control_status` | ESP32 | Alarm/equipment state |
| `commands` | Flask control API | Authenticated remote requests |
| `command_ack` | ESP32 | Device acknowledgment for control requests |
| `alerts` | Python subscriber | Condition and sensor-health events |
| `connectivity` | Python subscriber | Retained online/offline snapshot |
| `ml` | Python subscriber | Isolation Forest prediction + anomaly score |

**Broker:** `iot-monitor-dp0912.northcentralus.cloudapp.azure.com` · **External TLS:** `8883` · **Docker-internal MQTT:** `1883`.

## 📊 Single Grafana dashboard

![Grafana monitoring dashboard](docs/images/grafana-dashboard.png)

*Dashboard screenshot stored in the repository; the current live values and panel layout can change over time.*

The dashboard combines real-time monitoring, device connectivity, sensor health, ML anomaly status, historical Azure trends, operator sign-in and remote configuration. Live MQTT and historical queries use **different data sources** but are displayed together on this **one dashboard**.

## 🤖 Analytics and historical storage

The Python subscriber groups readings into approximately **30-second windows**, computing averages, minima, maxima, valid sample counts and worst observed condition. The same summary provides features for the model: temperature average, humidity average, vibration average and vibration maximum.

The Isolation Forest result is separate from the ESP32 rule-based condition. Model output is `NORMAL` or `ANOMALY` with an anomaly score. A window containing sensor faults is skipped for ML rather than treating invalid data as a meaningful anomaly.

Azure Table Storage contains **`SUMMARY`** and **`EVENT`** entries. The History API exposes:

- `GET /api/history/summary`
- `GET /api/history/events`

The in-memory retry queue is not durable across a backend process termination; historical reliability can be improved in future revisions.

## 🚀 Run the existing deployment

These instructions are for the **already configured Azure VM and ESP32**, not a completely new cloud account. Existing private `.env`, Mosquitto credentials/certificates, device settings and Grafana data sources must be preserved. Run the cloud commands **only on Azure**, and the Mac commands **only on macOS**.

### 1 — Azure VM: start the cloud backend

Connect from **Mac Terminal**:

```bash
ssh azureuser@iot-monitor-dp0912.northcentralus.cloudapp.azure.com
```

On the **Azure SSH terminal**:

```bash
cd ~/IoT-Equipment-Condition-Monitoring-System

docker compose -f compose.cloud.yaml up -d
```

The three cloud services are `mosquitto`, `subscriber`, and `api`. Docker Compose sets `restart: unless-stopped` so the existing containers normally restart with Docker. Use `docker compose -f compose.cloud.yaml up -d --build` **only when deploying changes to backend code or container dependencies**.

> **Do not** start a duplicate subscriber on your Mac or run an old local Mosquitto stack. That can cause duplicate alerts and writes or connect to the wrong broker.

### 2 — ESP32: power the device

Power the ESP32 via USB. It reconnects to its saved Wi-Fi when available and then to the Azure MQTT broker; **no local Mac broker is required**. Telemetry is sent approximately every **2.5 seconds**.

For a first-time firmware installation, open `firmware/esp32/equipment_monitor/equipment_monitor.ino` in Arduino IDE, install the board support and libraries (**DHT sensor library**, **WiFiManager**, **PubSubClient**, **ArduinoJson**; ESP32 framework provides Wi-Fi, Wire and Preferences), and create a private `secrets.h` from `secrets.example.h`. The tracked `mqtt_ca.h` contains the CA certificate used to verify the broker. Never upload private passwords or CA signing keys to Git.

### 3 — Mac Terminal A: start the one Grafana dashboard

```bash
brew services start grafana
```

Open **<http://localhost:3000>** and select the existing **IoT Equipment Condition Monitoring — Live MQTT Test** dashboard. Your Grafana installation and data sources should be kept as configured:

- **`grafana-mqtt-datasource`:** `tls://iot-monitor-dp0912.northcentralus.cloudapp.azure.com:8883` with the configured MQTT username/password and trusted CA certificate. Keep **Skip TLS Verification OFF**.
- **`Azure-Historical-Data`:** Infinity data source for Azure history through the Flask API tunnel.

The JSON dashboard backup is at [`dashboard/grafana/iot-equipment-live-dashboard.json`](dashboard/grafana/iot-equipment-live-dashboard.json).

### 4 — Mac Terminal B: connect historical data and operator controls

Keep **another Mac Terminal window open** with this command:

```bash
ssh -o ExitOnForwardFailure=yes -N \
  -L 127.0.0.1:5001:127.0.0.1:5001 \
  azureuser@iot-monitor-dp0912.northcentralus.cloudapp.azure.com
```

This secure SSH tunnel forwards the cloud Flask service to `http://127.0.0.1:5001` on your Mac. The browser-side operator forms and Infinity historical queries rely on it. **Leaving this terminal open is intentional.** It is not needed for direct MQTT live data, but it *is* needed for history and operator controls from the Mac.

### 5 — Use the dashboard

Choose **Last 15 minutes** for live monitoring. For Azure history, choose a longer range (such as **Last 7 days**) and zoom into old points. Because Grafana uses one dashboard-wide time range, **live panels may show “No data” when an old absolute period is selected**. Choose **Last 15 minutes** to return to current telemetry.

Sign in with your separately configured **operator credentials** to change thresholds, select an equipment profile, refresh configuration, or acknowledge the audible alarm. These actions send commands to the ESP32 and receive device acknowledgments.

### 6 — When finished

You may close Grafana and the **SSH tunnel** on your Mac when not viewing the dashboard. **Do not stop the Azure containers** if you want the ESP32's cloud ingestion, storage, ML processing and email notifications to continue. Azure VM and storage resources may incur charges while running.

## 📶 ESP32 Wi-Fi setup

The ESP32 uses **WiFiManager**. If its stored Wi-Fi is unavailable, it can offer `EquipmentMonitor-Setup`. To change Wi-Fi **without turning off your existing router**:

1. Open Arduino **Serial Monitor at 115200 baud** while the ESP32 is USB-connected.
2. Type **`W`** and press Send.
3. Connect your Mac to **`EquipmentMonitor-Setup`** using the private portal password.
4. Open **<http://192.168.4.1>** while connected to that ESP32 Wi-Fi.
5. Select a new 2.4 GHz-compatible Wi-Fi network or phone hotspot, enter its password, and save.
6. Reconnect the Mac to its normal Wi-Fi; the ESP32 independently reconnects to **the same Azure broker**.

Switching between home Wi-Fi and an iPhone hotspot has been demonstrated. The firmware does **not** automatically choose among multiple saved networks, and some captive/enterprise networks may need additional authentication that WiFiManager alone cannot complete.

## ⚙️ Cloud deployment files and private configuration

| File | Purpose |
|---|---|
| `compose.cloud.yaml` | Current Azure Docker Compose services |
| `docker/mosquitto/mosquitto.cloud.conf` | MQTT internal listener, TLS listener, authentication and persistence |
| `docker/Dockerfile` | Backend image for subscriber and API |
| `docker/run_api.py` | Waitress API startup and MQTT control listener |
| `.env.example` | Template for the **private Azure `.env`** |
| `firmware/esp32/equipment_monitor/secrets.example.h` | Template for the **private firmware `secrets.h`** |

A new VM deployment also needs private certificates and a Mosquitto password file under the paths mounted by `compose.cloud.yaml`, as described in the [operations guide](docs/guides/02_OPERATIONS_GUIDE.md). The remote TLS certificate must match the broker's DNS hostname. **Do not commit secrets, `.env`, `secrets.h`, `cloud-private/`, or private keys.**

### Internal and external connectivity

| Endpoint | Exposure | Used by |
|---|---|---|
| Azure MQTT `8883/tcp` | Public TLS (subject to Azure firewall rules) | ESP32 + Mac Grafana MQTT |
| Docker MQTT `1883/tcp` | Container network only | Python subscriber + Flask control API |
| Azure API `127.0.0.1:5001` | VM loopback only | Mac SSH tunnel |
| Grafana `localhost:3000` | Mac-hosted web UI | Browser on Mac |

**Cost note:** Grafana OSS is free to self-host. Azure VM, networking and storage costs depend on your Azure subscription. There is no Azure Managed Grafana requirement for this project.

## 📂 Repository structure

```text
IoT-Equipment-Condition-Monitoring-System/
├── README.md
├── compose.cloud.yaml
├── .env.example                    # Template, not real secrets
├── requirements.txt
├── firmware/esp32/equipment_monitor/
│   ├── equipment_monitor.ino      # Sensors, classification, Wi-Fi, MQTT, controls
│   ├── mqtt_ca.h                 # Trusted root CA certificate
│   └── secrets.example.h         # Private secrets.h template
├── backend/
│   ├── mqtt/
│   │   ├── subscriber.py
│   │   └── telemetry_aggregator.py
│   ├── azure/
│   │   ├── storage.py
│   │   ├── query_history.py
│   │   └── history_api.py
│   ├── api/control_api.py
│   └── notifications/email_notifier.py
├── ml/
│   ├── inference/predict_anomaly.py
│   ├── training/train_model.py
│   └── models/isolation_forest.joblib
├── docker/
│   ├── Dockerfile
│   ├── run_api.py
│   └── mosquitto/mosquitto.cloud.conf
├── dashboard/grafana/
│   └── iot-equipment-live-dashboard.json
└── docs/
    ├── architecture/system_architecture.md
    ├── guides/02_OPERATIONS_GUIDE.md
    ├── images/
    │   ├── system-architecture-azure.png
    │   └── grafana-dashboard.png
    └── wiring/esp32_wiring.md
```

## 🔒 Security and limitations

- Public MQTT clients authenticate with a username/password and validate the broker's TLS certificate using the project's root CA.
- The Azure Flask API is exposed only on VM loopback; the Mac reaches it through SSH port forwarding.
- Operator access uses a separate session login and CSRF-protected commands; Grafana login is not a substitute for operator authentication.
- Sensor glitches can still cause temporary DHT11 faults or warnings; the system is an **educational prototype**, not a certified industrial safety system.
- The notification implementation supports **email**; **SMS is not implemented**.
- Manual Wi-Fi onboarding is implemented; automatic multi-network roaming is not.
- Credentials previously shared outside secure storage should be rotated in the actual services.

## 📖 Additional documentation

- [Detailed system architecture](docs/architecture/system_architecture.md)
- [Azure operations guide](docs/guides/02_OPERATIONS_GUIDE.md)
- [ESP32 wiring and safety](docs/wiring/esp32_wiring.md)
- [Public ESP32 configuration example](firmware/esp32/equipment_monitor/secrets.example.h)

---

<div align="center">

**From sensor readings to secure cloud analytics — one ESP32, one Azure backend, one Grafana dashboard.**

</div>
