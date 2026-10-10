# Hardware Integration Test Results

## Firmware

File: firmware/esp32/equipment_monitor/equipment_monitor.ino

Version: Hardware Integration v1.0

Git Commit: 984e7d3

## Hardware Test Results

| Test | Result |
|---|---|
| ESP32 startup | PASS |
| DHT11 temperature | PASS |
| DHT11 humidity | PASS |
| MPU6500 vibration | PASS |
| Green LED | PASS |
| Yellow LED | PASS |
| Red LED | PASS |
| Active buzzer | PASS |
| IR receiver | PASS |
| Physical push button | PASS |
| LCD1602 display | PASS |
| LCD navigation | PASS |
| Five LCD pages | PASS |
| DC motor ON | PASS |
| DC motor OFF | PASS |
| Continuous motor operation | PASS |
| Motor control using remote | PASS |
| Motor control using Serial Monitor | PASS |
| Emergency stop | PASS |
| Emergency stop reset | PASS |
| Configurable thresholds | PASS |
| LCD stability during fan operation | PASS |

## Serial Monitor Commands

| Command | Function |
|---|---|
| P | Print system status |
| T | Print thresholds |
| ? | Print help |
| N | Simulate NORMAL |
| W | Simulate WARNING |
| C | Simulate CRITICAL |
| A | Automatic monitoring |
| M | Arm motor |
| F | Fan ON continuously |
| O | Fan OFF |
| X | Emergency stop |
| R | Reset emergency stop |

Serial baud rate: 115200

## IR Remote Controls

| Button | Hex Code | Function |
|---|---|---|
| POWER | 0x45 | Emergency stop |
| VOL+ | 0x46 | Increase buzzer pattern |
| FUNC/STOP | 0x47 | Automatic monitoring |
| PREV | 0x44 | Previous LCD page |
| PLAY/PAUSE | 0x40 | Toggle fan |
| NEXT | 0x43 | Next LCD page |
| DOWN | 0x07 | Decrease threshold |
| VOL- | 0x15 | Decrease buzzer pattern |
| UP | 0x09 | Increase threshold |
| 0 | 0x16 | Temperature/humidity page |
| EQ | 0x19 | Warning/critical threshold selection |
| ST/REPT | 0x0D | Reset emergency stop |
| 1 | 0x0C | Simulate NORMAL |
| 2 | 0x18 | Simulate WARNING |
| 3 | 0x5E | Simulate CRITICAL |
| 4 | 0x08 | Arm motor |
| 5 | 0x1C | Fan ON continuously |
| 6 | 0x5A | Fan OFF |
| 7 | 0x42 | Select temperature threshold |
| 8 | 0x52 | Select humidity threshold |
| 9 | 0x4A | Select vibration threshold |

## LCD Pages

1. Temperature and humidity
2. Vibration and equipment condition
3. Fan status and operating mode
4. Buzzer setting and IR/button status
5. Configurable sensor thresholds

## Motor and LCD Troubleshooting

Problem:
LCD became blank when the motor started.

Cause suspected:
Shared supply wiring, voltage disturbance or motor electrical noise.

Fix:
Separated motor and LCD 5V supply wiring branches.

Verification:
Motor operates while LCD remains readable.

## Project Status

Local hardware integration has been tested successfully.

Wi-Fi, MQTT, cloud integration, dashboard and AI/ML remain future development tasks.
