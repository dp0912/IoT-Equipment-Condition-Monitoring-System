# Current prototype validation checklist

**Historical note:** Previously recorded LCD, motor and IR tests belong to a removed prototype and are not evidence for the current monitoring-only build. Mark checks below PASS only after rerunning them on the final firmware and services.

- [ ] Arduino IDE compiles and uploads `equipment_monitor.ino`
- [ ] DHT11 ambient temperature/humidity and MPU vibration readings received
- [ ] Green/yellow/red LEDs respond to NORMAL/WARNING/CRITICAL thresholds
- [ ] Buzzer beeps on CRITICAL; GPIO13 button mutes it without clearing severity
- [ ] MQTT telemetry, sensor health, control status and confirmed config received
- [ ] Operator sign-in, profile Apply and threshold Apply return ESP32 acknowledgement
- [ ] Python subscriber publishes alerts/ML and stores Azure SUMMARY/EVENT data
- [ ] WARNING/CRITICAL/RECOVERY email includes selected equipment profile
- [ ] Grafana live and Azure historic panels show valid data
- [ ] Device OFFLINE/ONLINE state is handled after a disconnect/restart
