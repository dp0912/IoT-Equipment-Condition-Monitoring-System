
/*
 * SOFE 4610U — IoT Equipment Condition Monitoring
 * Monitoring-only rebuild
 *
 * Board: ESP32-WROOM-32 DevKit
 * Arduino IDE board: ESP32 Dev Module
 *
 * Hardware:
 * DHT11: GPIO27
 * MPU6050/MPU6500: SDA21, SCL22
 * Green LED: GPIO25
 * Yellow LED: GPIO26
 * Red LED: GPIO33
 * Button: GPIO13 to GND
 * Active buzzer: GPIO23
 *
 * CRITICAL buzzer: 200 ms ON / 800 ms OFF
 * Physical button acknowledges and silences the alarm.
 *
 * No physical motor, LCD, remote or sound sensor.
 *
 * Educational demonstration, not a safety-certified system.
 */

#include <Arduino.h>
#include <Wire.h>
#include <DHT.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <math.h>
#include <time.h>
#include "secrets.h"

// ============================================================
// 1. HARDWARE
// ============================================================

constexpr int PIN_DHT = 27;
constexpr int PIN_SDA = 21;
constexpr int PIN_SCL = 22;

constexpr int PIN_GREEN = 25;
constexpr int PIN_YELLOW = 26;
constexpr int PIN_RED = 33;

constexpr int PIN_BUTTON = 13;
constexpr int PIN_BUZZER = 23;

// Requires a GPIO-compatible active buzzer or suitable driver.
constexpr bool BUZZER_ENABLED = true;

constexpr unsigned long BUZZER_ON_MS = 200;
constexpr unsigned long BUZZER_PERIOD_MS = 1000;

DHT dht(PIN_DHT, DHT11);

// ============================================================
// 2. MQTT
// ============================================================

constexpr char DEVICE_ID[] = "ESP32-001";

constexpr char TOPIC_TELEMETRY[] =
    "equipment/ESP32-001/telemetry";

constexpr char TOPIC_STATUS[] =
    "equipment/ESP32-001/status";

constexpr char TOPIC_CONFIG[] =
    "equipment/ESP32-001/config";

constexpr char TOPIC_HEALTH[] =
    "equipment/ESP32-001/sensor_health";

constexpr char TOPIC_CONTROL[] =
    "equipment/ESP32-001/control_status";

constexpr char TOPIC_COMMAND[] =
    "equipment/ESP32-001/commands";

constexpr char TOPIC_ACK[] =
    "equipment/ESP32-001/command_ack";

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

Preferences prefs;

unsigned long lastWiFiTry = 0;
unsigned long lastMQTTTry = 0;
unsigned long lastTelemetry = 0;
unsigned long lastStatus = 0;

// ============================================================
// 3. EQUIPMENT PROFILES
// ============================================================

struct Limits {
  float criticalLow;
  float warningLow;
  float warningHigh;
  float criticalHigh;
};

struct Profile {
  const char *name;
  Limits temperature;
  Limits humidity;
  Limits vibration;
};

// Demonstration limits, not calibrated machinery standards.
// DHT11 measures ambient rather than internal temperatures.

const Profile PROFILES[] = {

  {
    "MOTOR",
    {0, 10, 60, 70},
    {20, 30, 75, 90},
    {0, 0, 1.0f, 3.0f}
  },

  {
    "PUMP",
    {0, 10, 55, 65},
    {20, 30, 80, 95},
    {0, 0, 0.8f, 2.5f}
  },

  {
    "COMPRESSOR",
    {0, 10, 50, 60},
    {20, 30, 70, 85},
    {0, 0, 1.2f, 3.2f}
  },

  {
    "FAN",
    {0, 10, 45, 55},
    {20, 30, 75, 90},
    {0, 0, 0.6f, 2.0f}
  },

  {
    "CONDENSER",
    {0, 10, 40, 50},
    {20, 30, 80, 95},
    {0, 0, 1.5f, 3.5f}
  },

  {
    "HEAT_EXCHANGER",
    {0, 10, 42, 52},
    {20, 30, 80, 95},
    {0, 0, 1.5f, 3.5f}
  },

  {
    "AHU",
    {0, 10, 38, 48},
    {20, 30, 75, 90},
    {0, 0, 0.7f, 2.2f}
  },

  {
    "CHILLER",
    {0, 10, 40, 50},
    {20, 30, 80, 95},
    {0, 0, 0.9f, 2.6f}
  }
};

constexpr int PROFILE_COUNT =
    sizeof(PROFILES) / sizeof(PROFILES[0]);

// 0 = Temperature
// 1 = Humidity
// 2 = Vibration
Limits limits[3];

int profileIndex = 0;

// ============================================================
// 4. SENSOR STATE
// ============================================================

float temperatureC = NAN;
float humidity = NAN;
float vibrationRMS = NAN;

bool dhtValid = false;
bool vibrationValid = false;
bool mpuReady = false;

uint8_t mpuAddress = 0x68;

enum Severity {
  NORMAL = 0,
  WARNING = 1,
  CRITICAL = 2
};

Severity severity = WARNING;

const char *severityName(Severity s) {
  if (s == CRITICAL) return "CRITICAL";
  if (s == WARNING) return "WARNING";
  return "NORMAL";
}

bool buzzerAcknowledged = false;

bool lastButton = HIGH;
unsigned long lastButtonChange = 0;

String recentIds[12];
uint8_t recentIndex = 0;

// ============================================================
// 5. PROFILE CONFIGURATION
// ============================================================

void loadProfile(int index) {

  profileIndex = index;

  limits[0] = PROFILES[index].temperature;
  limits[1] = PROFILES[index].humidity;
  limits[2] = PROFILES[index].vibration;
}

bool goodLimits(int metric, Limits v) {

  if (!isfinite(v.warningHigh) ||
      !isfinite(v.criticalHigh)) {
    return false;
  }

  // Vibration uses high limits only.
  if (metric == 2) {

    return v.warningHigh >= 0 &&
           v.warningHigh < v.criticalHigh &&
           v.criticalHigh <= 200;
  }

  if (!isfinite(v.criticalLow) ||
      !isfinite(v.warningLow)) {
    return false;
  }

  if (!(v.criticalLow < v.warningLow &&
        v.warningLow < v.warningHigh &&
        v.warningHigh < v.criticalHigh)) {
    return false;
  }

  if (metric == 0) {
    return v.criticalLow >= -40 &&
           v.criticalHigh <= 80;
  }

  return v.criticalLow >= 0 &&
         v.criticalHigh <= 100;
}

// Save the active profile and thresholds in ESP32 memory.
void saveSettings() {

  prefs.putUChar("profile", profileIndex);

  for (int i = 0; i < 3; ++i) {

    char key[12];

    snprintf(key, sizeof(key), "limit%d", i);

    prefs.putBytes(
      key,
      &limits[i],
      sizeof(Limits)
    );
  }
}

// Restore settings after restart.
void restoreSettings() {

  prefs.begin("monitor-v3", false);

  int index = prefs.getUChar("profile", 0);

  if (index >= PROFILE_COUNT) {
    index = 0;
  }

  loadProfile(index);

  for (int i = 0; i < 3; ++i) {

    char key[12];

    snprintf(key, sizeof(key), "limit%d", i);

    Limits stored;

    if (
      prefs.getBytesLength(key) == sizeof(Limits) &&
      prefs.getBytes(
        key,
        &stored,
        sizeof(Limits)
      ) == sizeof(Limits) &&
      goodLimits(i, stored)
    ) {
      limits[i] = stored;
    }
  }
}

// ============================================================
// 6. MPU6050 / MPU6500 COMMUNICATION
// ============================================================

bool readRegisters(
  uint8_t address,
  uint8_t reg,
  uint8_t *buffer,
  uint8_t count
) {

  Wire.beginTransmission(address);
  Wire.write(reg);

  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (
    Wire.requestFrom(
      (int)address,
      (int)count
    ) != count
  ) {
    return false;
  }

  for (uint8_t i = 0; i < count; ++i) {
    buffer[i] = Wire.read();
  }

  return true;
}

bool writeRegister(
  uint8_t address,
  uint8_t reg,
  uint8_t value
) {

  Wire.beginTransmission(address);
  Wire.write(reg);
  Wire.write(value);

  return Wire.endTransmission() == 0;
}

void initializeMPU() {

  mpuReady = false;

  for (
    uint8_t addr :
    {uint8_t(0x68), uint8_t(0x69)}
  ) {

    uint8_t id;

    if (
      readRegisters(addr, 0x75, &id, 1) &&
      (id == 0x70 || id == 0x68)
    ) {

      mpuAddress = addr;

      mpuReady =
          writeRegister(addr, 0x6B, 0x00) &&
          writeRegister(addr, 0x1C, 0x00);

      Serial.printf(
        "MPU 0x%02X WHO_AM_I=0x%02X ready=%d\n",
        addr,
        id,
        mpuReady
      );

      return;
    }
  }

  Serial.println(
    "MPU not detected; vibration invalid"
  );
}

// ============================================================
// 7. SENSOR READINGS
// ============================================================

void sampleSensors() {

  float t = dht.readTemperature();
  float h = dht.readHumidity();

  dhtValid =
      isfinite(t) &&
      isfinite(h) &&
      t >= -40 &&
      t <= 80 &&
      h >= 0 &&
      h <= 100;

  temperatureC = dhtValid ? t : NAN;
  humidity = dhtValid ? h : NAN;

  vibrationValid = false;
  vibrationRMS = NAN;

  if (!mpuReady) {
    initializeMPU();
  }

  if (!mpuReady) {
    return;
  }

  // Remove mean acceleration from 16 samples
  // to estimate vibration.

  float ax[16], ay[16], az[16];

  float mx = 0;
  float my = 0;
  float mz = 0;

  for (int i = 0; i < 16; ++i) {

    uint8_t b[6];

    if (
      !readRegisters(
        mpuAddress,
        0x3B,
        b,
        6
      )
    ) {
      mpuReady = false;
      return;
    }

    int16_t x =
      (int16_t)((uint16_t(b[0]) << 8) | b[1]);

    int16_t y =
      (int16_t)((uint16_t(b[2]) << 8) | b[3]);

    int16_t z =
      (int16_t)((uint16_t(b[4]) << 8) | b[5]);

    ax[i] = x * (9.80665f / 16384.0f);
    ay[i] = y * (9.80665f / 16384.0f);
    az[i] = z * (9.80665f / 16384.0f);

    mx += ax[i];
    my += ay[i];
    mz += az[i];

    delay(3);
  }

  mx /= 16;
  my /= 16;
  mz /= 16;

  float sq = 0;

  for (int i = 0; i < 16; ++i) {

    float x = ax[i] - mx;
    float y = ay[i] - my;
    float z = az[i] - mz;

    sq += x*x + y*y + z*z;
  }

  vibrationRMS = sqrtf(sq / 16.0f);

  vibrationValid = isfinite(vibrationRMS);
}

// ============================================================
// 8. EQUIPMENT CONDITION
// ============================================================

Severity classifyOne(
  float value,
  Limits l,
  bool lowEnabled
) {

  if (
    (lowEnabled && value <= l.criticalLow) ||
    value >= l.criticalHigh
  ) {
    return CRITICAL;
  }

  if (
    (lowEnabled && value <= l.warningLow) ||
    value >= l.warningHigh
  ) {
    return WARNING;
  }

  return NORMAL;
}

void updateCondition() {

  Severity next = NORMAL;

  if (!dhtValid || !vibrationValid) {
    next = WARNING;
  }

  if (dhtValid) {

    next = max(
      next,
      classifyOne(
        temperatureC,
        limits[0],
        true
      )
    );

    next = max(
      next,
      classifyOne(
        humidity,
        limits[1],
        true
      )
    );
  }

  if (vibrationValid) {

    next = max(
      next,
      classifyOne(
        vibrationRMS,
        limits[2],
        false
      )
    );
  }

  if (next != severity) {
    buzzerAcknowledged = false;
  }

  severity = next;

  digitalWrite(
    PIN_GREEN,
    severity == NORMAL ? HIGH : LOW
  );

  digitalWrite(
    PIN_YELLOW,
    severity == WARNING ? HIGH : LOW
  );

  digitalWrite(
    PIN_RED,
    severity == CRITICAL ? HIGH : LOW
  );
}

// ============================================================
// 9. BUZZER
// ============================================================

void updateBuzzer() {

  if (!BUZZER_ENABLED) {
    return;
  }

  if (
    severity != CRITICAL ||
    buzzerAcknowledged
  ) {

    digitalWrite(PIN_BUZZER, LOW);
    return;
  }

  // 200 ms ON, 800 ms OFF.
  bool beepOn =
    (millis() % BUZZER_PERIOD_MS) < BUZZER_ON_MS;

  digitalWrite(
    PIN_BUZZER,
    beepOn ? HIGH : LOW
  );
}

// ============================================================
// 10. PHYSICAL ACKNOWLEDGEMENT BUTTON
// ============================================================

void handleButton() {

  bool current = digitalRead(PIN_BUTTON);

  if (
    current != lastButton &&
    millis() - lastButtonChange > 50
  ) {

    lastButton = current;
    lastButtonChange = millis();

    if (current == LOW) {

      buzzerAcknowledged = true;

      if (BUZZER_ENABLED) {
        digitalWrite(PIN_BUZZER, LOW);
      }

      Serial.println(
        "Alarm acknowledged locally; severity unchanged"
      );
    }
  }
}

// ============================================================
// 11. MQTT JSON PUBLISHING
// ============================================================

bool publishJson(
  const char *topic,
  JsonDocument &doc,
  bool retain = false
) {

  if (!mqtt.connected()) {
    return false;
  }

  String data;

  serializeJson(doc, data);

  return mqtt.publish(
    topic,
    data.c_str(),
    retain
  );
}

// Confirmed thresholds and current profile.
void sendConfig() {

  JsonDocument doc;

  doc["device_id"] = DEVICE_ID;
  doc["profile"] = PROFILES[profileIndex].name;

  const char *names[] = {
    "temperature",
    "humidity",
    "vibration"
  };

  for (int i = 0; i < 3; ++i) {

    JsonObject m =
      doc[names[i]].to<JsonObject>();

    if (i != 2) {

      m["critical_low"] = limits[i].criticalLow;
      m["warning_low"] = limits[i].warningLow;
    }

    m["warning_high"] = limits[i].warningHigh;
    m["critical_high"] = limits[i].criticalHigh;

    m["low_enabled"] = (i != 2);
  }

  publishJson(TOPIC_CONFIG, doc, true);
}

// Sensor diagnostics and equipment/alarm state.
void sendHealthAndState() {

  JsonDocument health;

  health["device_id"] = DEVICE_ID;

  health["sensor_health"] =
    dhtValid && vibrationValid ? "OK" : "FAULT";

  health["dht_valid"] = dhtValid;
  health["vibration_valid"] = vibrationValid;

  health["fault_reason"] =
    !dhtValid ? "DHT_INVALID" :
    !vibrationValid ? "MPU_INVALID" :
    "NONE";

  health["uptime_ms"] = millis();

  publishJson(TOPIC_HEALTH, health, true);

  JsonDocument state;

  state["device_id"] = DEVICE_ID;
  state["profile"] = PROFILES[profileIndex].name;
  state["condition"] = severityName(severity);

  state["alarm_acknowledged"] =
    buzzerAcknowledged;

  state["buzzer_output_enabled"] =
    BUZZER_ENABLED;

  state["sensor_fault"] =
    !dhtValid || !vibrationValid;

  state["uptime_ms"] = millis();

  publishJson(TOPIC_CONTROL, state, true);
}

// ============================================================
// 12. CLEAN TELEMETRY
// ============================================================

void sendTelemetry() {

  JsonDocument doc;

  doc["device_id"] = DEVICE_ID;

  if (dhtValid) {

    doc["temperature"] = temperatureC;
    doc["humidity"] = humidity;

  } else {

    doc["temperature"] = nullptr;
    doc["humidity"] = nullptr;
  }

  if (vibrationValid) {

    doc["vibration"] = vibrationRMS;

  } else {

    doc["vibration"] = nullptr;
  }

  doc["condition"] = severityName(severity);
  doc["profile"] = PROFILES[profileIndex].name;

  // Retained for Python subscriber sensor validation.
  doc["dht_valid"] = dhtValid;
  doc["vibration_valid"] = vibrationValid;

  doc["sensor_fault"] =
    !dhtValid || !vibrationValid;

  publishJson(TOPIC_TELEMETRY, doc);

  Serial.printf(
    "T:%s H:%s V:%s Condition:%s Profile:%s MQTT:%d\n",
    dhtValid ? String(temperatureC, 1).c_str() : "FAULT",
    dhtValid ? String(humidity, 1).c_str() : "FAULT",
    vibrationValid ? String(vibrationRMS, 3).c_str() : "FAULT",
    severityName(severity),
    PROFILES[profileIndex].name,
    mqtt.connected()
  );
}

// ============================================================
// 13. MQTT COMMAND ACKNOWLEDGEMENT
// ============================================================

void sendAck(
  const String &id,
  const char *status,
  const char *reason
) {

  JsonDocument ack;

  ack["device_id"] = DEVICE_ID;
  ack["command_id"] = id;
  ack["status"] = status;
  ack["reason"] = reason;
  ack["uptime_ms"] = millis();

  publishJson(TOPIC_ACK, ack);
}

bool numeric(JsonVariantConst value) {

  return value.is<int>() ||
         value.is<float>() ||
         value.is<double>();
}

// ============================================================
// 14. MQTT COMMAND PROCESSING
// ============================================================

void handleCommand(
  char *topic,
  byte *data,
  unsigned int size
) {

  if (
    strcmp(topic, TOPIC_COMMAND) != 0 ||
    size > 1200 ||
    size < 10
  ) {
    return;
  }

  JsonDocument cmd;

  if (deserializeJson(cmd, data, size)) {
    return;
  }

  String device = cmd["device_id"] | "";
  String id = cmd["command_id"] | "";
  String action = cmd["action"] | "";

  if (
    device != DEVICE_ID ||
    id.length() < 8 ||
    id.length() > 64
  ) {
    return;
  }

  // Validate command ID characters.
  for (unsigned i = 0; i < id.length(); ++i) {

    char c = id[i];

    if (!(
      isalnum((unsigned char)c) ||
      c == '-' ||
      c == '_'
    )) {
      return;
    }
  }

  // Reject expired commands or unsynchronized clock.
  time_t now = time(nullptr);

  int64_t expires =
    cmd["expires_at"] | int64_t(0);

  if (
    now < 1760000000 ||
    expires < now ||
    expires > now + 20
  ) {

    sendAck(
      id,
      "REJECTED",
      "EXPIRED_OR_UNSYNCED_CLOCK"
    );

    return;
  }

  // Reject duplicate command IDs.
  for (const String &previous : recentIds) {

    if (previous == id) {

      sendAck(
        id,
        "REJECTED",
        "DUPLICATE_COMMAND"
      );

      return;
    }
  }

  recentIds[recentIndex] = id;

  recentIndex =
    (recentIndex + 1) % 12;

  bool accepted = false;
  bool changed = false;

  const char *reason = "OK";

  // Request current configuration.
  if (action == "GET_CONFIG") {

    accepted = true;
    sendConfig();
  }

  // Change equipment profile.
  else if (action == "SET_PROFILE") {

    String name = cmd["profile"] | "";

    int selected = -1;

    for (int i = 0; i < PROFILE_COUNT; ++i) {

      if (name == PROFILES[i].name) {
        selected = i;
      }
    }

    if (selected < 0) {

      reason = "INVALID_PROFILE";

    } else {

      loadProfile(selected);

      accepted = true;
      changed = true;
    }
  }

  // Acknowledge audible alarm remotely.
  else if (action == "ACK_ALARM") {

    buzzerAcknowledged = true;
    accepted = true;

    if (BUZZER_ENABLED) {
      digitalWrite(PIN_BUZZER, LOW);
    }
  }

  // Change monitoring thresholds.
  else if (action == "SET_THRESHOLDS") {

    String metric = cmd["metric"] | "";

    int i =
      metric == "temperature" ? 0 :
      metric == "humidity" ? 1 :
      metric == "vibration" ? 2 : -1;

    if (i < 0) {

      reason = "INVALID_METRIC";

    } else if (
      !numeric(cmd["warning_high"]) ||
      !numeric(cmd["critical_high"]) ||
      (i != 2 &&
        (!numeric(cmd["warning_low"]) ||
         !numeric(cmd["critical_low"])))
    ) {

      reason = "MISSING_OR_INVALID_THRESHOLD";

    } else {

      Limits candidate = limits[i];

      candidate.warningHigh =
        cmd["warning_high"].as<float>();

      candidate.criticalHigh =
        cmd["critical_high"].as<float>();

      if (i != 2) {

        candidate.warningLow =
          cmd["warning_low"].as<float>();

        candidate.criticalLow =
          cmd["critical_low"].as<float>();
      }

      if (!goodLimits(i, candidate)) {

        reason = "INVALID_THRESHOLD_RANGE_OR_ORDER";

      } else {

        limits[i] = candidate;

        accepted = true;
        changed = true;
      }
    }
  }

  else {

    reason = "UNKNOWN_ACTION";
  }

  // Persist successfully applied changes.
  if (changed) {

    saveSettings();
    updateCondition();
    sendConfig();
  }

  sendHealthAndState();

  sendAck(
    id,
    accepted ? "APPLIED" : "REJECTED",
    reason
  );
}

// ============================================================
// 15. WI-FI AND MQTT CONNECTION
// ============================================================

void maintainNetwork() {

  unsigned long now = millis();

  if (WiFi.status() != WL_CONNECTED) {

    if (
      lastWiFiTry == 0 ||
      now - lastWiFiTry >= 10000
    ) {

      lastWiFiTry = now;

      Serial.println("[WIFI] Connecting...");

      WiFi.begin(
        WIFI_SSID,
        WIFI_PASSWORD
      );
    }

    return;
  }

  static bool clockStarted = false;

  if (!clockStarted) {

    configTime(
      0,
      0,
      "pool.ntp.org",
      "time.google.com"
    );

    clockStarted = true;
  }

  if (!mqtt.connected()) {

    if (
      lastMQTTTry == 0 ||
      now - lastMQTTTry >= 5000
    ) {

      lastMQTTTry = now;

      Serial.printf(
        "[MQTT] Connecting to %s:%d\n",
        MQTT_SERVER,
        MQTT_PORT
      );

      bool ok = mqtt.connect(
        DEVICE_ID,
        MQTT_USERNAME,
        MQTT_PASSWORD,
        TOPIC_STATUS,
        1,
        true,
        "OFFLINE"
      );

      if (ok) {

        mqtt.subscribe(TOPIC_COMMAND, 1);

        mqtt.publish(
          TOPIC_STATUS,
          "ONLINE",
          true
        );

        sendConfig();
        sendHealthAndState();

        Serial.println(
          "[MQTT] Connected and subscribed"
        );

      } else {

        Serial.printf(
          "[MQTT] Retry rc=%d\n",
          mqtt.state()
        );
      }
    }

  } else {

    mqtt.loop();
  }
}

// ============================================================
// 16. ESP32 SETUP
// ============================================================

void setup() {

  Serial.begin(115200);

  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_YELLOW, OUTPUT);
  pinMode(PIN_RED, OUTPUT);

  digitalWrite(PIN_GREEN, LOW);
  digitalWrite(PIN_YELLOW, HIGH);
  digitalWrite(PIN_RED, LOW);

  pinMode(PIN_BUTTON, INPUT_PULLUP);

  if (BUZZER_ENABLED) {

    pinMode(PIN_BUZZER, OUTPUT);
    digitalWrite(PIN_BUZZER, LOW);
  }

  Wire.begin(PIN_SDA, PIN_SCL);

  dht.begin();

  initializeMPU();

  restoreSettings();

  WiFi.mode(WIFI_STA);

  mqtt.setServer(
    MQTT_SERVER,
    MQTT_PORT
  );

  mqtt.setCallback(handleCommand);

  mqtt.setBufferSize(2048);

  Serial.println(
    "Monitor v3: no motor, LCD, IR, or sound sensor"
  );

  Serial.printf(
    "Buzzer output enabled: %s\n",
    BUZZER_ENABLED ? "YES" : "NO"
  );
}

// ============================================================
// 17. MAIN LOOP
// ============================================================

void loop() {

  handleButton();

  maintainNetwork();

  // Non-blocking buzzer control.
  updateBuzzer();

  unsigned long now = millis();

  // Collect sensor measurements every 2.5 seconds.
  if (
    lastTelemetry == 0 ||
    now - lastTelemetry >= 2500
  ) {

    lastTelemetry = now;

    sampleSensors();

    updateCondition();

    sendTelemetry();

    sendHealthAndState();
  }

  // Publish online status every 15 seconds.
  if (
    lastStatus == 0 ||
    now - lastStatus >= 15000
  ) {

    lastStatus = now;

    if (mqtt.connected()) {

      mqtt.publish(
        TOPIC_STATUS,
        "ONLINE",
        true
      );
    }
  }
}
