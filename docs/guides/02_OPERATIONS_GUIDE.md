# Operations Guide — Current Azure Deployment

This guide documents the existing deployment.
It does not require another Grafana subscription or
a second Grafana dashboard.

## Components

- ESP32: physical sensors and local condition monitoring
- Azure Ubuntu VM: Docker Mosquitto, subscriber and Flask API
- Azure Table Storage: persistent history
- Mac: free Grafana OSS using Homebrew

## Azure backend

The Azure VM uses:

`compose.cloud.yaml`

Services:

- `mosquitto`
- `subscriber`
- `api`

The Compose services use `restart: unless-stopped`.

The existing cloud deployment can be managed from an
authenticated Azure SSH session using:

```bash
cd ~/IoT-Equipment-Condition-Monitoring-System
docker compose -f compose.cloud.yaml up -d --build
```

Do not start a second local subscriber on the Mac.
Duplicate subscribers could duplicate historical writes
and email alerts.

## Private files required on Azure

- `.env` — MQTT, Azure, operator and email configuration
- `cloud-private/mqtt-certs/server.crt`
- `cloud-private/mqtt-certs/server.key`
- `cloud-private/mqtt-secrets/passwd`

Never commit these private files.

The root CA certificate used by Grafana and the ESP32
must correspond to the CA that signed the MQTT server
certificate.

## ESP32 configuration

Firmware:

`firmware/esp32/equipment_monitor/equipment_monitor.ino`

Private header:

`firmware/esp32/equipment_monitor/secrets.h`

The MQTT hostname is:

`iot-monitor-dp0912.northcentralus.cloudapp.azure.com`

Remote MQTT uses TLS on port 8883.

The firmware uses WiFiManager for network onboarding.

To manually open Wi-Fi configuration, enter `W` in
Arduino Serial Monitor at 115200 baud.

Connect a computer to `EquipmentMonitor-Setup`, open
`http://192.168.4.1`, and configure the desired Wi-Fi.

Manual setup is required when switching between different
networks; multiple-network automatic roaming is not implemented.

## Start Grafana on the Mac

```bash
brew services start grafana
```

Dashboard:

`http://localhost:3000`

The existing MQTT data source connects directly to Azure
using TLS and CA verification.

Keep the existing data sources and single dashboard.

## Access the Azure API from the Mac

Open a separate Mac Terminal session:

```bash
ssh -o ExitOnForwardFailure=yes -N   -L 127.0.0.1:5001:127.0.0.1:5001   azureuser@iot-monitor-dp0912.northcentralus.cloudapp.azure.com
```

Leave this terminal session open while using historical
data and operator controls.

The Infinity data source and Business Forms use the
local API address `http://127.0.0.1:5001`.

The SSH tunnel does not make the API public.

## Grafana time ranges

For live monitoring, use Last 15 minutes.

For historical analysis, use Last 7 days or an absolute
time range. Zooming an old historical graph changes the
time range for all panels, including live MQTT panels.

To return to live monitoring, select Last 15 minutes again.

## Credentials and security

Keep `.env`, `secrets.h`, the Mosquitto password file,
and private certificate keys out of GitHub.

Rotate previously exposed passwords across every component
that uses them. Update the broker, ESP32, subscriber, API
and Grafana consistently.

The root CA certificate can be distributed to trusted MQTT
clients; its private signing key must remain private.

## Cost

Grafana OSS is free to self-host.

The Azure VM and Azure Storage may incur Azure charges
depending on the subscription and usage.

The current dashboard remains on the Mac.
No Azure Managed Grafana service is used.

## Current limitations

- One active physical sensing device
- Manual Wi-Fi reconfiguration between networks
- Occasional DHT11 reading faults
- No SMS integration yet
- No publicly hosted Grafana dashboard
- Not intended for certified industrial safety applications
