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

The current deployment separates cloud processing from
the locally hosted Grafana dashboard.

```text
ESP32 + DHT11 + MPU6050
          |
          | Wi-Fi / MQTT TLS :8883
          v
Azure Ubuntu VM — Docker Compose
          |
          +-- Mosquitto MQTT Broker
          +-- Python Subscriber + Isolation Forest
          +-- Flask History and Control API
          |
          v
Azure Table Storage
          |
          | Flask API through SSH tunnel
          v
Grafana OSS on Mac — localhost:3000
```

Grafana also subscribes directly to the Azure MQTT broker
over TLS for live data.

The same dashboard displays current readings, historical
Azure records, ML results, operator controls and alerts.

[Detailed Current Architecture](docs/architecture/system_architecture.md)

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
| 🐳 **Containerization** | Three Azure Docker services with Mac-hosted Grafana |

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

The ESP32 connects to the Azure MQTT broker using
authenticated MQTT over TLS on TCP port **8883**.

**Broker hostname:**
`iot-monitor-dp0912.northcentralus.cloudapp.azure.com`

The broker also offers port 1883 inside Docker for
the subscriber and API. Port 1883 is not publicly published.

The current device identifier is `ESP32-001`.

| Topic suffix | Purpose |
|---|---|
| `telemetry` | Sensor readings |
| `status` | Online/offline state |
| `config` | Confirmed thresholds and profile |
| `sensor_health` | Sensor validity |
| `control_status` | Alarm and equipment state |
| `alerts` | Equipment alerts |
| `commands` | Remote control commands |
| `command_ack` | Control acknowledgements |
| `connectivity` | Connectivity events |
| `ml` | Isolation Forest results |

All topics use the prefix `equipment/ESP32-001/`.

The ESP32 uses WiFiManager for network onboarding.
Entering `W` in Serial Monitor opens the configuration
portal manually without disabling the home router.

Network switching has been demonstrated between home
Wi-Fi and an iPhone hotspot. Automatic multi-network
roaming is not part of the current firmware.

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

The current Azure backend uses `compose.cloud.yaml`.

| Service | Location | Function |
|---|---|---|
| `mosquitto` | Azure VM | Secure MQTT broker |
| `subscriber` | Azure VM | Ingestion, ML, storage, email |
| `api` | Azure VM | History and operator control |
| `grafana` | Mac via Homebrew | Single monitoring dashboard |

Grafana OSS is free. Azure VM and storage costs depend
on the Azure subscription and usage.

The original `compose.yaml` and `compose.release.yaml`
remain in the repository as local-development alternatives.
They are not the currently running cloud deployment.

---

## 🚀 Getting Started

### Current deployment

1. The Azure Ubuntu VM runs the three Docker services
   defined in `compose.cloud.yaml`.
2. Private MQTT certificates, credentials and Azure
   connection settings are configured outside Git.
3. The ESP32 uses `equipment_monitor.ino`,
   `mqtt_ca.h` and a private `secrets.h`.
4. WiFiManager configures the device Wi-Fi through
   `EquipmentMonitor-Setup`.
5. Grafana OSS runs on the Mac at `http://localhost:3000`.
6. The MQTT data source connects to Azure using TLS.
7. An SSH tunnel forwards the Azure Flask API to
   `127.0.0.1:5001` for history and controls.

### Documentation

[Current Operations Guide](docs/guides/02_OPERATIONS_GUIDE.md)

[Current System Architecture](docs/architecture/system_architecture.md)

[ESP32 Configuration Example](firmware/esp32/equipment_monitor/secrets.example.h)

The private `secrets.h` and `.env` are not committed.

---

## 📁 Repository Structure

```text
IoT-Equipment-Condition-Monitoring-System/
├── README.md
├── compose.cloud.yaml
├── compose.yaml
├── compose.release.yaml
├── .env.example
├── firmware/esp32/equipment_monitor/
│   ├── equipment_monitor.ino
│   ├── mqtt_ca.h
│   └── secrets.example.h
├── backend/
│   ├── mqtt/
│   ├── azure/
│   ├── api/
│   └── notifications/
├── ml/
├── docker/
│   ├── Dockerfile
│   ├── run_api.py
│   └── mosquitto/
├── dashboard/grafana/
├── docs/
└── .github/workflows/
```

Private credentials, certificate keys, and runtime data
remain outside version control.

---

## 🔐 Security

- Authenticated MQTT over TLS on public port 8883
- Trusted private CA for MQTT certificate verification
- MQTT port 1883 not publicly published
- Flask API bound to Azure VM localhost
- SSH tunnel for Mac-to-Azure history and control access
- Separate authenticated Grafana operator controls
- ESP32 command acknowledgements
- Private `.env`, `secrets.h` and certificate keys
- No publicly exposed Grafana web service

Previously exposed credentials should be rotated.

The software is an educational monitoring prototype,
not a certified industrial safety system.

---

## 📚 Documentation

**Current deployment:** [Azure Operations Guide](docs/guides/02_OPERATIONS_GUIDE.md) and [System Architecture](docs/architecture/system_architecture.md).


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
