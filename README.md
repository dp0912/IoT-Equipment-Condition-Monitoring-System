
<div align="center">

# ⚙️ IoT Equipment Condition Monitoring System

### Intelligent Edge Monitoring • Cloud Analytics • Machine Learning

**An end-to-end Industrial IoT prototype combining real-time sensor monitoring, edge intelligence, cloud-based analytics, machine learning, and automated equipment alerts.**

<br>

![ESP32](https://img.shields.io/badge/ESP32-Edge%20Computing-E7352C?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-Backend-3776AB?style=for-the-badge&logo=python&logoColor=white)
![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?style=for-the-badge)
![Azure](https://img.shields.io/badge/Microsoft%20Azure-Cloud-0078D4?style=for-the-badge)
![Grafana](https://img.shields.io/badge/Grafana-Dashboard-F46800?style=for-the-badge&logo=grafana&logoColor=white)
![Scikit-learn](https://img.shields.io/badge/Scikit--learn-Anomaly%20Detection-F7931E?style=for-the-badge)

<br>

![Status](https://img.shields.io/badge/Status-Prototype%20%7C%20Integration%20Testing-yellow)
![Course](https://img.shields.io/badge/Ontario%20Tech%20University-SOFE%204610U-003DA5)

**[Overview](#-project-overview) · [Architecture](#-system-architecture) · [Features](#-key-features) · [Dashboard](#-grafana-dashboard) · [Documentation](#-project-documentation) · [Setup](#-quick-start)**

</div>

---

## 📖 Project Overview

The **IoT Equipment Condition Monitoring System** is an Industrial IoT prototype developed for **SOFE 4610U — Design of IoT** at Ontario Tech University.

The system uses an **ESP32-WROOM-32** with DHT11 and MPU6050/MPU6500 sensors to monitor temperature, humidity, and vibration. Sensor measurements are evaluated locally to determine equipment conditions and transmitted using MQTT to a Python backend.

The backend integrates **Microsoft Azure Table Storage**, **Isolation Forest machine learning**, email notifications, and a Grafana dashboard for live monitoring, historical analysis, and authenticated remote configuration.

### Supported Equipment Profiles

The system supports eight configurable equipment-monitoring profiles:

`MOTOR` · `PUMP` · `COMPRESSOR` · `FAN` · `CONDENSER` · `HEAT_EXCHANGER` · `AHU` · `CHILLER`

Each profile provides configurable temperature, humidity, and vibration thresholds.

> **Scope:** The current prototype uses one ESP32 to monitor one selected equipment profile at a time. It does not physically operate industrial machinery.

---

## 🏗️ System Architecture

The system uses a four-layer architecture separating edge processing, MQTT communication and backend services, cloud storage, and visualization.

<div align="center">

<img src="docs/images/system-architecture.png" alt="IoT Equipment Condition Monitoring System Architecture" width="100%">

<sub>System architecture — Edge Computing, Python Services, Azure Storage, Grafana Visualization & Alerts</sub>

</div>

| Layer | Technologies | Responsibilities |
|---|---|---|
| **Edge Computing** | ESP32, DHT11, MPU6050/MPU6500 | Sensor acquisition, condition classification, local alerts |
| **Local Services** | Mosquitto, Python, Flask | MQTT messaging, aggregation, ML, notifications, operator commands |
| **Cloud** | Microsoft Azure Table Storage | Historical sensor summaries and condition events |
| **Visualization** | Grafana, SMTP | Real-time dashboard, historical analysis, operator controls, email alerts |

**Telemetry Flow**

`ESP32 → MQTT Broker → Python Backend → Azure / ML → Grafana`

**Operator Control Flow**

`Grafana → Authenticated Flask API → MQTT Commands → ESP32 → Acknowledgement`

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 📡 **Real-Time Monitoring** | Temperature, humidity, and vibration telemetry approximately every 2.5 seconds |
| 🚦 **Condition Detection** | Edge-based NORMAL, WARNING, and CRITICAL classification |
| 🔔 **Local Alerts** | Green/yellow/red LEDs, audible buzzer, and acknowledgement button |
| 🏭 **Equipment Profiles** | Eight selectable equipment profiles with configurable thresholds |
| 🔐 **Operator Authentication** | Dedicated Sign In / Sign Out controls and session status |
| 🎛️ **Remote Configuration** | Authenticated threshold and profile changes with ESP32 command confirmation |
| 🔒 **Access Protection** | Flask sessions, CSRF protection, and restricted configuration endpoints |
| 💾 **Persistent Configuration** | Equipment profiles and thresholds retained after restart |
| ☁️ **Azure Integration** | Historical sensor summaries and equipment events |
| 🤖 **ML Anomaly Detection** | Isolation Forest inference on aggregated telemetry |
| 📧 **Email Notifications** | Equipment-specific WARNING, CRITICAL, RECOVERY, and connectivity alerts |
| 📊 **Grafana Visualization** | Live measurements, historical trends, sensor health, and configuration |

---

## 📊 Grafana Dashboard

The Grafana dashboard provides a centralized interface for monitoring equipment conditions, reviewing historical information, detecting anomalies, and managing authorized configuration changes.

<div align="center">

<img src="docs/images/grafana-dashboard.png" alt="IoT Equipment Condition Monitoring Dashboard" width="100%">

<sub>Illustrative dashboard showcase based on the implemented monitoring system.</sub>

</div>

### Dashboard Capabilities

| Real-Time Monitoring | Analytics & Configuration |
|---|---|
| Temperature, humidity, and vibration | Azure historical sensor trends |
| Equipment condition and connectivity | Historical equipment alerts |
| Latest sensor readings | Isolation Forest anomaly status |
| Sensor health and alarm state | Operator Sign In / Sign Out |
| Equipment alerts | Configurable thresholds |
| Live sensor trends | Eight selectable equipment profiles |

### 🔐 Operator Authentication & Access Control

The dashboard includes an operator authentication system that is separate from Grafana's own user login.

Operators must authenticate before applying configuration changes to the ESP32.

The **Operator Access** panel provides:

- **Username and Password:** Credentials for authorized operators.
- **Sign in:** Authenticates the operator through the Flask backend.
- **Sign out:** Ends the active operator session.
- **Session Status:** Displays `SIGNED IN`, `SIGNED OUT`, or an API availability state.

#### Operator Permissions

| Function | Signed Out | Signed In |
|---|---|---|
| View live sensor readings | ✅ Allowed | ✅ Allowed |
| View equipment condition | ✅ Allowed | ✅ Allowed |
| View historical Azure data | ✅ Allowed | ✅ Allowed |
| View alerts and sensor health | ✅ Allowed | ✅ Allowed |
| Change temperature thresholds | 🔒 Restricted | ✅ Allowed |
| Change humidity thresholds | 🔒 Restricted | ✅ Allowed |
| Change vibration thresholds | 🔒 Restricted | ✅ Allowed |
| Change equipment profile | 🔒 Restricted | ✅ Allowed |
| Access operator configuration API | 🔒 Restricted | ✅ Allowed |

Dashboard viewing remains available to users who have permission to access Grafana. Operator authentication controls the separate equipment-configuration API.

#### Authentication Workflow

**1. Signed Out**

The operator session is inactive. Sensor readings, equipment conditions, alerts, and historical data remain available.

Configuration requests are rejected by the Flask backend until the operator signs in.

**2. Sign In**

An operator enters their credentials and selects **Sign in**.

The Flask API validates the credentials and establishes an authenticated session.

The dashboard displays the authenticated operator status.

**3. Configuration Changes**

Once authenticated, the operator can modify threshold values or select an equipment monitoring profile.

The command is sent through the Flask backend using MQTT.

The dashboard reports successful application only after receiving the matching ESP32 acknowledgement.

**4. Sign Out**

The operator selects **Sign out** to terminate the authenticated session.

The dashboard returns to `SIGNED OUT`, and subsequent configuration requests are denied until the operator authenticates again.

**5. Session Expiration**

Operator sessions also have a backend-enforced security timeout. This provides additional protection if an operator leaves the dashboard without manually signing out.

#### Authentication Security

The control system uses:

- Environment-based operator credentials stored outside the repository.
- Flask session cookies.
- CSRF protection for configuration-changing requests.
- Operator authentication checks on protected API endpoints.
- Login attempt rate limiting.
- Explicit Sign Out functionality.
- ESP32 command acknowledgement before reporting success.

Operator credentials are not stored in the exported Grafana dashboard JSON.

The control API is intended for local development and should not be exposed directly to the public internet without additional production security controls.

### Grafana Technologies

The dashboard uses:

- **Grafana MQTT Data Source** for live telemetry.
- **Infinity Data Source** for historical Azure information through Flask.
- **Business Forms** for operator authentication and configuration.
- **Dynamic Text** for customized equipment, sensor, and anomaly status displays.

**[View Grafana Dashboard JSON](dashboard/grafana/iot-equipment-live-dashboard.json)**

---

## 🔧 Hardware & Edge Processing

### ESP32 Hardware Configuration

| Component | ESP32 GPIO | Purpose |
|---|---|---|
| DHT11 | GPIO 27 | Temperature and humidity |
| MPU6050/MPU6500 SDA | GPIO 21 | I²C data |
| MPU6050/MPU6500 SCL | GPIO 22 | I²C clock |
| Green LED | GPIO 25 | NORMAL condition |
| Yellow LED | GPIO 26 | WARNING condition |
| Red LED | GPIO 33 | CRITICAL condition |
| Push Button | GPIO 13 | Alarm acknowledgement |
| Active Buzzer | GPIO 23 | Audible critical alert |

### Condition Classification

| Condition | Local Response |
|---|---|
| 🟢 **NORMAL** | Green LED ON |
| 🟡 **WARNING** | Yellow LED ON |
| 🔴 **CRITICAL** | Red LED ON and buzzer activated |

Temperature and humidity use upper and lower thresholds, while vibration uses upper thresholds.

During a CRITICAL condition, the buzzer repeats a **200 ms ON / 800 ms OFF** pattern.

Pressing the physical button acknowledges and silences the alarm without changing the actual equipment condition.

**[View Hardware Wiring](docs/wiring/esp32_wiring.md)**

---

## 📡 MQTT Communication

The system uses **Eclipse Mosquitto** as its local MQTT broker.

The current device identifier is `ESP32-001`.

### MQTT Topics

| Topic | Purpose |
|---|---|
| `equipment/ESP32-001/telemetry` | Live sensor measurements |
| `equipment/ESP32-001/status` | Device online/offline state |
| `equipment/ESP32-001/config` | Confirmed thresholds and equipment profile |
| `equipment/ESP32-001/sensor_health` | Sensor diagnostics |
| `equipment/ESP32-001/control_status` | Equipment condition and audible alarm |
| `equipment/ESP32-001/commands` | Operator configuration commands |
| `equipment/ESP32-001/command_ack` | ESP32 command acknowledgements |
| `equipment/ESP32-001/alerts` | Equipment alerts |
| `equipment/ESP32-001/connectivity` | Backend connectivity monitoring |
| `equipment/ESP32-001/ml` | ML anomaly results |

### Example Telemetry Payload

```json
{
  "device_id": "ESP32-001",
  "profile": "MOTOR",
  "temperature": 24.8,
  "humidity": 60.0,
  "vibration": 0.062,
  "condition": "NORMAL",
  "dht_valid": true,
  "vibration_valid": true,
  "sensor_fault": false
}
```

MQTT enables bidirectional communication between the ESP32 and the monitoring services.

Operator commands are transmitted through the authenticated Flask API rather than directly from unauthenticated dashboard controls.

---

## 🤖 Machine Learning & Azure

### AI/ML Anomaly Detection

The Python backend aggregates valid telemetry into approximately **30-second windows**.

An **Isolation Forest** model analyzes the aggregated sensor features and produces a NORMAL or ANOMALY classification with an anomaly score.

**ML Pipeline**

`Sensor Data → Aggregation → Feature Preparation → Isolation Forest → MQTT Result → Grafana`

The ML subsystem operates alongside the ESP32's threshold-based condition classification.

### Azure Historical Storage

Microsoft Azure Table Storage stores two types of monitoring records:

- **SUMMARY:** Aggregated temperature, humidity, and vibration measurements.
- **EVENT:** Equipment condition changes and alert events.

A Flask History API retrieves Azure records and serves them to Grafana for historical analysis.

Historical measurements are displayed as individual points to avoid implying continuous monitoring across periods where data was not collected.

> ML results are experimental indicators, not validated industrial fault diagnoses.

---

## 📧 Automated Email Notifications

The Python backend provides equipment-specific notifications through SMTP.

| Alert | Trigger |
|---|---|
| ⚠️ WARNING | Equipment enters WARNING condition |
| 🚨 CRITICAL | Equipment enters CRITICAL condition |
| ✅ RECOVERY | Equipment returns to NORMAL |
| 📶 OFFLINE / ONLINE | Device connectivity changes |

Example notification:

```text
Subject: RECOVERY - MOTOR - Equipment Back to Normal

IoT EQUIPMENT CONDITION MONITORING SYSTEM
-----------------------------------------

Alert: RECOVERY
Equipment: MOTOR
Device: ESP32-001
Previous Condition: CRITICAL
Current Condition: NORMAL

Temperature: 26.7 C
Humidity: 63.0 %
Vibration: 0.2131 RMS
```

The selected equipment profile is included automatically in equipment-condition notifications.

---

## 🛠️ Technology Stack

| Category | Technology |
|---|---|
| Embedded Hardware | ESP32-WROOM-32 |
| Firmware | Arduino C++ |
| Sensors | DHT11, MPU6050/MPU6500 |
| Communication | MQTT, Eclipse Mosquitto |
| Backend | Python, Paho MQTT |
| REST APIs | Flask |
| Authentication | Flask Sessions, CSRF, CORS |
| Cloud | Microsoft Azure Table Storage |
| Dashboard | Grafana |
| Machine Learning | Scikit-learn, Isolation Forest |
| Notifications | SMTP |
| Development | VS Code, Arduino IDE, Git, GitHub |

---

## 📚 Project Documentation

The project includes two consolidated guides covering its technical design, installation, daily operation, and validation.

| Document | Description |
|---|---|
| 📘 **[Technical Project Guide](docs/guides/01_TECHNICAL_GUIDE.md)** | System architecture, ESP32 firmware, hardware, MQTT, Python backend, Azure integration, Grafana, ML, alerts, and security |
| 🛠️ **[Operations & Testing Guide](docs/guides/02_OPERATIONS_AND_TESTING.md)** | First-time setup, environment configuration, startup/shutdown, troubleshooting, and end-to-end testing |

**Additional References**

- [System Architecture](docs/architecture/system_architecture.md)
- [ESP32 Hardware Wiring](docs/wiring/esp32_wiring.md)
- [Current Validation Checklist](docs/testing/current_validation.md)
- [Grafana Dashboard Configuration](dashboard/grafana/iot-equipment-live-dashboard.json)

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/dp0912/IoT-Equipment-Condition-Monitoring-System.git
cd IoT-Equipment-Condition-Monitoring-System
```

### 2. Configure Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Configure `.env` with MQTT credentials, Azure settings, operator authentication, and optional SMTP configuration.

### 3. Upload ESP32 Firmware

Open:

```text
firmware/esp32/equipment_monitor/equipment_monitor.ino
```

Configure the local, Git-ignored `secrets.h` with Wi-Fi and MQTT credentials.

Install the required Arduino libraries, select **ESP32 Dev Module**, and upload the firmware.

### 4. Start MQTT Broker

For a local Homebrew installation:

```bash
brew services start mosquitto
```

### 5. Start Python Backend

Open a terminal with the virtual environment activated:

```bash
source .venv/bin/activate
python backend/mqtt/subscriber.py
```

### 6. Start History & Operator Control API

Open a separate terminal with the virtual environment activated:

```bash
source .venv/bin/activate
python backend/azure/history_api.py
```

The Flask API runs at:

```text
http://127.0.0.1:5001
```

The same Flask service provides:

- Historical Azure data.
- Operator session authentication.
- Sign In / Sign Out endpoints.
- Remote threshold configuration.
- Equipment profile configuration.
- ESP32 command acknowledgement.

### 7. Start Grafana

```bash
brew services start grafana
```

Open:

**http://localhost:3000**

Import the dashboard configuration:

```text
dashboard/grafana/iot-equipment-live-dashboard.json
```

Configure the MQTT and Infinity data sources and required Grafana plugins.

### 8. Operator Sign In / Sign Out

In the dashboard, navigate to **Configuration & Control → Operator Access**.

1. Enter the configured operator credentials.
2. Click **Sign in**.
3. Verify that the operator status shows `SIGNED IN`.
4. Apply an authorized threshold or equipment profile change.
5. Verify the ESP32 acknowledgement.
6. Click **Sign out** when finished.
7. Confirm that the operator status shows `SIGNED OUT`.

After Sign Out, configuration changes are blocked until the operator signs in again.

For detailed setup and troubleshooting, see the **[Operations & Testing Guide](docs/guides/02_OPERATIONS_AND_TESTING.md)**.

---

## 📁 Repository Structure

```text
IoT-Equipment-Condition-Monitoring-System/
│
├── README.md
├── requirements.txt
├── .env.example
│
├── firmware/
│   └── esp32/
│       └── equipment_monitor/
│           └── equipment_monitor.ino
│
├── hardware/
│   └── components.md
│
├── backend/
│   ├── api/                  # Operator authentication and controls
│   ├── mqtt/                 # Subscriber and aggregation
│   ├── azure/                # Cloud storage and history
│   └── notifications/        # Email alerts
│
├── dashboard/
│   └── grafana/              # Grafana dashboard JSON
│
├── ml/
│   ├── training/             # Model training
│   ├── inference/            # Anomaly inference
│   └── models/               # Isolation Forest model
│
├── docs/
│   ├── guides/
│   │   ├── 01_TECHNICAL_GUIDE.md
│   │   └── 02_OPERATIONS_AND_TESTING.md
│   │
│   ├── architecture/
│   │   └── system_architecture.md
│   │
│   ├── images/
│   │   ├── system-architecture.png
│   │   └── grafana-dashboard.png
│   │
│   ├── wiring/
│   │   └── esp32_wiring.md
│   │
│   └── testing/
│       └── current_validation.md
│
└── tests/
    └── test_monitoring_rebuild_contract.py
```

---

<div align="center">

### Built with ESP32 • Python • MQTT • Microsoft Azure • Grafana • Scikit-learn

*Transforming real-time sensor measurements into intelligent equipment insights.*

</div>
