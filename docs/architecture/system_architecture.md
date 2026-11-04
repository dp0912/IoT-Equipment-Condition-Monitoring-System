# Current monitoring-only architecture

```text
ESP32 (DHT11 + MPU6050/6500; LEDs + buzzer + ACK button)
  | MQTT telemetry / config / sensor-health / status
  v
Mosquitto broker
  |-- Grafana live MQTT panels
  |-- Python subscriber -- 30s aggregation -- Azure Table Storage
  |                                      |
  |                                      `-- Flask History API -> Grafana Azure history
  |-- Python ML inference -> MQTT ml -> Grafana ML panel
  `-- Email notifications (WARNING/CRITICAL/RECOVERY)

Grafana operator form -> Flask Control API -> MQTT commands
ESP32 -> MQTT command_ack + config -> Flask / Grafana
```

All eight types are selectable ESP32 monitoring profiles, not eight simultaneously connected machines.
