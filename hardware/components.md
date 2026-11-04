# Current hardware (monitoring-only prototype)

| Component | Connection | Purpose |
|---|---|---|
| ESP32-WROOM-32 | USB power | Sensor sampling and MQTT |
| DHT11 | Data GPIO27; 3.3V and GND per module rating | Ambient temperature and humidity |
| MPU6050/MPU6500 | SDA GPIO21, SCL GPIO22; 3.3V and GND per module rating | Acceleration-derived vibration RMS |
| Green LED + resistor | GPIO25 | NORMAL |
| Yellow LED + resistor | GPIO26 | WARNING |
| Red LED + resistor | GPIO33 | CRITICAL |
| Physical push button | GPIO13 to GND, internal pull-up | Silence/acknowledge critical buzzer |
| Active buzzer (or suitable driver) | GPIO23 output, GND return | Critical alarm, 200 ms ON/800 ms OFF |

Each LED requires its own appropriate current-limiting resistor. Confirm the buzzer's voltage/current rating before connecting to a GPIO; use a transistor driver if needed. **No motor, motor driver, LCD, IR remote, or sound sensor is installed.**
