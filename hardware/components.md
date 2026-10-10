# Hardware Components

## Project
IoT-Based Configurable Multi-Sensor Equipment Condition Monitoring System with AI/ML Integration

## Hardware Inventory

| Component | Purpose |
|---|---|
| ESP32 DevKit | Main microcontroller and future Wi-Fi/MQTT communication |
| DHT11 | Ambient temperature and humidity measurement |
| MPU6500 | Three-axis acceleration and vibration monitoring |
| LCD1602 | Local equipment monitoring display |
| SN74HC595N | Shift register for LCD control |
| L293D | DC motor driver |
| DC Motor with Fan | Simulated rotating equipment |
| IR Receiver | Infrared remote input |
| ELEGOO IR Remote | Local control and threshold configuration |
| Push Button | Emergency-stop and reset input |
| Green LED | Normal condition |
| Yellow LED | Warning condition |
| Red LED | Critical condition |
| Active Buzzer | Audible condition alerts |
| ELEGOO MB V2 Power Module | External 5V supply distribution |
| ESP32 USB Supply | ESP32 and 3.3V peripherals |
| Breadboard and Jumper Wires | Circuit assembly and interconnections |

## Current Hardware Status

All listed hardware components have been integrated and tested.

The fan supports continuous ON/OFF operation.

The LCD operates while the fan is running after separating the motor and LCD 5V supply wiring branches.

## Next Development Stage

- ESP32 Wi-Fi connectivity
- MQTT telemetry publishing
- Local Mosquitto broker
- Dashboard and cloud integration
- Remote notifications
- AI/ML anomaly detection
