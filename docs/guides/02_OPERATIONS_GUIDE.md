# Operations and Setup Guide

**Project:** IoT Equipment Condition Monitoring System
**Course:** SOFE 4610U — Fall 2026
**Environment:** MacBook Air (Apple Silicon), Docker Desktop, ESP32, Azure and Grafana

This guide describes the current Docker-based deployment.

## 1. First-Time Setup

### Clone the repository

```bash
git clone https://github.com/dp0912/IoT-Equipment-Condition-Monitoring-System.git
cd IoT-Equipment-Condition-Monitoring-System
```

### Configure environment variables

```bash
cp .env.example .env
```

Enter your actual MQTT, Azure, operator and optional SMTP settings in `.env`.

Do not commit the real `.env` file.

### Configure the ESP32

Open:

`firmware/esp32/equipment_monitor/equipment_monitor.ino`

Create the local `secrets.h` file beside the sketch with your Wi-Fi and MQTT credentials.

The ESP32 must connect to the Mac's current LAN IP on MQTT port 1883.

Select ESP32 Dev Module in Arduino IDE. Upload the firmware and open Serial Monitor at 115200 baud.

### Prepare Docker Volumes

The Compose configuration requires external volumes:

```bash
docker volume create iot-mqtt-secrets
docker volume create iot-grafana-data
docker volume create iot-grafana-config
```

The MQTT secrets volume must contain `/secrets/passwd`, readable by the Mosquitto container user.

The private Grafana config volume must contain `/grafana.ini`, corresponding to `/grafana-private/grafana.ini` in the container.

Creating an empty volume is not enough. Existing users should preserve their already configured volumes instead of recreating private settings.

The Compose-managed `mosquitto_data` volume stores MQTT persistence.

Never commit password files, Azure credentials, Grafana private settings or ESP32 secrets.

## 2. Daily Startup

Open Docker Desktop on the Mac.

From the repository root, run:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The four services should show `Up`:

- mosquitto
- subscriber
- api
- grafana

If Homebrew Mosquitto or Grafana is occupying the same ports, stop the conflicting services before starting Docker:

```bash
brew services stop mosquitto
brew services stop grafana
```

Docker uses these host ports:

| Service | Host port |
|---|---|
| Mosquitto | 1883 |
| Grafana | 3000 |
| Flask API | 5001, localhost only |

Inside Docker, the Python services connect to `mosquitto:1883`.

## 3. Verify the Monitoring Pipeline

### Check running services

```bash
docker compose ps
```

### Check sensor telemetry and processing

```bash
docker compose logs --tail=30 subscriber
```

Look for incoming measurements, SUMMARY generation, Isolation Forest inference and Azure write confirmations.

### Check API

```bash
curl http://127.0.0.1:5001/api/health
```

A healthy result should contain `status: OK` and `mqtt_connected: true`.

### Check Azure historical data

```bash
curl 'http://127.0.0.1:5001/api/history/summary?limit=2'
curl 'http://127.0.0.1:5001/api/history/events?limit=2'
```

### Open Grafana

Visit:

http://localhost:3000

The dashboard JSON is:

`dashboard/grafana/iot-equipment-live-dashboard.json`

Existing Grafana data is stored in the persistent volume. Fresh installations may require plugin, data source and dashboard configuration.

## 4. Troubleshooting

| Problem | What to check |
|---|---|
| Mosquitto not starting | Port 1883 conflicts, password file and Docker volume permissions |
| ESP32 not connecting | Wi-Fi, Mac LAN IP, broker port and MQTT credentials |
| No subscriber measurements | ESP32 status, MQTT broker and subscriber logs |
| Flask API restarting | API logs, imports, environment settings |
| No Azure history | Azure credentials, summary writes and history API |
| Grafana dashboard empty | MQTT/Infinity data sources, API, plugins and time range |
| Operator Apply fails | Session, CSRF, MQTT connection and ESP32 acknowledgement |
| Email not received | EMAIL_ENABLED, SMTP credentials, recipient and actual alert trigger |

Useful diagnostics:

```bash
docker compose logs --tail=50 mosquitto
docker compose logs --tail=50 subscriber
docker compose logs --tail=50 api
docker compose logs --tail=50 grafana
```

## 5. Safe Shutdown

From the project root:

```bash
docker compose down
```

This stops the four services and preserves named volumes.

If standalone Homebrew instances were started separately:

```bash
brew services stop mosquitto
brew services stop grafana
```

Do not use `docker compose down -v` for normal shutdown.

Unplug the ESP32 if its physical monitoring should also stop.


## Related Documentation

- [System Architecture](../architecture/system_architecture.md)
- [Technical Guide](01_TECHNICAL_GUIDE.md)
- [ESP32 Wiring](../wiring/esp32_wiring.md)
