<div align="center">

# ⚙️ IoT Equipment Condition Monitoring System

### Intelligent Edge Monitoring • Real-Time IoT • Cloud Analytics • Machine Learning

An end-to-end Industrial Internet of Things (IIoT) prototype that combines ESP32-based sensor monitoring, MQTT communication, real-time analytics, machine learning, Microsoft Azure storage, and interactive Grafana dashboards.

<br>

![ESP32](https://img.shields.io/badge/ESP32-Edge%20Computing-E7352C?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-Backend-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?style=for-the-badge)
![Azure](https://img.shields.io/badge/Microsoft%20Azure-Storage-0078D4?style=for-the-badge)
![Grafana](https://img.shields.io/badge/Grafana-Dashboard-F46800?style=for-the-badge&logo=grafana&logoColor=white)
![Scikit-learn](https://img.shields.io/badge/Scikit--learn-Isolation%20Forest-F7931E?style=for-the-badge)

<br>

**Ontario Tech University | SOFE 4610U — Design and Analysis of IoT Software**

[Overview](#-project-overview) • [Architecture](#-system-architecture) • [Features](#-key-features) • [Dashboard](#-grafana-dashboard) • [Setup](#-getting-started) • [Documentation](#-documentation)

</div>

---

## 📖 Project Overview

The **IoT Equipment Condition Monitoring System** is a configurable equipment monitoring platform designed to demonstrate the complete lifecycle of IoT data, from physical sensors to cloud storage and visualization.

An **ESP32-WROOM-32** collects temperature, humidity, and vibration measurements using DHT11 and MPU6050/MPU6500 sensors.

The ESP32 evaluates configurable thresholds locally and classifies equipment conditions into three levels:

- 🟢 **NORMAL** — Sensor readings are within configured operating limits.
- 🟡 **WARNING** — One or more measurements exceed warning limits.
- 🔴 **CRITICAL** — One or more measurements exceed critical limits.

The ESP32 activates local LED and buzzer indicators while publishing telemetry through MQTT.

A Docker-based Python backend processes incoming measurements, performs aggregation and Isolation Forest anomaly detection, stores historical records in Microsoft Azure Table Storage, and delivers email notifications.

**Grafana** provides live monitoring, historical trends, anomaly visualization, and authenticated equipment configuration.

The system supports eight equipment profiles, enabling the same monitoring hardware to represent different equipment scenarios.

> **Scope:** This is an educational monitoring prototype using one ESP32 and one active equipment profile at a time. It does not directly control an industrial motor or other machinery and is not a certified safety system.

---

## 🏗️ System Architecture

<div align="center">

<img src="docs/images/system-architecture.png" alt="IoT Equipment Condition Monitoring System Architecture" width="100%">

<sub>ESP32 Edge Layer • Docker-Based MQTT and Processing • Azure Storage • Grafana Visualization</sub>

</div>

### Architecture Components

| Layer | Technology | Responsibility |
|---|---|---|
| **Device & Edge** | ESP32, DHT11, MPU6050/MPU6500 | Sensor acquisition, condition classification, local alerts |
| **Communication** | MQTT, Eclipse Mosquitto | Telemetry, device status, commands and acknowledgements |
| **Processing** | Python, Paho MQTT, Scikit-learn | Aggregation, event processing, anomaly detection and notifications |
| **Cloud Storage** | Microsoft Azure Table Storage | Historical summaries and monitoring events |
| **API & Control** | Flask, Waitress | Historical data retrieval and authenticated configuration |
| **Visualization** | Grafana | Real-time readings, historical trends, ML results and controls |
| **Infrastructure** | Docker Compose | Local service orchestration and persistent data |

### Data Flow

```text
ESP32 + Sensors
      |
      | MQTT Telemetry
      v
Eclipse Mosquitto
      |
      +----------------------> Grafana Live Dashboard
      |
      v
Python Subscriber
      |
      +----> Data Aggregation
      |
      +----> Isolation Forest Anomaly Detection
      |
      +----> Event Detection and Email Alerts
      |
      v
Microsoft Azure Table Storage
      |
      v
Flask History API
      |
      v
Grafana Historical Dashboard
```

### Remote Configuration Flow

```text
Grafana Operator Controls
          |
          v
Authenticated Flask API
          |
          v
MQTT Command via Mosquitto
          |
          v
ESP32 Configuration Update
          |
          v
MQTT Command Acknowledgement
          |
          v
Grafana Confirmation
```

The backend reports a configuration change as applied only after receiving the corresponding ESP32 acknowledgement.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 📡 **Real-Time Telemetry** | Temperature, humidity and vibration readings approximately every 2.5 seconds |
| 🚦 **Edge Condition Detection** | NORMAL, WARNING and CRITICAL classification |
| 🔔 **Local Alerts** | Green, yellow and red LEDs, active buzzer and physical acknowledgement button |
| 🏭 **Equipment Profiles** | Eight equipment monitoring profiles with configurable thresholds |
| 🎛️ **Remote Configuration** | Change monitoring profiles and thresholds through Grafana |
| 🔐 **Operator Authentication** | Protected sign-in, sessions and authorized control requests |
| ✅ **Command Acknowledgements** | ESP32 confirms accepted or rejected configuration updates |
| 💾 **Persistent Settings** | ESP32 stores monitoring configuration using Preferences |
| 🤖 **ML Anomaly Detection** | Isolation Forest inference on aggregated telemetry |
| ☁️ **Cloud Storage** | Historical summaries and events in Azure Table Storage |
| �� **Grafana Visualization** | Live monitoring, historical trends and configuration panels |
| 📧 **Email Notifications** | Warning, critical, recovery, offline and online notifications |
| 📶 **Connectivity Monitoring** | Device availability and automatic reconnection |
| 🐳 **Containerization** | Four local services managed with Docker Compose |

---

## 🏭 Supported Equipment Profiles

The platform supports eight configurable monitoring profiles:

| Profile | Equipment Scenario |
|---|---|
| `MOTOR` | Electric motor |
| `PUMP` | Industrial pump |
| `COMPRESSOR` | Compressor |
| `FAN` | Ventilation fan |
| `CONDENSER` | Condenser |
| `HEAT_EXCHANGER` | Heat exchanger |
| `AHU` | Air handling unit |
| `CHILLER` | Chiller |

Each profile defines configurable temperature, humidity and vibration limits.

Only one profile is active at a time. An operator can switch profiles or modify thresholds through authenticated Grafana controls.

---

## 📊 Grafana Dashboard

<div align="center">

<img src="docs/images/grafana-dashboard.png" alt="IoT Equipment Monitoring Grafana Dashboard" width="100%">

<sub>Grafana monitoring dashboard with live telemetry, historical analytics and operator controls.</sub>

</div>

### Dashboard Capabilities

**Real-Time Monitoring**
- Temperature, humidity and vibration measurements
- Current equipment condition
- ESP32 online/offline status
- Sensor health and local alarm state
- Machine learning anomaly results

**Historical Analytics**
- Azure historical temperature and humidity trends
- Historical vibration measurements
- Aggregated monitoring summaries
- Equipment warning, critical and recovery events

**Operator Configuration**
- Operator sign-in and sign-out
- Equipment profile selection
- Temperature, humidity and vibration threshold updates
- ESP32-confirmed configuration values
- MQTT command acknowledgements

### Grafana Plugins

The dashboard uses:

- **Grafana MQTT Data Source** — Real-time MQTT telemetry
- **Infinity Data Source** — Historical data through the Flask API
- **Business Forms** — Operator authentication and configuration
- **Dynamic Text** — Customized dashboard displays

[View Dashboard JSON](dashboard/grafana/iot-equipment-live-dashboard.json)

---

## 🔧 Hardware

The system uses an ESP32-WROOM-32 development board and the following components.

| Component | GPIO / Connection | Purpose |
|---|---|---|
| DHT11 | GPIO27 | Temperature and humidity |
| MPU6050/MPU6500 SDA | GPIO21 | I²C sensor data |
| MPU6050/MPU6500 SCL | GPIO22 | I²C sensor clock |
| Green LED | GPIO25 | NORMAL indicator |
| Yellow LED | GPIO26 | WARNING indicator |
| Red LED | GPIO33 | CRITICAL indicator |
| Active Buzzer | GPIO23 | Audible critical alarm |
| Push Button | GPIO13 | Alarm acknowledgement |

The buzzer uses a repeating 200 ms ON / 800 ms OFF pattern during an unacknowledged critical condition.

The button allows the operator to silence the alarm without changing the measured equipment condition.

**Firmware:** [equipment_monitor.ino](firmware/esp32/equipment_monitor/equipment_monitor.ino)

**Wiring Guide:** [ESP32 Hardware Wiring](docs/wiring/esp32_wiring.md)

---

## 📡 MQTT Communication

Eclipse Mosquitto provides authenticated publish/subscribe messaging between the ESP32, Python backend, Flask API and Grafana.

The current device identifier is `ESP32-001`.

| MQTT Topic | Purpose |
|---|---|
| `equipment/ESP32-001/telemetry` | Sensor readings |
| `equipment/ESP32-001/status` | Device availability |
| `equipment/ESP32-001/config` | Confirmed equipment configuration |
| `equipment/ESP32-001/sensor_health` | Sensor diagnostics |
| `equipment/ESP32-001/control_status` | Condition and alarm status |
| `equipment/ESP32-001/alerts` | Equipment alerts |
| `equipment/ESP32-001/commands` | Remote configuration commands |
| `equipment/ESP32-001/command_ack` | Command acknowledgements |
| `equipment/ESP32-001/connectivity` | Connectivity events |
| `equipment/ESP32-001/ml` | Machine learning results |

MQTT authentication uses a private Mosquitto password file. Anonymous connections are disabled.

The current local-network MQTT listener uses port `1883` without TLS. It must not be exposed directly to the public internet.

---

## 🤖 Machine Learning

The Python backend uses **Scikit-learn Isolation Forest** for unsupervised anomaly detection.

Valid sensor measurements are aggregated into approximately 30-second windows.

The model uses four features:

1. Average temperature
2. Average humidity
3. Average vibration
4. Maximum vibration

The model produces a `NORMAL` or `ANOMALY` classification and an anomaly score.

Machine learning detection operates independently of the ESP32's configurable warning and critical thresholds.

This enables the system to flag unusual telemetry patterns even when individual sensor readings remain within the configured operating limits.

The model is experimental and does not provide certified industrial fault diagnosis.

---

## ☁️ Azure Cloud Storage

The project uses **Microsoft Azure Table Storage** to retain processed IoT monitoring data.

The backend stores two logical record types in the configured Azure table.

| Record Type | Information |
|---|---|
| `SUMMARY` | Aggregated temperature, humidity and vibration statistics |
| `EVENT` | Equipment condition transitions and monitoring events |

The Flask History API retrieves records through:

```http
GET /api/history/summary
GET /api/history/events
```

Grafana uses the Infinity data source to visualize the retrieved historical records.

The Azure connection string and table name are configured using private environment variables.

---

## 📧 Automated Notifications

The Python backend provides configurable SMTP email notifications.

| Notification | Trigger |
|---|---|
| ⚠️ WARNING | Equipment enters a warning condition |
| 🚨 CRITICAL | Equipment enters a critical condition |
| ✅ RECOVERY | Equipment returns to normal |
| 📶 DEVICE OFFLINE | Device connectivity is lost |
| 📶 DEVICE ONLINE | Device connectivity is restored |

Notifications require valid SMTP configuration in the private `.env` file.

**Planned enhancement:** SMS/text notifications for critical events.

---

## 🐳 Docker Infrastructure

The local application stack runs through **Docker Compose**.

| Service | Technology | Function | Host Port |
|---|---|---|---|
| `mosquitto` | Eclipse Mosquitto | MQTT broker | `1883` |
| `subscriber` | Python 3.12 | Ingestion, ML, Azure writes and notifications | Internal |
| `api` | Flask, Waitress | History API and operator controls | `127.0.0.1:5001` |
| `grafana` | Grafana | Visualization and configuration | `127.0.0.1:3000` |

Docker volumes preserve MQTT broker data, private configuration and Grafana application data.

---

## 🚀 Getting Started

### Prerequisites

- ESP32 development board and connected sensors
- Arduino IDE with ESP32 board support
- DHT sensor library, PubSubClient and ArduinoJson
- Docker Desktop with Docker Compose
- Local Wi-Fi network accessible to the ESP32 and host computer
- Microsoft Azure Storage account
- Private MQTT, Grafana operator and optional SMTP credentials

### 1. Clone the Repository

```bash
git clone https://github.com/dp0912/IoT-Equipment-Condition-Monitoring-System.git
cd IoT-Equipment-Condition-Monitoring-System
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and configure the required MQTT, Azure and operator credentials.

Configure SMTP settings if email notifications are enabled.

Never commit `.env` or real credentials.

### 3. Configure and Upload ESP32 Firmware

Open:

```text
firmware/esp32/equipment_monitor/equipment_monitor.ino
```

Create `secrets.h` in the same directory:

```cpp
#pragma once

#define WIFI_SSID "YOUR_WIFI_NAME"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

#define MQTT_SERVER "YOUR_MAC_LOCAL_IP"
#define MQTT_PORT 1883

#define MQTT_USERNAME "YOUR_MQTT_USERNAME"
#define MQTT_PASSWORD "YOUR_MQTT_PASSWORD"
```

Update the placeholder values.

In Arduino IDE, select **ESP32 Dev Module**, choose the correct USB port, and upload the firmware.

The Serial Monitor uses **115200 baud**.

### 4. Prepare Private Docker Configuration

This deployment uses three external volumes:

```bash
docker volume create iot-mqtt-secrets
docker volume create iot-grafana-data
docker volume create iot-grafana-config
```

These volumes require the appropriate private configuration.

- `iot-mqtt-secrets` contains the Mosquitto password file.
- `iot-grafana-data` stores Grafana dashboards, plugins and application data.
- `iot-grafana-config` contains the private Grafana configuration.

Creating the volumes alone does not configure authentication or Grafana.

See the [Operations Guide](docs/guides/02_OPERATIONS_GUIDE.md) for configuration details.

If the volumes are already configured, preserve and reuse them.

### 5. Start the Application

Open Docker Desktop and run from the repository root:

```bash
docker compose up -d --build
```

View the running services:

```bash
docker compose ps
```

### 6. Open Grafana

Open:

**http://localhost:3000**

Sign in to Grafana and open the equipment monitoring dashboard.

For a new Grafana installation, import:

```text
dashboard/grafana/iot-equipment-live-dashboard.json
```

Configure the required plugins and data sources.

### 7. Access the API

The local Flask API is available at:

**http://127.0.0.1:5001**

Health endpoint:

```bash
curl http://127.0.0.1:5001/api/health
```

### 8. Stop the Application

```bash
docker compose down
```

This stops the containers while preserving persistent volumes.

Do not use `docker compose down -v` for routine shutdown.

---

## 📁 Repository Structure

```text
IoT-Equipment-Condition-Monitoring-System/
|
├── README.md
├── compose.yaml
├── requirements.txt
├── .env.example
├── .dockerignore
|
├── firmware/
│   └── esp32/
│       └── equipment_monitor/
│           └── equipment_monitor.ino
|
├── hardware/
│   └── components.md
|
├── backend/
│   ├── mqtt/
│   ├── api/
│   ├── azure/
│   └── notifications/
|
├── ml/
│   ├── training/
│   ├── inference/
│   └── models/
|
├── dashboard/
│   └── grafana/
│       └── iot-equipment-live-dashboard.json
|
├── docker/
│   ├── Dockerfile
│   ├── run_api.py
│   └── mosquitto/
│       └── mosquitto.conf
|
└── docs/
    ├── architecture/
    │   └── system_architecture.md
    ├── guides/
    │   ├── 01_TECHNICAL_GUIDE.md
    │   └── 02_OPERATIONS_GUIDE.md
    ├── images/
    │   ├── system-architecture.png
    │   └── grafana-dashboard.png
    └── wiring/
        └── esp32_wiring.md
```

Private credentials, configuration secrets and persistent Docker data are excluded from Git.

---

## 🔐 Security

The system includes:

- MQTT username/password authentication
- Disabled anonymous broker access
- Separate operator authentication for configuration changes
- Flask session and CSRF protections
- Protected configuration endpoints
- ESP32 command acknowledgements
- Private environment configuration
- Localhost-bound Grafana and Flask services
- Persistent Docker storage

The implementation is intended for trusted local-network development. Production deployment would require additional security hardening, including encrypted MQTT transport and durable service-level recovery mechanisms.

---

## 📚 Documentation

| Document | Description |
|---|---|
| [System Architecture](docs/architecture/system_architecture.md) | System components and data flow |
| [Technical Guide](docs/guides/01_TECHNICAL_GUIDE.md) | Firmware, MQTT, backend, cloud, ML and control design |
| [Operations Guide](docs/guides/02_OPERATIONS_GUIDE.md) | Setup, startup, shutdown and troubleshooting |
| [Hardware Wiring](docs/wiring/esp32_wiring.md) | ESP32 pin connections |
| [Grafana Dashboard JSON](dashboard/grafana/iot-equipment-live-dashboard.json) | Exported monitoring dashboard |

---

## 🛠️ Technology Stack

**Hardware:** ESP32-WROOM-32, DHT11, MPU6050/MPU6500, LEDs, buzzer and push button

**Firmware:** Arduino C++

**Communication:** MQTT, Eclipse Mosquitto, Paho MQTT

**Backend:** Python, Flask, Waitress

**Machine Learning:** Scikit-learn, Isolation Forest

**Cloud:** Microsoft Azure Table Storage

**Visualization:** Grafana

**Notifications:** SMTP

**Infrastructure:** Docker, Docker Compose

**Development:** VS Code, Arduino IDE, Git and GitHub

---

<div align="center">

### Built with ESP32 • MQTT • Python • Docker • Azure • Grafana • Scikit-learn

**From real-time sensor data to intelligent equipment monitoring.**

</div>
