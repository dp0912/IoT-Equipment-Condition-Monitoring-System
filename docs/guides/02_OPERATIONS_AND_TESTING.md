# Operations, Setup, Troubleshooting and Validation
## Runbook · SOFE 4610U · 4 November 2026

**Repository:** https://github.com/dp0912/IoT-Equipment-Condition-Monitoring-System  
**Environment:** macOS (Apple Silicon/Homebrew), VS Code, Arduino IDE, ESP32, local Mosquitto and Grafana. Run commands at repository root unless stated otherwise.

## 1. First-time configuration

**Get the code and Python dependencies:**

```bash
git clone https://github.com/dp0912/IoT-Equipment-Condition-Monitoring-System.git
cd IoT-Equipment-Condition-Monitoring-System
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

**Configure `.env` privately:** Set the actual MQTT broker's reachable host and matching username/password. For the local Flask control, set `CONTROL_USERNAME`, strong `CONTROL_PASSWORD` (12+ characters), random `CONTROL_SESSION_SECRET` (32+ characters), and permitted `CONTROL_ALLOWED_ORIGINS`. Configure the Azure Table Storage variables expected by `backend/azure/storage.py` and `backend/azure/query_history.py` using your valid Azure connection settings. Email is optional; enabling it requires SMTP host, port, sending address, app password, and recipient. `.env.example` is a template, not a working secret file. Never commit `.env`.

**Firmware:** Open `firmware/esp32/equipment_monitor/equipment_monitor.ino` in Arduino IDE. Create the private `secrets.h` used by the sketch with your Wi-Fi and MQTT credentials (match its actual required symbol names). Install ESP32 board package and the required Arduino libraries `DHT`, `PubSubClient`, and `ArduinoJson`; `Wire` and `Preferences` are part of the ESP32 toolchain. Select **ESP32 Dev Module** and the correct USB serial port. Upload and use Serial Monitor at **115200 baud**. Do not change working GPIO connections while energized.

**Broker:** Mosquitto is installed/configured separately. On an Apple Silicon Mac, broker configuration is commonly at `/opt/homebrew/etc/mosquitto/mosquitto.conf`; authentication password files must be secured. Configure a listener reachable from the ESP32 LAN, require authentication, and keep port 1883 off the public internet. If the Mac IP changes, align the broker listener, `.env`, and ESP32 secrets. Avoid starting a second broker when port 1883 is already occupied.

**Grafana:** Install or start Grafana with Homebrew, then import `dashboard/grafana/iot-equipment-live-dashboard.json`. Match MQTT and Infinity datasource identifiers to your local installation. Install the plugins required by actual panels (MQTT datasource, Infinity datasource, Business Forms and Business Text/Dynamic Text). Business Forms login and thresholds depend on the local Flask API being alive. The illustrative `docs/images/*.png` images are for README presentation, not functioning dashboards.

## 2. Daily startup — correct sequence

**Terminal A — broker check**

```bash
brew services start mosquitto
lsof -nP -iTCP:1883 -sTCP:LISTEN
```

**Terminal B — Python subscriber (leave running)**

```bash
source .venv/bin/activate
python backend/mqtt/subscriber.py
```

This consumes MQTT messages, produces Azure SUMMARY/EVENT uploads, ML results, equipment alerts, connectivity state and email messages when enabled.

**Terminal C — single Flask History + Control API (leave running)**

```bash
source .venv/bin/activate
python backend/azure/history_api.py
```

No extra `control_api.py` server is needed. The same Flask process provides historical endpoints and authenticated configuration controls on `127.0.0.1:5001`.

**Terminal D — Grafana**

```bash
brew services start grafana
```

Visit `http://localhost:3000`. Plug the ESP32 into USB and verify it connects to Wi-Fi and MQTT. Local sensor state can continue without a browser, but Azure, ML, email and dashboards need their respective processes running.

## 3. Quick checks

```bash
# Flask alive and MQTT control connection state
curl -s http://127.0.0.1:5001/api/health

# Latest stored Azure records (when credentials and data are available)
curl -s 'http://127.0.0.1:5001/api/history/summary?limit=2'
curl -s 'http://127.0.0.1:5001/api/history/events?limit=2'

# Source and tests; run from repository root
python -m compileall -q backend ml
python -m unittest discover -s tests -v
python -m json.tool dashboard/grafana/iot-equipment-live-dashboard.json > /dev/null
```

For a broker subscription, use valid credentials without saving them in shell history. Example using interactive password entry in `zsh` (replace host with your broker address):

```bash
read -s 'MQTT_PASS?MQTT password: '; echo
mosquitto_sub -h 127.0.0.1 -p 1883 -u esp32_monitor \
  -P "$MQTT_PASS" -t 'equipment/ESP32-001/telemetry' -C 1 -W 15
unset MQTT_PASS
```

If the broker is bound only to a LAN interface rather than loopback, replace `127.0.0.1` accordingly. A failed subscription is not proof the ESP32 or data source is broken; first confirm the listener, IP, credentials and publish topic.

## 4. What the operator should see

**Live:** Current temperature/humidity/vibration, NORMAL/WARNING/CRITICAL, ONLINE/OFFLINE, sensor health, equipment profile, confirmed thresholds, audible alarm acknowledgement, transition events and ML score/state.

**Historical:** SUMMARY trends and EVENT records from Azure within selected dates. Historical panels require an operational subscriber, Azure credentials/storage and Flask history API; empty panels may simply mean no saved data for that period.

**Configuration:** Sign in through the dashboard's operator form, select one of eight equipment profiles or edit valid warning/critical thresholds, press Apply, and verify ESP32 `APPLIED` acknowledgement plus an updated `config` MQTT publication. A failed request or timeout does not certify an applied change. The GPIO13 button (or authorized alarm acknowledgement command, when available) silences the critical buzzer while leaving the actual condition unchanged.

## 5. Essential troubleshooting

| Symptom | Check first |
|---|---|
| No serial/sensor measurements | USB serial port, 115200 baud, DHT GPIO27, MPU SDA21/SCL22, sensor power/common ground |
| Buzzer silent in CRITICAL | GPIO23 and buzzer GND, suitable driver/rating, active condition, acknowledgement state |
| No MQTT telemetry | ESP32 Wi-Fi, broker listener IP:1883, authentication, `telemetry` topic, Mac IP changed |
| Broker not starting | `lsof` for another process already using port 1883; Mosquitto config/service log |
| Grafana live empty | MQTT datasource connection, exact topic, ESP32 messages, query transformations |
| Grafana history empty | Flask `/api/health`, Azure `/api/history/*`, saved data in range, Infinity datasource |
| Operator Apply fails | Session expiry, CSRF token, strong control secrets, control MQTT status, ESP32 command ACK |
| No email | `EMAIL_ENABLED`, SMTP credentials/app password, recipient, actual state transition, subscriber running |
| No ML data | Model file present, valid 30-second summary windows, subscriber log and `/ml` topic |
| Device falsely OFFLINE | Actual telemetry gaps, Wi-Fi dropout, backend blocking, freshness timeout (~10 seconds) |

## 6. Final acceptance checklist — rerun on current build

| ID | Test | Expected evidence | Status |
|---|---|---|---|
| T01 | Compile/upload current firmware | Arduino IDE successful build + serial readings | NOT REVALIDATED |
| T02 | DHT + MPU and sensor fault handling | Valid values; health flags change when sensor unavailable | NOT REVALIDATED |
| T03 | Local NORMAL / WARNING / CRITICAL | Correct LED; CRITICAL audible 200/800ms pattern | NOT REVALIDATED |
| T04 | Physical alarm acknowledgement | Button silences buzzer; CRITICAL condition remains | NOT REVALIDATED |
| T05 | All eight equipment profiles | Selected profile and confirmed values update | NOT REVALIDATED |
| T06 | Authorized threshold editing | Flask response matches ESP32 ACK; retained config updated | NOT REVALIDATED |
| T07 | Unauthenticated/invalid control | Invalid login/CSRF/threshold rejected; no ESP32 apply | NOT REVALIDATED |
| T08 | Live MQTT + Grafana | Sensor, status, condition, health, config and alert panels | NOT REVALIDATED |
| T09 | Azure + History API | SUMMARY and EVENT records; query/graph by date | NOT REVALIDATED |
| T10 | ML inference | 30-second window produces model label and score | NOT REVALIDATED |
| T11 | Email state transitions | WARNING/CRITICAL/RECOVERY include equipment profile | NOT REVALIDATED |
| T12 | Network / device interruption | OFFLINE then ONLINE events and optional email | NOT REVALIDATED |
| T13 | Automated code checks | Python compile, unittests, dashboard JSON valid | RERUN AFTER CHANGES |

**Reporting rule:** Record actual date/time, environment, steps, expected result, observed result, outcome and sanitized evidence. The earlier three structural tests passed before a previous cleanup, but that does **not** establish all hardware/cloud cases passed on the final version. Do not use the illustrative Grafana picture as test evidence.

## 7. Shutdown and version control

Stop subscriber and Flask terminals with `Control+C`. Optionally stop local services if not needed:

```bash
brew services stop grafana
brew services stop mosquitto
```

The ESP32 can be unplugged after the demonstration. Pending in-memory Azure/email jobs may not survive abrupt shutdown, so check for queued output first. To publish documentation after reviewing it:

```bash
git status --short
git add docs
# Review the staged changes before committing:
git diff --cached --stat
git commit -m 'docs: consolidate current IoT technical and operations guides'
git push origin main
```

For detailed pin connections, refer to `docs/wiring/esp32_wiring.md`. For a concise public summary, refer to `README.md`. No separate old motor/LCD/IR or preliminary MQTT-only documents are required for this current implementation.
