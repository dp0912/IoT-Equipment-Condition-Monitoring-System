# ESP32 Hardware Wiring Documentation

## ESP32 GPIO Connections

| Component | ESP32 GPIO | Description |
|---|---|---|
| DHT11 | GPIO27 | Temperature and humidity data |
| MPU6500 SDA | GPIO21 | I2C data |
| MPU6500 SCL | GPIO22 | I2C clock |
| Green LED | GPIO25 | Normal indicator |
| Yellow LED | GPIO26 | Warning indicator |
| Red LED | GPIO33 | Critical indicator |
| Active Buzzer | GPIO23 | Audible alerts |
| IR Receiver | GPIO32 | IR remote commands |
| Push Button | GPIO13 | Emergency stop/reset |
| L293D Enable | GPIO4 | Motor enable |
| L293D IN1 | GPIO2 | Motor direction control |
| L293D IN2 | GPIO15 | Motor direction control |
| SN74HC595 SER | GPIO18 | Serial data |
| SN74HC595 SRCLK | GPIO19 | Shift clock |
| SN74HC595 RCLK | GPIO5 | Latch clock |

## L293D Motor Connections

| L293D Pin | Connection |
|---|---|
| 1 | ESP32 GPIO4 |
| 2 | ESP32 GPIO2 |
| 3 | DC motor red wire |
| 4 | Common GND |
| 5 | Common GND |
| 6 | DC motor black wire |
| 7 | ESP32 GPIO15 |
| 8 | External regulated 5V motor supply |
| 12 | Common GND |
| 13 | Common GND |
| 16 | Regulated 5V logic supply |

## SN74HC595 Connections

| SN74HC595 Pin | Connection |
|---|---|
| 8 | GND |
| 10 | 3.3V |
| 11 | ESP32 GPIO19 |
| 12 | ESP32 GPIO5 |
| 13 | GND |
| 14 | ESP32 GPIO18 |
| 16 | 3.3V |

The SN74HC595 controls the LCD1602 in 4-bit parallel mode.

## LCD1602 Power

- LCD VCC: regulated 5V
- LCD GND: common GND
- LCD RW: GND
- LCD contrast: potentiometer
- LCD control/data: SN74HC595 outputs

## Power Distribution

ESP32:
- Powered by USB
- Supplies 3.3V to compatible peripherals

ELEGOO MB V2:
- Supplies regulated 5V for LCD and L293D
- LCD and motor use separate 5V wiring branches
- Grounds remain common

## Important Troubleshooting Finding

Initial problem:
LCD went blank whenever the DC motor started.

Observation:
ESP32 continued running and printing sensor telemetry.

Resolution:
Separated the motor-driver 5V supply wiring from the LCD 5V supply wiring.

Result:
LCD continued functioning while the motor was running.

Note:
The two branches may still share the ELEGOO module's internal regulator.

## Safety Notes

- Never connect 5V to the ESP32 3.3V rail.
- Never connect the DC motor directly to an ESP32 GPIO.
- Keep a common ground between controller and motor driver.
- Disconnect power before modifying wiring.
- GPIO2 and GPIO15 are ESP32 boot-strapping pins.
- The software emergency stop is not a certified safety-rated circuit.
