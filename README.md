# IoT Equipment Condition Monitoring System

An ESP32-based IoT system for real-time equipment condition monitoring using vibration and environmental sensors, configurable thresholds, MQTT communication, and AI/ML-based anomaly detection.

**Course:** SOFE 4610U — Design & Analysis of IoT  
**University:** Ontario Tech University  
**Status:** In Development | Fall 2026

## Overview

This project develops a low-cost industrial equipment monitoring prototype using a DC motor and fan. The ESP32 collects vibration, temperature, and humidity data, evaluates operating conditions, and provides local alerts. MQTT enables remote monitoring, historical analysis, and planned AI/ML-based anomaly detection.

## Key Features

- Real-time vibration, ambient temperature, and humidity monitoring
- Configurable thresholds and equipment profiles
- Condition classification: **NORMAL, WARNING, CRITICAL**
- LCD display, keypad, IR remote, LEDs, and buzzer
- ESP32-controlled DC motor demonstration
- MQTT telemetry and cloud dashboard
- Email/SMS notifications and device-offline alerts
- AI/ML-based anomaly detection

_Features are planned and will be implemented incrementally._

## Technology Stack

| Category        | Technologies                          |
| --------------- | ------------------------------------- |
| Hardware        | ESP32, MPU6500, DHT11, L293D, LCD1602 |
| Firmware        | C/C++, Arduino IDE                    |
| Communication   | Wi-Fi, MQTT, Mosquitto                |
| Backend & AI/ML | Python, scikit-learn                  |
| Cloud           | Microsoft Azure (planned)             |
| Development     | VS Code, Git, GitHub                  |

## Repository Structure

```text
firmware/     ESP32 firmware
backend/      MQTT and backend services
dashboard/    Monitoring interface
ml/           Anomaly detection
hardware/     Hardware documentation
docs/         Architecture, wiring, and testing
```

## Project Information

**Institution:** Ontario Tech University  
**Academic Term:** Fall 2026  
**Purpose:** Academic IoT prototype and equipment condition monitoring demonstration

---

_Developed for SOFE 4610U — Design & Analysis of IoT._
