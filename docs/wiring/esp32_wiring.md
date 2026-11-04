# ESP32 wiring — current monitoring-only setup

| Signal | ESP32 GPIO | Notes |
|---|---|---|
| DHT11 data | 27 | Common ground, supply according to breakout rating |
| MPU SDA | 21 | I²C |
| MPU SCL | 22 | I²C |
| Green LED | 25 | Series resistor, NORMAL |
| Yellow LED | 26 | Series resistor, WARNING |
| Red LED | 33 | Series resistor, CRITICAL |
| Alarm acknowledge button | 13 | Button between GPIO13 and GND; INPUT_PULLUP |
| Active buzzer/driver | 23 | Buzzer negative/common to GND |

Use a shared ground, avoid driving a high-current buzzer directly from GPIO, and disconnect power before rewiring. No physical machine is controlled; the eight equipment types are selectable **monitoring profiles**.
