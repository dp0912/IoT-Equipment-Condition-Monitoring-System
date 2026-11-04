
<div align="center">

# ⚙️ IoT Equipment Condition Monitoring System

### Intelligent Edge Monitoring • Cloud Analytics • Machine Learning

**A configurable end-to-end Industrial IoT prototype for real-time equipment monitoring, anomaly detection, historical analytics, and automated alerting.**

<br>

![ESP32](https://img.shields.io/badge/ESP32-Edge%20Computing-E7352C?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-Backend-3776AB?style=for-the-badge&logo=python&logoColor=white)
![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?style=for-the-badge)
![Azure](https://img.shields.io/badge/Microsoft%20Azure-Cloud-0078D4?style=for-the-badge)
![Grafana](https://img.shields.io/badge/Grafana-Visualization-F46800?style=for-the-badge&logo=grafana&logoColor=white)
![Scikit-learn](https://img.shields.io/badge/Scikit--learn-Machine%20Learning-F7931E?style=for-the-badge)

<br>

![Status](https://img.shields.io/badge/Status-Prototype%20%7C%20Integration%20Testing-yellow)
![University](https://img.shields.io/badge/Ontario%20Tech%20University-SOFE%204610U-003DA5)

**[Overview](#-overview) • [Architecture](#-system-architecture) • [Features](#-key-features) • [Dashboard](#-grafana-dashboard) • [Installation](#-getting-started)**

</div>

---

## 📖 Overview

The **IoT Equipment Condition Monitoring System** is an end-to-end Industrial IoT prototype developed for **SOFE 4610U — Design of IoT** at Ontario Tech University.

The system combines **ESP32 edge computing, MQTT communication, Python services, Microsoft Azure, Grafana, and Isolation Forest machine learning** to transform real-time sensor measurements into actionable equipment insights.

An ESP32 collects temperature, humidity, and vibration measurements, evaluates configurable thresholds locally, and publishes telemetry through an MQTT broker. A Python backend processes incoming data, handles historical storage and notifications, and provides anomaly detection and authenticated operator configuration.

### Supported Equipment Profiles

The system includes eight selectable equipment monitoring profiles:

`MOTOR` · `PUMP` · `COMPRESSOR` · `FAN` · `CONDENSER` · `HEAT_EXCHANGER` · `AHU` · `CHILLER`

> **Project scope:** One ESP32 monitors one selected equipment profile at a time. These profiles simulate different monitoring contexts; the prototype does not physically operate industrial machinery.

---

## 🏗️ System Architecture

The architecture separates sensor acquisition, local processing, cloud storage, and visualization into four integrated layers.

<div align="center">

<img src="docs/images/system-architecture.png" alt="IoT Equipment Condition Monitoring System Architecture" width="100%">

<sub>Four-layer IoT architecture: Edge Device → Local Services → Azure Cloud → Visualization & Alerts</sub>

</div>

### Architecture Layers

| Layer | Technology | Responsibility |
|---|---|---|
| **Edge Layer** | ESP32, DHT11, MPU6050/MPU6500 | Sensor acquisition, validation, local condition classification, LEDs, buzzer |
| **Local Services** | Mosquitto, Python, Flask, Scikit-learn | MQTT messaging, processing, aggregation, ML inference, operator commands, email alerts |
| **Cloud Layer** | Microsoft Azure Table Storage | Persistent telemetry summaries and equipment events |
| **Visualization & Alerts** | Grafana, SMTP | Live monitoring, historical analysis, remote configuration, notifications |

**Data flow:** ESP32 → MQTT Broker → Python Services → Azure / ML → Grafana & Email Notifications.

**Operator control:** Grafana → Authenticated Flask API → MQTT Commands → ESP32 → Command Acknowledgement.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 📡 **Real-Time Monitoring** | Temperature, humidity, and vibration measurements approximately every 2.5 seconds |
| 🚦 **Edge-Based Detection** | NORMAL, WARNING, and CRITICAL condition classification |
| 🔔 **Local Alerts** | Green/yellow/red LEDs, audible buzzer, and physical acknowledgement button |
| 🏭 **Equipment Profiles** | Eight selectable profiles with customizable monitoring thresholds |
| 🎛️ **Remote Configuration** | Authenticated Grafana controls with ESP32 command acknowledgement |
| 💾 **Persistent Settings** | Equipment profile and thresholds saved across ESP32 restarts |
| ☁️ **Azure Integration** | Historical sensor summaries and condition events in Azure Table Storage |
| 🤖 **ML Anomaly Detection** | Isolation Forest analysis on aggregated telemetry |
| 📧 **Email Alerts** | Equipment-specific WARNING, CRITICAL, RECOVERY, and connectivity notifications |
| 📊 **Grafana Dashboard** | Live monitoring, diagnostics, ML results, historical trends, and configuration |

---

## 📊 Grafana Dashboard

A centralized Grafana interface provides real-time equipment visibility, condition monitoring, historical analytics, and operator configuration.

<div align="center">

<img src="docs/images/grafana-dashboard.png" alt="IoT Equipment Condition Monitoring Dashboard" width="100%">

<sub>Illustrative dashboard showcase based on the implemented monitoring and configuration features.</sub>

</div>

### Monitoring & Visualization

- **Live Telemetry:** Temperature, humidity, vibration RMS, and equipment condition.
- **Sensor Diagnostics:** DHT11 and MPU sensor validity, device connectivity, and fault detection.
- **Equipment Alerts:** WARNING, CRITICAL, and RECOVERY events.
- **Historical Analytics:** Azure-backed sensor trends and condition history.
- **AI/ML:** Isolation Forest anomaly status and anomaly score.

### Configuration & Control

- Authenticated operator login.
- Temperature and humidity upper/lower thresholds.
- Vibration warning and critical thresholds.
- Eight selectable equipment profiles.
- ESP32-confirmed configuration and audible alarm status.

The dashboard integrates **Grafana MQTT and Infinity data sources**, **Business Forms**, and **Dynamic Text**.

**[Explore the Grafana Dashboard Configuration](dashboard/grafana/iot-equipment-live-dashboard.json)**

---

## 🔧 Hardware & Edge Processing

### Hardware Components

| Component | ESP32 GPIO | Function |
|---|---|---|
| DHT11 | GPIO 27 | Ambient temperature and humidity |
| MPU6050/MPU6500 SDA | GPIO 21 | I²C data |
| MPU6050/MPU6500 SCL | GPIO 22 | I²C clock |
| Green LED | GPIO 25 | NORMAL indication |
| Yellow LED | GPIO 26 | WARNING indication |
| Red LED | GPIO 33 | CRITICAL indication |
| Push Button | GPIO 13 | Alarm acknowledgement |
| Active Buzzer | GPIO 23 | Audible critical alarm |

### Condition Monitoring

The ESP32 classifies sensor readings using configurable thresholds.

| Condition | Edge Response |
|---|---|
| 🟢 **NORMAL** | Green LED |
| 🟡 **WARNING** | Yellow LED |
| 🔴 **CRITICAL** | Red LED and repeating audible alarm |

Temperature and humidity are checked against upper and lower thresholds. Vibration is checked against upper thresholds.

The buzzer uses a **200 ms ON / 800 ms OFF** pattern. Pressing the acknowledgement button silences the sound while preserving the actual equipment condition.

**[View Hardware & Wiring Documentation](docs/wiring/esp32_wiring.md)**

---

## 📡 MQTT Communication

The ESP32 communicates with the Python backend and Grafana through an authenticated Mosquitto MQTT broker.

The current monitoring device identifier is `ESP32-001`.

### MQTT Topics

| Topic | Purpose |
|---|---|
| `equipment/ESP32-001/telemetry` | Live sensor readings and condition |
| `equipment/ESP32-001/status` | Device online/offline status |
| `equipment/ESP32-001/config` | Confirmed equipment profile and thresholds |
| `equipment/ESP32-001/sensor_health` | Sensor diagnostics |
| `equipment/ESP32-001/control_status` | Equipment and audible alarm state |
| `equipment/ESP32-001/commands` | Operator configuration commands |
| `equipment/ESP32-001/command_ack` | Applied/rejected command acknowledgements |
| `equipment/ESP32-001/alerts` | Equipment condition events |
| `equipment/ESP32-001/ml` | Machine-learning inference results |

### Example Telemetry

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

MQTT messaging enables bidirectional communication for telemetry, configuration changes, and command acknowledgements.

---

## 🤖 Machine Learning & Azure

### AI/ML Anomaly Detection

The Python backend aggregates valid telemetry into approximately **30-second windows** and processes it using an **Isolation Forest** model.

The ML subsystem supplements rule-based condition classification with anomaly detection.

**ML Pipeline:**

`Sensor Data → Validation → Aggregation → Feature Extraction → Isolation Forest → MQTT Results → Grafana`

### Cloud Historical Analytics

Microsoft Azure Table Storage stores historical monitoring information, including:

- **SUMMARY:** Aggregated temperature, humidity, and vibration records.
- **EVENT:** Equipment condition changes, alerts, and recovery events.

The Flask History API exposes records to Grafana using HTTP/JSON, allowing users to analyze historical trends over selected date ranges.

> ML results are experimental anomaly indicators, not validated industrial fault diagnoses.

---

## 📧 Automated Alerts

The Python notification service sends equipment-specific alerts through SMTP.

| Alert Type | Trigger |
|---|---|
| ⚠️ WARNING | Warning threshold reached |
| 🚨 CRITICAL | Critical threshold reached |
| ✅ RECOVERY | Equipment returns to NORMAL |
| 📶 OFFLINE / ONLINE | Device connectivity changes |

**Example Email:**

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

Equipment names are dynamically included in condition-alert emails based on the selected monitoring profile.

---

## 🛠️ Technology Stack

| Category | Technology |
|---|---|
| Embedded System | ESP32-WROOM-32, Arduino C++ |
| Sensors | DHT11, MPU6050/MPU6500 |
| Communication | MQTT, Eclipse Mosquitto |
| Backend | Python, Paho MQTT |
| APIs | Flask |
| Cloud Storage | Microsoft Azure Table Storage |
| Visualization | Grafana |
| Machine Learning | Scikit-learn, Isolation Forest |
| Notifications | SMTP |
| Development | VS Code, Arduino IDE, Git, GitHub |

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/dp0912/IoT-Equipment-Condition-Monitoring-System.git
cd IoT-Equipment-Condition-Monitoring-System
```

### 2. Set Up the Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Configure the local `.env` file with your MQTT, Azure, operator authentication, and optional email settings.

### 3. Upload ESP32 Firmware

Open the Arduino sketch:

```text
firmware/esp32/equipment_monitor/equipment_monitor.ino
```

Create a local `secrets.h` with Wi-Fi and MQTT credentials. Install the required Arduino libraries, select **ESP32 Dev Module**, and upload the firmware.

### 4. Start Local Services

Start Mosquitto:

```bash
brew services start mosquitto
```

Start the Python MQTT subscriber:

```bash
python backend/mqtt/subscriber.py
```

In a second terminal, start the History / Control API:

```bash
python backend/azure/history_api.py
```

Start Grafana:

```bash
brew services start grafana
```

Open **http://localhost:3000** and import:

```text
dashboard/grafana/iot-equipment-live-dashboard.json
```

Configure Grafana data sources and install the required plugins.

> These service commands describe the local macOS/Homebrew development environment. Cloud credentials, MQTT authentication, and SMTP settings must be configured separately.

---

## 📁 Repository Structure

```text
IoT-Equipment-Condition-Monitoring-System/
│
├── backend/
│   ├── api/              # Authenticated operator controls
│   ├── mqtt/             # MQTT subscriber and aggregation
│   ├── azure/            # Azure storage and history API
│   └── notifications/    # Equipment email alerts
│
├── firmware/
│   └── esp32/            # ESP32 Arduino firmware
│
├── dashboard/
│   └── grafana/          # Grafana dashboard JSON
│
├── ml/
│   ├── training/         # Isolation Forest training
│   ├── inference/        # ML inference
│   └── models/           # Trained model
│
├── docs/
│   ├── architecture/     # Architecture documentation
│   ├── images/           # System and dashboard visuals
│   ├── testing/          # Validation documentation
│   └── wiring/           # ESP32 hardware wiring
│
├── hardware/
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🧪 Testing & Validation

The repository includes structural tests covering monitoring-only firmware, dashboard configuration, and equipment-specific notifications.

Run the automated tests:

```bash
python -m unittest discover -s tests -v
```

Validate Python modules:

```bash
python -m compileall -q backend ml
```

**[View Testing & Validation Documentation](docs/testing/current_validation.md)**

The system is an educational prototype under integration testing. It is not intended as a safety-certified industrial control system.

---

## 🔮 Future Enhancements

- **Multi-Device Monitoring:** Dedicated ESP32 devices for equipment instances such as `MOTOR-01`, `FAN-01`, and `FAN-02`.
- **Secure Connectivity:** MQTT over TLS and individual device credentials.
- **Advanced ML:** Equipment-specific anomaly models and fault diagnostics.
- **SMS Alerts:** Critical-condition text notifications and escalation.
- **Cloud Scalability:** Containerization, automated deployment, and expanded Azure integration.
- **Fleet Dashboards:** Multi-equipment monitoring and centralized analytics.

---

## 👨‍💻 Developer

**Dhruvin Patel**  
Software Engineering — Ontario Tech University  
SOFE 4610U — Design of IoT | Fall 2026

**GitHub:** [github.com/dp0912](https://github.com/dp0912)

<div align="center">

---

### Built with ESP32 • Python • MQTT • Microsoft Azure • Grafana • Scikit-learn

*From real-time sensor acquisition to intelligent equipment monitoring.*

</div>
