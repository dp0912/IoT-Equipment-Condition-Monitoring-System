
/*
 * IoT-Based Configurable Multi-Sensor Equipment Condition Monitoring System
 * ESP32 Dev Module | Serial Monitor: 115200 baud
 *
 * Hardware:
 * DHT11 GPIO27
 * MPU6500 SDA21, SCL22
 * LEDs GREEN25, YELLOW26, RED33
 * Buzzer GPIO23
 * IR receiver GPIO32
 * Physical STOP button GPIO13
 * L293D EN4, IN1 GPIO2, IN2 GPIO15
 * 74HC595 SER18, SRCLK19, RCLK5
 * LCD1602 via shift register
 *
 * Networking:
 * ESP32 -> Wi-Fi -> Mosquitto on Mac
 * MQTT credentials are stored privately in secrets.h.
 *
 * IMPORTANT:
 * This is demonstration firmware, NOT a safety-rated controller.
 * Software STOP does not guarantee electrical isolation.
 * Disconnect external motor power during initial testing.
 */

#include <Arduino.h>
#include <Wire.h>
#include <DHT.h>
#include <IRremote.hpp>
#include <Preferences.h>
#include <math.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "secrets.h"

// ============================================================
// 1. MQTT CONFIGURATION
// ============================================================

// MQTT topics used by the project.
constexpr const char *DEVICE_ID = "ESP32-001";
constexpr const char *TOPIC_TELEMETRY =
    "equipment/ESP32-001/telemetry";
constexpr const char *TOPIC_STATUS =
    "equipment/ESP32-001/status";

// How frequently to retry network connections.
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t MQTT_RETRY_MS = 5000;
constexpr uint32_t STATUS_INTERVAL_MS = 15000;

// WiFiClient provides TCP transport.
// PubSubClient implements the MQTT protocol.
WiFiClient wifiTransport;
PubSubClient mqtt(wifiTransport);

uint32_t lastWifiAttempt = 0;
uint32_t lastMqttAttempt = 0;
uint32_t lastStatusPublish = 0;

bool wifiAttempted = false;
bool mqttAttempted = false;

// Network function declarations.
void startNetwork();
void serviceNetwork();
void publishTelemetry();
void publishDeviceStatus();

// ============================================================
// 2. GPIO PIN DEFINITIONS
// ============================================================

constexpr int DHT_PIN = 27;
constexpr int SDA_PIN = 21;
constexpr int SCL_PIN = 22;

constexpr int GREEN = 25;
constexpr int YELLOW = 26;
constexpr int RED = 33;
constexpr int BUZZER = 23;

constexpr int IR_PIN = 32;
constexpr int BUTTON = 13;

constexpr int MOTOR_EN = 4;
constexpr int MOTOR_IN1 = 2;
constexpr int MOTOR_IN2 = 15;

constexpr int SR_DATA = 18;
constexpr int SR_CLOCK = 19;
constexpr int SR_LATCH = 5;

constexpr uint8_t LCD_RS = 1 << 4;
constexpr uint8_t LCD_EN = 1 << 5;

// ============================================================
// 3. SENSORS, SETTINGS AND SYSTEM STATE
// ============================================================

DHT dht(DHT_PIN, DHT11);
Preferences prefs;

uint8_t mpuAddr = 0x68;
bool mpuFound = false;
bool dhtValid = false;
bool vibValid = false;

float tempC = NAN;
float hum = NAN;
float vib = NAN;

// Warning thresholds: temperature, humidity, vibration.
float warnLimit[3] = {32.0f, 75.0f, 1.0f};

// Critical thresholds.
float critLimit[3] = {40.0f, 90.0f, 3.0f};

const char *metricNames[3] = {"TEMP", "HUM", "VIB"};
const char *metricKeysW[3] = {"tw", "hw", "vw"};
const char *metricKeysC[3] = {"tc", "hc", "vc"};

float steps[3] = {0.5f, 1.0f, 0.1f};

int selectedMetric = 0;
bool editCritical = false;

// Buzzer pattern setting, not physical loudness.
int buzzerLevel = 2;

// AUTO uses sensor readings.
// Other modes simulate conditions for demonstration.
enum Mode {
  AUTO_MODE,
  NORMAL_MODE,
  WARNING_MODE,
  CRITICAL_MODE
};

Mode mode = AUTO_MODE;

uint8_t page = 0;

bool autoPages = true;
bool motorArmed = false;
bool motorRunning = false;
bool stopLatched = false;

uint32_t lastSample = 0;
uint32_t lastLCD = 0;
uint32_t lastPage = 0;
uint32_t lastPrint = 0;

uint32_t buttonChange = 0;
uint32_t buttonDownAt = 0;

bool lastRawButton = HIGH;
bool stableButton = HIGH;
bool longHandled = false;

// Forward declarations.
Mode currentMode();
Mode sensorMode();

// ============================================================
// 4. MOTOR CONTROL AND SOFTWARE STOP
// ============================================================

// Force the motor-driver control inputs LOW.
void motorOff() {
  digitalWrite(MOTOR_EN, LOW);
  digitalWrite(MOTOR_IN1, LOW);
  digitalWrite(MOTOR_IN2, LOW);
  motorRunning = false;
}

// Latch STOP and require an explicit reset and re-arm.
void latchStop(const char *source) {
  motorOff();
  motorArmed = false;
  stopLatched = true;

  Serial.printf(
    "STOP LATCHED by %s. Reset only when safe.\n",
    source
  );
}

// Start fan only when local interlocks permit it.
void startFan() {
  if (stopLatched) {
    Serial.println("Fan BLOCKED: stop latched.");
    return;
  }

  if (!motorArmed) {
    Serial.println("Fan BLOCKED: motor disarmed.");
    return;
  }

  if (!dhtValid || !vibValid) {
    Serial.println("Fan BLOCKED: sensor data unavailable.");
    return;
  }

  if (currentMode() == CRITICAL_MODE ||
      sensorMode() == CRITICAL_MODE) {
    Serial.println("Fan BLOCKED: CRITICAL condition.");
    return;
  }

  motorOff();

  digitalWrite(MOTOR_IN1, HIGH);
  digitalWrite(MOTOR_IN2, LOW);
  digitalWrite(MOTOR_EN, HIGH);

  motorRunning = true;

  Serial.println("FAN ON until OFF/STOP/critical condition.");
}

// ============================================================
// 5. 74HC595 SHIFT REGISTER AND LCD1602
// ============================================================

// Q0-Q3: LCD D4-D7
// Q4: LCD RS
// Q5: LCD EN

void write595(uint8_t value) {
  digitalWrite(SR_LATCH, LOW);
  shiftOut(SR_DATA, SR_CLOCK, MSBFIRST, value);
  digitalWrite(SR_LATCH, HIGH);
}

void lcdNibble(uint8_t n, bool rs) {
  uint8_t value = (n & 15) | (rs ? LCD_RS : 0);

  write595(value);
  delayMicroseconds(1);

  write595(value | LCD_EN);
  delayMicroseconds(2);

  write595(value);
  delayMicroseconds(50);
}

void lcdSend(uint8_t b, bool rs) {
  lcdNibble(b >> 4, rs);
  lcdNibble(b & 15, rs);
}

void lcdCmd(uint8_t b) {
  lcdSend(b, false);
  delay(2);
}

// Initialize LCD in 4-bit mode.
void lcdInit() {
  write595(0);
  delay(100);

  lcdNibble(3, false);
  delay(5);
  lcdNibble(3, false);

  delayMicroseconds(150);
  lcdNibble(3, false);
  lcdNibble(2, false);

  lcdCmd(0x28);
  lcdCmd(0x0C);
  lcdCmd(0x06);
  lcdCmd(0x01);
}

// Print one padded 16-character LCD row.
void lcdLine(uint8_t row, String s) {
  lcdCmd(0x80 + (row ? 0x40 : 0));

  s = s.substring(0, 16);

  while (s.length() < 16) {
    s += ' ';
  }

  for (size_t i = 0; i < s.length(); i++) {
    lcdSend(s[i], true);
  }
}

// ============================================================
// 6. MPU6500 ACCELEROMETER
// ============================================================

// Read consecutive MPU6500 registers over I2C.
bool mpuRead(uint8_t reg, uint8_t *buf, size_t len) {
  Wire.beginTransmission(mpuAddr);
  Wire.write(reg);

  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom((int)mpuAddr, (int)len) != (int)len) {
    return false;
  }

  for (size_t i = 0; i < len; i++) {
    buf[i] = Wire.read();
  }

  return true;
}

void mpuWrite(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(mpuAddr);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

// Detect MPU6500 at either common I2C address.
void setupMPU() {
  uint8_t who = 0;

  for (uint8_t addr : {uint8_t(0x68), uint8_t(0x69)}) {
    mpuAddr = addr;

    if (mpuRead(0x75, &who, 1)) {
      mpuFound = true;

      mpuWrite(0x6B, 0);
      delay(100);
      mpuWrite(0x1C, 0);

      Serial.printf(
        "MPU detected at 0x%02X, WHO_AM_I=0x%02X\n",
        mpuAddr, who
      );

      return;
    }
  }

  Serial.println("MPU NOT FOUND - check wiring.");
}

// ============================================================
// 7. READ TEMPERATURE, HUMIDITY AND VIBRATION
// ============================================================

// DHT11 measures temperature and humidity.
// MPU6500 provides 16 acceleration samples.
// Dynamic acceleration RMS estimates vibration.
void readSensors() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();

  dhtValid = isfinite(t) && isfinite(h);

  if (dhtValid) {
    tempC = t;
    hum = h;
  }

  vibValid = false;

  if (!mpuFound) {
    return;
  }

  float x[16], y[16], z[16];
  float mx = 0, my = 0, mz = 0;
  bool ok = true;

  for (int i = 0; i < 16; i++) {
    uint8_t b[6];

    if (!mpuRead(0x3B, b, 6)) {
      ok = false;
      break;
    }

    int16_t ax = (int16_t)((b[0] << 8) | b[1]);
    int16_t ay = (int16_t)((b[2] << 8) | b[3]);
    int16_t az = (int16_t)((b[4] << 8) | b[5]);

    x[i] = ax * (9.80665f / 16384.0f);
    y[i] = ay * (9.80665f / 16384.0f);
    z[i] = az * (9.80665f / 16384.0f);

    mx += x[i];
    my += y[i];
    mz += z[i];

    delay(3);
  }

  if (ok) {
    mx /= 16;
    my /= 16;
    mz /= 16;

    float sum = 0;

    for (int i = 0; i < 16; i++) {
      float dx = x[i] - mx;
      float dy = y[i] - my;
      float dz = z[i] - mz;

      sum += dx * dx + dy * dy + dz * dz;
    }

    vib = sqrtf(sum / 16);
    vibValid = true;
  }
}

// ============================================================
// 8. EQUIPMENT CONDITION CLASSIFICATION
// ============================================================

// Missing sensor data is classified as WARNING.
Mode sensorMode() {
  if (!dhtValid || !vibValid) {
    return WARNING_MODE;
  }

  float values[3] = {tempC, hum, vib};

  for (int i = 0; i < 3; i++) {
    if (values[i] >= critLimit[i]) {
      return CRITICAL_MODE;
    }
  }

  for (int i = 0; i < 3; i++) {
    if (values[i] >= warnLimit[i]) {
      return WARNING_MODE;
    }
  }

  return NORMAL_MODE;
}

// Return live sensor condition or selected simulation mode.
Mode currentMode() {
  return mode == AUTO_MODE ? sensorMode() : mode;
}

const char *modeName(Mode m) {
  switch (m) {
    case NORMAL_MODE: return "NORMAL";
    case WARNING_MODE: return "WARNING";
    case CRITICAL_MODE: return "CRITICAL";
    default: return "AUTO";
  }
}

// Format sensor value or show N/A.
String val(float x, bool valid, int digits) {
  return valid ? String(x, digits) : String("N/A");
}

// ============================================================
// 9. LED, BUZZER AND MOTOR INTERLOCK OUTPUTS
// ============================================================

void updateOutputs() {
  Mode m = currentMode();

  digitalWrite(GREEN, m == NORMAL_MODE);
  digitalWrite(YELLOW, m == WARNING_MODE);
  digitalWrite(RED, m == CRITICAL_MODE);

  // Different beep rates indicate critical condition.
  bool beep = false;

  if (m == CRITICAL_MODE && buzzerLevel > 0) {
    uint32_t period =
      buzzerLevel == 1 ? 1600 :
      buzzerLevel == 2 ? 800 : 400;

    beep = (millis() % period) < 120;
  }

  digitalWrite(BUZZER, beep ? HIGH : LOW);

  // Stop running motor if sensors fail.
  if (motorRunning && (!dhtValid || !vibValid)) {
    latchStop("sensor data unavailable");
  }
  // Stop running motor if condition becomes critical.
  else if (motorRunning &&
           (m == CRITICAL_MODE ||
            sensorMode() == CRITICAL_MODE)) {
    latchStop("CRITICAL condition");
  }
}

// ============================================================
// 10. LCD DISPLAY PAGES
// ============================================================

// Pages 0-3 display monitoring information.
// Page 4 displays editable thresholds.
void updateLCD() {
  if (page == 0) {
    lcdLine(0, "Temp: " + val(tempC, dhtValid, 1) + " C");
    lcdLine(1, "Hum: " + val(hum, dhtValid, 0) + " %");
  }
  else if (page == 1) {
    lcdLine(0, "Vib: " + val(vib, vibValid, 3));
    lcdLine(1, "State: " + String(modeName(currentMode())));
  }
  else if (page == 2) {
    lcdLine(
      0,
      "Fan: " + String(motorRunning ? "RUN" : "OFF") +
      (stopLatched ? " STOP" : "")
    );

    lcdLine(1, "Mode: " +
      String(mode == AUTO_MODE ? "AUTO" : "TEST"));
  }
  else if (page == 3) {
    lcdLine(0, "Buzzer: " + String(buzzerLevel) + " (pattern)");
    lcdLine(1, "IR/BTN READY");
  }
  else {
    int digits = selectedMetric == 2 ? 2 : 1;

    float value = editCritical ?
      critLimit[selectedMetric] :
      warnLimit[selectedMetric];

    lcdLine(
      0,
      String(metricNames[selectedMetric]) +
      (editCritical ? " CRIT LIMIT" : " WARN LIMIT")
    );

    lcdLine(1, "Set: " + String(value, digits));
  }
}

// ============================================================
// 11. SERIAL STATUS AND THRESHOLDS
// ============================================================

void printStatus() {
  Serial.printf(
    "Temp=%s C | Hum=%s %% | Vib=%s m/s^2 | "
    "Condition=%s | Fan=%s | Armed=%d | Stop=%d | Beep=%d\n",
    val(tempC, dhtValid, 1).c_str(),
    val(hum, dhtValid, 0).c_str(),
    val(vib, vibValid, 3).c_str(),
    modeName(currentMode()),
    motorRunning ? "ON" : "OFF",
    motorArmed,
    stopLatched,
    buzzerLevel
  );
}

void printThresholds() {
  Serial.printf(
    "Limits: Temp W%.1f/C%.1f C; "
    "Hum W%.1f/C%.1f %%; "
    "Vib W%.2f/C%.2f m/s^2\n",
    warnLimit[0], critLimit[0],
    warnLimit[1], critLimit[1],
    warnLimit[2], critLimit[2]
  );
}

void setPage(uint8_t p) {
  page = p;
  autoPages = false;
  lastLCD = 0;
}

// ============================================================
// 12. CONFIGURABLE THRESHOLDS
// ============================================================

// Threshold changes are stored in ESP32 nonvolatile memory.
void adjustThreshold(int direction) {
  float &target = editCritical ?
    critLimit[selectedMetric] :
    warnLimit[selectedMetric];

  float candidate =
    target + steps[selectedMetric] * direction;

  if (candidate < 0) {
    candidate = 0;
  }

  if (selectedMetric == 1 && candidate > 100) {
    candidate = 100;
  }

  if (editCritical &&
      candidate <= warnLimit[selectedMetric]) {
    Serial.println(
      "Rejected: critical must exceed warning limit."
    );
    return;
  }

  if (!editCritical &&
      candidate >= critLimit[selectedMetric]) {
    Serial.println(
      "Rejected: warning must be below critical limit."
    );
    return;
  }

  target = candidate;

  prefs.putFloat(
    editCritical ?
      metricKeysC[selectedMetric] :
      metricKeysW[selectedMetric],
    target
  );

  printThresholds();
  setPage(4);
}

// ============================================================
// 13. STOP RESET
// ============================================================

// Reset never automatically arms or starts the motor.
void resetStop() {
  mode = AUTO_MODE;

  if (sensorMode() == CRITICAL_MODE) {
    Serial.println(
      "RESET DENIED: sensor readings are CRITICAL."
    );
    return;
  }

  stopLatched = false;
  motorOff();
  motorArmed = false;

  Serial.println(
    "STOP CLEARED. Fan still DISARMED."
  );
}

void selectMetric(int index) {
  selectedMetric = index;
  setPage(4);
  printThresholds();
}

// ============================================================
// 14. INFRARED REMOTE CONTROL
// ============================================================

void handleRemote(uint16_t cmd) {
  Serial.printf("IR command 0x%02X\n", cmd);

  switch (cmd) {
    case 0x45:
      latchStop("IR POWER");
      break;

    case 0x46:
      buzzerLevel = min(3, buzzerLevel + 1);
      break;

    case 0x47:
      mode = AUTO_MODE;
      autoPages = true;
      Serial.println("AUTO monitoring");
      break;

    case 0x44:
      setPage((page + 4) % 5);
      break;

    case 0x40:
      if (motorRunning) {
        motorOff();
        Serial.println("Fan OFF");
      } else {
        startFan();
      }
      break;

    case 0x43:
      setPage((page + 1) % 5);
      break;

    case 0x07:
      adjustThreshold(-1);
      break;

    case 0x15:
      buzzerLevel = max(0, buzzerLevel - 1);
      break;

    case 0x09:
      adjustThreshold(+1);
      break;

    case 0x16:
      setPage(0);
      break;

    case 0x19:
      editCritical = !editCritical;
      setPage(4);
      Serial.println(
        editCritical ?
          "Edit CRITICAL limit" :
          "Edit WARNING limit"
      );
      break;

    case 0x0D:
      resetStop();
      break;

    case 0x0C:
      mode = NORMAL_MODE;
      Serial.println("TEST NORMAL");
      break;

    case 0x18:
      mode = WARNING_MODE;
      Serial.println("TEST WARNING");
      break;

    case 0x5E:
      mode = CRITICAL_MODE;
      Serial.println("TEST CRITICAL");
      break;

    // Remote 4: arm motor.
    case 0x08:
      if (stopLatched || !dhtValid || !vibValid ||
          sensorMode() == CRITICAL_MODE) {
        Serial.println("ARM BLOCKED.");
      } else {
        motorArmed = true;
        Serial.println("Motor ARMED. Fan remains OFF.");
      }
      break;

    // Remote 5: fan ON.
    case 0x1C:
      startFan();
      break;

    // Remote 6: fan OFF.
    case 0x5A:
      motorOff();
      Serial.println("Fan OFF (arm retained)");
      break;

    // Remote 7/8/9: select threshold.
    case 0x42:
      selectMetric(0);
      break;

    case 0x52:
      selectMetric(1);
      break;

    case 0x4A:
      selectMetric(2);
      break;

    default:
      Serial.println("Unmapped IR command");
      break;
  }

  updateLCD();
}

// Decode NEC IR commands.
// Ignore repeated or overflow frames.
void pollRemote() {
  if (IrReceiver.decode()) {
    auto data = IrReceiver.decodedIRData;

    if (data.protocol == NEC &&
        data.address == 0 &&
        !(data.flags &
          (IRDATA_FLAGS_IS_REPEAT |
           IRDATA_FLAGS_WAS_OVERFLOW))) {
      handleRemote(data.command);
    }

    IrReceiver.resume();
  }
}

// ============================================================
// 15. PHYSICAL PUSHBUTTON
// ============================================================

// Short press latches STOP.
// Button uses INPUT_PULLUP, active LOW.
void pollButton() {
  bool raw = digitalRead(BUTTON);
  uint32_t now = millis();

  if (raw != lastRawButton) {
    lastRawButton = raw;
    buttonChange = now;
  }

  if (now - buttonChange < 35 ||
      raw == stableButton) {
    return;
  }

  stableButton = raw;

  if (stableButton == LOW) {
    buttonDownAt = now;
    longHandled = false;
  }
  else if (!longHandled) {
    latchStop("physical button");
  }
}

// Holding the button for 2 seconds requests reset.
void pollButtonHold() {
  if (stableButton == LOW &&
      !longHandled &&
      millis() - buttonDownAt >= 2000) {
    longHandled = true;
    resetStop();
  }
}

// ============================================================
// 16. SERIAL MONITOR COMMANDS
// ============================================================

void help() {
  Serial.println(
    "SERIAL: A auto | N normal | W warning | "
    "C critical | P status | T thresholds | ? help"
  );

  Serial.println(
    "M arm | F fan ON | O fan OFF | "
    "X latch STOP | R reset STOP"
  );

  Serial.println(
    "IR: POWER stop; VOL+/VOL- buzzer; "
    "FUNC auto; PREV/NEXT LCD; PLAY fan toggle"
  );

  Serial.println(
    "IR: DOWN/UP limit -/+; 0 overview; "
    "EQ warning/critical; ST/REPT reset"
  );

  Serial.println(
    "IR: 1/2/3 test modes; 4 ARM; 5 ON; "
    "6 OFF; 7/8/9 select sensor limit"
  );

  Serial.println(
    "BUTTON: short press STOP; hold 2 seconds reset."
  );
}

// ============================================================
// 17. WI-FI INITIALIZATION
// ============================================================

// Configure Wi-Fi and MQTT using private secrets.h.
void startNetwork() {
  WiFi.mode(WIFI_STA);

  // Disable Wi-Fi sleep for more consistent local MQTT.
  WiFi.setSleep(false);

  // Configure MQTT broker address and message buffer.
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setBufferSize(768);

  Serial.println("[NET] Starting Wi-Fi connection...");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  wifiAttempted = true;
  lastWifiAttempt = millis();
}

// ============================================================
// 18. WI-FI AND MQTT CONNECTION MANAGEMENT
// ============================================================

// Called repeatedly from loop().
// Retry timing avoids long explicit delay() loops.
// Library connection attempts may still block briefly.
void serviceNetwork() {
  uint32_t now = millis();

  // First, check Wi-Fi.
  if (WiFi.status() != WL_CONNECTED) {
    if (!wifiAttempted ||
        now - lastWifiAttempt >= WIFI_RETRY_MS) {

      lastWifiAttempt = now;
      wifiAttempted = true;

      Serial.println(
        "[NET] Wi-Fi disconnected; retrying..."
      );

      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }

    return;
  }

  // Wi-Fi is connected; now check MQTT.
  if (!mqtt.connected()) {
    if (!mqttAttempted ||
        now - lastMqttAttempt >= MQTT_RETRY_MS) {

      mqttAttempted = true;
      lastMqttAttempt = now;

      Serial.printf(
        "[MQTT] Connecting to %s:%d ...\n",
        MQTT_SERVER,
        MQTT_PORT
      );

      // Last Will and Testament:
      // If connection is unexpectedly lost, the broker
      // publishes OFFLINE on the status topic.
      bool connected = mqtt.connect(
        DEVICE_ID,
        MQTT_USERNAME,
        MQTT_PASSWORD,
        TOPIC_STATUS,
        1,
        true,
        "OFFLINE"
      );

      if (connected) {
        Serial.printf(
          "[MQTT] Connected; ESP32 IP: %s\n",
          WiFi.localIP().toString().c_str()
        );

        mqtt.publish(TOPIC_STATUS, "ONLINE", true);
        lastStatusPublish = now;
      }
      else {
        Serial.printf(
          "[MQTT] Connection failed (state=%d).\n",
          mqtt.state()
        );
      }
    }

    return;
  }

  // Maintain MQTT connection and keepalive.
  mqtt.loop();

  // Periodically refresh ONLINE status.
  if (now - lastStatusPublish >= STATUS_INTERVAL_MS) {
    lastStatusPublish = now;
    publishDeviceStatus();
  }
}

// ============================================================
// 19. MQTT DEVICE STATUS
// ============================================================

// Retained status lets future dashboards identify
// the latest known connection state.
void publishDeviceStatus() {
  if (mqtt.connected()) {
    mqtt.publish(TOPIC_STATUS, "ONLINE", true);
  }
}

// ============================================================
// 20. MQTT SENSOR TELEMETRY
// ============================================================

// Publish real readings as JSON every sensor sample.
// Invalid sensor readings are sent as JSON null.
// This does NOT accept remote motor commands.
void publishTelemetry() {
  if (!mqtt.connected()) {
    return;
  }

  String t = dhtValid ? String(tempC, 1) : "null";
  String h = dhtValid ? String(hum, 1) : "null";
  String v = vibValid ? String(vib, 3) : "null";

  String payload =
    "{\"device_id\":\"" + String(DEVICE_ID) + "\"";

  payload += ",\"temperature\":" + t;
  payload += ",\"humidity\":" + h;
  payload += ",\"vibration\":" + v;

  payload +=
    ",\"condition\":\"" +
    String(modeName(currentMode())) + "\"";

  payload +=
    ",\"sensor_condition\":\"" +
    String(modeName(sensorMode())) + "\"";

  payload +=
    ",\"mode\":\"" +
    String(modeName(mode)) + "\"";

  payload +=
    ",\"dht_valid\":" +
    String(dhtValid ? "true" : "false");

  payload +=
    ",\"vibration_valid\":" +
    String(vibValid ? "true" : "false");

  payload +=
    ",\"motor_running\":" +
    String(motorRunning ? "true" : "false");

  payload +=
    ",\"motor_armed\":" +
    String(motorArmed ? "true" : "false");

  payload +=
    ",\"stop_latched\":" +
    String(stopLatched ? "true" : "false");

  payload +=
    ",\"uptime_ms\":" +
    String(millis());

  payload += "}";

  if (!mqtt.publish(
        TOPIC_TELEMETRY,
        payload.c_str()
      )) {
    Serial.println(
      "[MQTT] Telemetry publish failed."
    );
  }
}

// ============================================================
// 21. ESP32 SETUP
// ============================================================

void setup() {
  // Initialize motor outputs in the OFF state.
  digitalWrite(MOTOR_EN, LOW);
  pinMode(MOTOR_EN, OUTPUT);

  digitalWrite(MOTOR_IN1, LOW);
  pinMode(MOTOR_IN1, OUTPUT);

  digitalWrite(MOTOR_IN2, LOW);
  pinMode(MOTOR_IN2, OUTPUT);

  motorOff();

  // Start USB Serial Monitor.
  Serial.begin(115200);
  delay(300);

  // Configure local indicators.
  pinMode(GREEN, OUTPUT);
  pinMode(YELLOW, OUTPUT);
  pinMode(RED, OUTPUT);

  pinMode(BUZZER, OUTPUT);
  digitalWrite(BUZZER, LOW);

  pinMode(BUTTON, INPUT_PULLUP);

  // Configure shift register pins.
  pinMode(SR_DATA, OUTPUT);
  pinMode(SR_CLOCK, OUTPUT);
  pinMode(SR_LATCH, OUTPUT);

  // Initialize sensors and LCD.
  Wire.begin(SDA_PIN, SCL_PIN);
  dht.begin();
  setupMPU();
  lcdInit();

  // Load previously saved thresholds.
  prefs.begin("iotmonitor", false);

  for (int i = 0; i < 3; i++) {
    float w = prefs.getFloat(
      metricKeysW[i],
      warnLimit[i]
    );

    float c = prefs.getFloat(
      metricKeysC[i],
      critLimit[i]
    );

    if (isfinite(w) &&
        isfinite(c) &&
        w >= 0 &&
        c > w &&
        (i != 1 || c <= 100)) {

      warnLimit[i] = w;
      critLimit[i] = c;
    }
  }

  // Initialize IR receiver.
  IrReceiver.begin(
    IR_PIN,
    DISABLE_LED_FEEDBACK
  );

  lcdLine(0, "IoT Full Test");
  lcdLine(1, "Fan DISARMED");

  Serial.println(
    "FULL SYSTEM TEST READY; fan OFF and DISARMED."
  );

  printThresholds();
  help();

  // Start Wi-Fi after local hardware initialization.
  startNetwork();
}

// ============================================================
// 22. MAIN LOOP
// ============================================================

// Local monitoring continues even when MQTT is offline.
void loop() {
  uint32_t now = millis();

  // Check physical and IR controls.
  pollButton();
  pollButtonHold();
  pollRemote();

  // Process Serial Monitor commands.
  while (Serial.available()) {
    char c = toupper(
      (unsigned char)Serial.read()
    );

    switch (c) {
      case 'A':
        mode = AUTO_MODE;
        Serial.println("AUTO");
        break;

      case 'N':
        mode = NORMAL_MODE;
        Serial.println("TEST NORMAL");
        break;

      case 'W':
        mode = WARNING_MODE;
        Serial.println("TEST WARNING");
        break;

      case 'C':
        mode = CRITICAL_MODE;
        Serial.println("TEST CRITICAL");
        break;

      case 'P':
        printStatus();
        break;

      case 'T':
        printThresholds();
        break;

      case 'M':
        if (stopLatched ||
            !dhtValid ||
            !vibValid ||
            sensorMode() == CRITICAL_MODE) {

          Serial.println("ARM BLOCKED.");
        }
        else {
          motorArmed = true;
          Serial.println("Motor ARMED.");
        }
        break;

      case 'F':
        startFan();
        break;

      case 'O':
        motorOff();
        Serial.println("Fan OFF (arm retained)");
        break;

      case 'X':
        latchStop("Serial X");
        break;

      case 'R':
        resetStop();
        break;

      case '?':
        help();
        break;

      default:
        // Ignore unrecognized characters/newlines.
        break;
    }
  }

  // Sample real sensors every 2 seconds.
  bool newSample = false;

  if (now - lastSample >= 2000) {
    lastSample = now;
    readSensors();
    newSample = true;
  }

  // Keep local indicators and interlocks active.
  updateOutputs();

  // Maintain Wi-Fi and MQTT connections.
  serviceNetwork();

  // Send sensor readings only after a new sample.
  if (newSample) {
    publishTelemetry();
  }

  // Automatically rotate LCD monitoring pages.
  if (autoPages && now - lastPage >= 3000) {
    lastPage = now;
    page = (page + 1) % 4;
  }

  // Refresh LCD once per second.
  if (now - lastLCD >= 1000) {
    lastLCD = now;
    updateLCD();
  }

  // Print status to Serial Monitor every 2 seconds.
  if (now - lastPrint >= 2000) {
    lastPrint = now;
    printStatus();
  }
}
