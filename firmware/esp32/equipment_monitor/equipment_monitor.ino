/*
 * IoT-Based Configurable Multi-Sensor Equipment Condition Monitoring System
 * ------------------------------------------------------------------------
 * Hardware integration baseline v1.0 (based on tested IoT_Full_System_Test_v2)
 * Target: ESP32 Dev Module | Serial Monitor: 115200 baud
 *
 * Hardware:
 *   DHT11: GPIO27
 *   MPU6500: I2C SDA21 / SCL22, address 0x68 or 0x69
 *   LEDs: green25, yellow26, red33; active buzzer23
 *   IR receiver32; emergency pushbutton13 (INPUT_PULLUP, active LOW)
 *   L293D: EN pin1 <- GPIO4; IN1 pin2 <- GPIO2; IN2 pin7 <- GPIO15
 *           motor across L293D outputs pins3 and6
 *   74HC595: SER18, SRCLK19, RCLK5; LCD1602 in 4-bit mode
 *
 * Power: ESP32 via USB. LCD and motor driver use separate 5V supply
 * branches from ELEGOO module, with common ground. These branches may
 * still share a regulator. NEVER feed 5V into ESP32's 3.3V rail.
 *
 * Libraries: DHT sensor library, IRremote 4.x, Wire, Preferences.
 * Local demonstration firmware: not a safety-rated motor controller.
 * GPIO2/GPIO15 are ESP32 strapping pins; add hardware motor inhibit for
 * dependable power-up behavior. Motor must be mechanically guarded.
 *
 * Differences from tested v2: explanatory comments, sensor-failure
 * interlock for motor start/run/reset, and sensorMode forward declaration.
 * Re-test these changes on hardware before tagging as verified.
 */

#include <Arduino.h>

#include <Wire.h>

#include <DHT.h>

#include <IRremote.hpp>

#include <Preferences.h>

#include <math.h>

// Original v2 implementation, retained for hardware compatibility.
// INTEGRATED LOCAL VERIFICATION FIRMWARE (not a certified safety controller).

// ESP32 Dev Module, Serial Monitor 115200. Libraries: DHT sensor library, IRremote.

// Keep motor power disconnected until motor voltage/current and supply are checked.

// ESP32 GPIO2 and GPIO15 are boot-strapping pins: a hardware motor-enable

// pulldown/interlock is recommended; firmware cannot guarantee boot-time OFF.

// --- GPIO mapping: keep consistent with the physical breadboard ---
constexpr int DHT_PIN=27, SDA_PIN=21, SCL_PIN=22;

constexpr int GREEN=25, YELLOW=26, RED=33, BUZZER=23, IR_PIN=32, BUTTON=13;

constexpr int MOTOR_EN=4, MOTOR_IN1=2, MOTOR_IN2=15;

constexpr int SR_DATA=18, SR_CLOCK=19, SR_LATCH=5;

constexpr uint8_t LCD_RS=1<<4, LCD_EN=1<<5;

// --- Device drivers and persistent configuration ---
DHT dht(DHT_PIN,DHT11);

Preferences prefs;

uint8_t mpuAddr=0x68;

bool mpuFound=false, dhtValid=false, vibValid=false;

float tempC=NAN, hum=NAN, vib=NAN;

// Factory thresholds; user adjustments are saved to ESP32 flash (Preferences).
float warnLimit[3]={32.0f,75.0f,1.0f};

float critLimit[3]={40.0f,90.0f,3.0f};

const char *metricNames[3]={"TEMP","HUM","VIB"};

const char *metricKeysW[3]={"tw","hw","vw"};

const char *metricKeysC[3]={"tc","hc","vc"};

float steps[3]={0.5f,1.0f,0.1f};

int selectedMetric=0;

bool editCritical=false;

int buzzerLevel=2; // Active buzzer: OFF / short beeps / medium / frequent, NOT loudness.

// AUTO uses live sensor classification; other modes simulate test conditions.
enum Mode {AUTO_MODE,NORMAL_MODE,WARNING_MODE,CRITICAL_MODE};

Mode mode=AUTO_MODE;

uint8_t page=0;

bool autoPages=true, motorArmed=false, motorRunning=false, stopLatched=false;

uint32_t lastSample=0,lastLCD=0,lastPage=0,lastPrint=0;

uint32_t buttonChange=0,buttonDownAt=0;

bool lastRawButton=HIGH,stableButton=HIGH,longHandled=false;

Mode currentMode();
Mode sensorMode();  // Forward declaration: used by motor interlock before its definition.

// Force L293D enable and both direction inputs LOW.
void motorOff(){

  digitalWrite(MOTOR_EN,LOW); digitalWrite(MOTOR_IN1,LOW);digitalWrite(MOTOR_IN2,LOW);

  motorRunning=false;

}

// Latch a software emergency stop; explicit reset and re-arm required.
void latchStop(const char *source){

  motorOff();motorArmed=false;stopLatched=true;

  Serial.printf("STOP LATCHED by %s. Reset only when safe (hold button / ST-REPT / R).\n",source);

}

// Continuous run until OFF/STOP/critical/missing sensor.
void startFan(){

  if(stopLatched){Serial.println("Fan BLOCKED: stop latched. Reset first.");return;}

  if(!motorArmed){Serial.println("Fan BLOCKED: motor disarmed. Use M to arm after electrical check.");return;}

  if(!dhtValid || !vibValid){Serial.println("Fan BLOCKED: sensor data unavailable.");return;}
  if(currentMode()==CRITICAL_MODE || sensorMode()==CRITICAL_MODE){Serial.println("Fan BLOCKED: CRITICAL condition.");return;}

  motorOff();digitalWrite(MOTOR_IN1,HIGH);digitalWrite(MOTOR_IN2,LOW);

  digitalWrite(MOTOR_EN,HIGH);motorRunning=true;

  Serial.println("FAN ON continuously until OFF/STOP/critical condition.");

}

// --- SN74HC595 -> LCD1602 4-bit parallel interface ---
// Q0-Q3: LCD D4-D7; Q4: RS; Q5: EN (as wired in this sketch).
void write595(uint8_t v){digitalWrite(SR_LATCH,LOW);shiftOut(SR_DATA,SR_CLOCK,MSBFIRST,v);digitalWrite(SR_LATCH,HIGH);}

void lcdNibble(uint8_t n,bool rs){

  uint8_t v=(n&15)|(rs?LCD_RS:0);

  write595(v);delayMicroseconds(1);write595(v|LCD_EN);delayMicroseconds(2);write595(v);delayMicroseconds(50);

}

void lcdSend(uint8_t b,bool rs){lcdNibble(b>>4,rs);lcdNibble(b&15,rs);}

void lcdCmd(uint8_t b){lcdSend(b,false);delay(2);}

// Standard HD44780 4-bit initialization sequence.
void lcdInit(){

  write595(0);delay(100);lcdNibble(3,false);delay(5);lcdNibble(3,false);

  delayMicroseconds(150);lcdNibble(3,false);lcdNibble(2,false);

  lcdCmd(0x28);lcdCmd(0x0C);lcdCmd(0x06);lcdCmd(0x01);

}

void lcdLine(uint8_t row,String s){

  lcdCmd(0x80+(row?0x40:0));s=s.substring(0,16);

  while(s.length()<16)s+=' ';

  for(size_t i=0;i<s.length();i++)lcdSend(s[i],true);

}

// --- MPU6500 I2C access ---
bool mpuRead(uint8_t reg,uint8_t *buf,size_t len){

  Wire.beginTransmission(mpuAddr);Wire.write(reg);

  if(Wire.endTransmission(false)!=0)return false;

  if(Wire.requestFrom((int)mpuAddr,(int)len)!=(int)len)return false;

  for(size_t i=0;i<len;i++)buf[i]=Wire.read();return true;

}

void mpuWrite(uint8_t reg,uint8_t val){Wire.beginTransmission(mpuAddr);Wire.write(reg);Wire.write(val);Wire.endTransmission();}

void setupMPU(){

  uint8_t who=0;

  for(uint8_t addr: {uint8_t(0x68),uint8_t(0x69)}){

    mpuAddr=addr;

    if(mpuRead(0x75,&who,1)){

      mpuFound=true;mpuWrite(0x6B,0);delay(100);mpuWrite(0x1C,0);

      Serial.printf("MPU detected at 0x%02X, WHO_AM_I=0x%02X\n",mpuAddr,who);return;

    }

  }

  Serial.println("MPU NOT FOUND - check SDA21/SCL22 and power.");

}

// DHT11 plus 16 MPU accelerometer samples; vibration is dynamic RMS.
void readSensors(){

  float t=dht.readTemperature(),h=dht.readHumidity();

  dhtValid=isfinite(t)&&isfinite(h);

  if(dhtValid){tempC=t;hum=h;}

  vibValid=false;

  if(!mpuFound)return;

  float x[16],y[16],z[16],mx=0,my=0,mz=0;bool ok=true;

  for(int i=0;i<16;i++){

    uint8_t b[6];if(!mpuRead(0x3B,b,6)){ok=false;break;}

    int16_t ax=(int16_t)((b[0]<<8)|b[1]);

    int16_t ay=(int16_t)((b[2]<<8)|b[3]);

    int16_t az=(int16_t)((b[4]<<8)|b[5]);

    x[i]=ax*(9.80665f/16384.0f);y[i]=ay*(9.80665f/16384.0f);z[i]=az*(9.80665f/16384.0f);

    mx+=x[i];my+=y[i];mz+=z[i];delay(3);

  }

  if(ok){

    mx/=16;my/=16;mz/=16;float sum=0;

    for(int i=0;i<16;i++){

      float dx=x[i]-mx,dy=y[i]-my,dz=z[i]-mz;

      sum+=dx*dx+dy*dy+dz*dz;

    }

    vib=sqrtf(sum/16);vibValid=true;

  }

}

// Evaluate sensor health first, then critical and warning limits.
Mode sensorMode(){

  if(!dhtValid||!vibValid)return WARNING_MODE; // Missing sensor => warning, not healthy.

  float v[3]={tempC,hum,vib};

  for(int i=0;i<3;i++)if(v[i]>=critLimit[i])return CRITICAL_MODE;

  for(int i=0;i<3;i++)if(v[i]>=warnLimit[i])return WARNING_MODE;

  return NORMAL_MODE;

}

Mode currentMode(){return mode==AUTO_MODE?sensorMode():mode;}

const char *modeName(Mode m){

  return m==NORMAL_MODE?"NORMAL":m==WARNING_MODE?"WARNING":m==CRITICAL_MODE?"CRITICAL":"AUTO";

}

String val(float x,bool ok,int digits){return ok?String(x,digits):String("N/A");}

// Update condition LEDs, buzzer alert pattern, and motor interlocks.
void updateOutputs(){

  Mode m=currentMode();

  digitalWrite(GREEN,m==NORMAL_MODE);

  digitalWrite(YELLOW,m==WARNING_MODE);

  digitalWrite(RED,m==CRITICAL_MODE);

  // Active buzzer: change alert duty/pattern, not actual acoustic volume.

  bool beep=false;

  if(m==CRITICAL_MODE && buzzerLevel>0){

    uint32_t period=buzzerLevel==1?1600:(buzzerLevel==2?800:400);

    beep=(millis()%period)<120;

  }

  digitalWrite(BUZZER,beep?HIGH:LOW);

  // Stop fan when critical, including real sensor critical during simulation.

  if(motorRunning && (!dhtValid || !vibValid)){
    latchStop("sensor data unavailable");
  } else if((m==CRITICAL_MODE || sensorMode()==CRITICAL_MODE) && motorRunning){
    latchStop("CRITICAL condition");
  }

}

// LCD pages 0-3: monitoring; page 4: editable threshold.
void updateLCD(){

  if(page==0){

    lcdLine(0,"Temp: "+val(tempC,dhtValid,1)+" C");

    lcdLine(1,"Hum: "+val(hum,dhtValid,0)+" %");

  }else if(page==1){

    lcdLine(0,"Vib: "+val(vib,vibValid,3));

    lcdLine(1,"State: "+String(modeName(currentMode())));

  }else if(page==2){

    lcdLine(0,"Fan: "+String(motorRunning?"RUN":"OFF")+(stopLatched?" STOP":""));

    lcdLine(1,"Mode: "+String(mode==AUTO_MODE?"AUTO":"TEST"));

  }else if(page==3){

    lcdLine(0,"Buzzer: "+String(buzzerLevel)+" (pattern)");

    lcdLine(1,"IR/BTN READY");

  }else{

    int digits=selectedMetric==2?2:1;

    float value=editCritical?critLimit[selectedMetric]:warnLimit[selectedMetric];

    lcdLine(0,String(metricNames[selectedMetric])+(editCritical?" CRIT LIMIT":" WARN LIMIT"));

    lcdLine(1,"Set: "+String(value,digits));

  }

}

// --- Serial status and threshold reporting ---
void printStatus(){

  Serial.printf("Temp=%s C | Hum=%s %% | Vib=%s m/s^2 | Condition=%s | Fan=%s | Armed=%d | Stop=%d | Beep=%d\n",

    val(tempC,dhtValid,1).c_str(),val(hum,dhtValid,0).c_str(),

    val(vib,vibValid,3).c_str(),modeName(currentMode()),motorRunning?"ON":"OFF",

    motorArmed,stopLatched,buzzerLevel);

}

void printThresholds(){

  Serial.printf("Limits: Temp W%.1f/C%.1f C; Hum W%.1f/C%.1f %%; Vib W%.2f/C%.2f m/s^2\n",

    warnLimit[0],critLimit[0],warnLimit[1],critLimit[1],warnLimit[2],critLimit[2]);

}

void setPage(uint8_t p){page=p;autoPages=false;lastLCD=0;}

// Enforce warning < critical; store valid edits in NVS flash.
void adjustThreshold(int direction){

  float &target=editCritical?critLimit[selectedMetric]:warnLimit[selectedMetric];

  float candidate=target+steps[selectedMetric]*direction;

  if(candidate<0)candidate=0;

  if(selectedMetric==1 && candidate>100)candidate=100;

  if(editCritical && candidate<=warnLimit[selectedMetric]){

    Serial.println("Rejected: critical limit must exceed warning limit.");return;

  }

  if(!editCritical && candidate>=critLimit[selectedMetric]){

    Serial.println("Rejected: warning limit must be below critical limit.");return;

  }

  target=candidate;

  prefs.putFloat(editCritical?metricKeysC[selectedMetric]:metricKeysW[selectedMetric],target);

  printThresholds();setPage(4);

}

// Clearing STOP never starts or arms the motor.
void resetStop(){

  // Return from test mode to actual sensor mode; don't reset into a critical state.

  mode=AUTO_MODE;

  if(sensorMode()==CRITICAL_MODE){

    Serial.println("RESET DENIED: sensor readings are CRITICAL.");return;

  }

  stopLatched=false;motorOff();motorArmed=false;

  Serial.println("STOP CLEARED. Fan still DISARMED; use M to arm.");

}

void selectMetric(int index){selectedMetric=index;setPage(4);printThresholds();}

// --- ELEGOO NEC remote: 21 mapped keys ---
void handleRemote(uint16_t cmd){

  Serial.printf("IR command 0x%02X\n",cmd);

  switch(cmd){

    case 0x45:latchStop("IR POWER");break;

    case 0x46:buzzerLevel=min(3,buzzerLevel+1);Serial.printf("Buzzer pattern=%d\n",buzzerLevel);break;

    case 0x47:mode=AUTO_MODE;autoPages=true;Serial.println("AUTO monitoring");break;

    case 0x44:setPage((page+4)%5);break;

    case 0x40:if(motorRunning){motorOff();Serial.println("Fan OFF");}else startFan();break;

    case 0x43:setPage((page+1)%5);break;

    case 0x07:adjustThreshold(-1);break;

    case 0x15:buzzerLevel=max(0,buzzerLevel-1);Serial.printf("Buzzer pattern=%d\n",buzzerLevel);break;

    case 0x09:adjustThreshold(+1);break;

    case 0x16:setPage(0);break;

    case 0x19:editCritical=!editCritical;setPage(4);Serial.println(editCritical?"Edit CRITICAL limit":"Edit WARNING limit");break;

    case 0x0D:resetStop();break;

    case 0x0C:mode=NORMAL_MODE;Serial.println("TEST NORMAL");break;

    case 0x18:mode=WARNING_MODE;Serial.println("TEST WARNING");break;

    case 0x5E:mode=CRITICAL_MODE;Serial.println("TEST CRITICAL");break;

    case 0x08: // remote 4: arm motor

      if(stopLatched || !dhtValid || !vibValid || sensorMode()==CRITICAL_MODE){Serial.println("ARM BLOCKED: stop, missing sensor, or critical condition.");}

      else {motorArmed=true;Serial.println("Motor ARMED. Fan remains OFF.");}

      break;

    case 0x1C:startFan();break; // remote 5: fan ON

    case 0x5A:motorOff();Serial.println("Fan OFF (arm retained)");break; // remote 6: fan OFF

    case 0x42:selectMetric(0);break;

    case 0x52:selectMetric(1);break;

    case 0x4A:selectMetric(2);break;

    default:Serial.println("Unmapped IR command");break;

  }

  updateLCD();

}

// Ignore repeat/overflow frames to avoid accidental repeated actions.
void pollRemote(){

  if(IrReceiver.decode()){

    auto data=IrReceiver.decodedIRData;

    if(data.protocol==NEC && data.address==0 &&

       !(data.flags & (IRDATA_FLAGS_IS_REPEAT | IRDATA_FLAGS_WAS_OVERFLOW))){

      handleRemote(data.command);

    }

    IrReceiver.resume();

  }

}

// Debounced active-LOW button: short release latches STOP.
void pollButton(){

  bool raw=digitalRead(BUTTON);

  uint32_t now=millis();

  if(raw!=lastRawButton){lastRawButton=raw;buttonChange=now;}

  if(now-buttonChange<35 || raw==stableButton)return;

  stableButton=raw;

  if(stableButton==LOW){buttonDownAt=now;longHandled=false;}

  else if(!longHandled){latchStop("physical button");}

}

// Hold >=2 seconds to request stop reset.
void pollButtonHold(){

  if(stableButton==LOW && !longHandled && millis()-buttonDownAt>=2000){

    longHandled=true;resetStop();

  }

}

// --- Serial Monitor command reference ---
void help(){

  Serial.println("SERIAL: A auto | N normal | W warning | C critical | P status | T thresholds | ? help");

  Serial.println("M arm (only after electrical verification) | F fan ON continuously | O fan OFF | X latch STOP/disarm | R reset STOP");

  Serial.println("IR: POWER stop; VOL+/VOL- buzzer pattern; FUNC auto; PREV/NEXT LCD; PLAY toggle fan");

  Serial.println("IR: DOWN/UP limit -/+; 0 overview; EQ warn/critical; ST/REPT reset; 1/2/3 simulation");

  Serial.println("IR: 4 ARM motor; 5 fan ON continuously; 6 fan OFF; 7/8/9 select temp/hum/vib limit");

  Serial.println("BUTTON: short press STOP latch; hold 2 seconds reset (only when sensors not critical).");

}

// --- Safe startup and hardware initialization ---
void setup(){

  digitalWrite(MOTOR_EN,LOW);pinMode(MOTOR_EN,OUTPUT);

  digitalWrite(MOTOR_IN1,LOW);pinMode(MOTOR_IN1,OUTPUT);

  digitalWrite(MOTOR_IN2,LOW);pinMode(MOTOR_IN2,OUTPUT);motorOff();

  Serial.begin(115200);delay(300);

  pinMode(GREEN,OUTPUT);pinMode(YELLOW,OUTPUT);pinMode(RED,OUTPUT);

  pinMode(BUZZER,OUTPUT);digitalWrite(BUZZER,LOW);

  pinMode(BUTTON,INPUT_PULLUP);

  pinMode(SR_DATA,OUTPUT);pinMode(SR_CLOCK,OUTPUT);pinMode(SR_LATCH,OUTPUT);

  Wire.begin(SDA_PIN,SCL_PIN);dht.begin();setupMPU();lcdInit();

  prefs.begin("iotmonitor",false);

  for(int i=0;i<3;i++){

    float w=prefs.getFloat(metricKeysW[i],warnLimit[i]);

    float c=prefs.getFloat(metricKeysC[i],critLimit[i]);

    if(isfinite(w)&&isfinite(c)&&w>=0&&c>w && (i!=1 || c<=100)){

      warnLimit[i]=w;critLimit[i]=c;

    }

  }

  IrReceiver.begin(IR_PIN,DISABLE_LED_FEEDBACK);

  lcdLine(0,"IoT Full Test");lcdLine(1,"Fan DISARMED");

  Serial.println("FULL SYSTEM TEST READY; fan OFF and DISARMED.");

  printThresholds();help();

}

// --- Main non-networked monitoring loop ---
void loop(){

  uint32_t now=millis();

  pollButton();pollButtonHold();pollRemote();

  while(Serial.available()){

    char c=toupper((unsigned char)Serial.read());

    switch(c){

      case 'A':mode=AUTO_MODE;Serial.println("AUTO");break;

      case 'N':mode=NORMAL_MODE;Serial.println("TEST NORMAL");break;

      case 'W':mode=WARNING_MODE;Serial.println("TEST WARNING");break;

      case 'C':mode=CRITICAL_MODE;Serial.println("TEST CRITICAL");break;

      case 'P':printStatus();break;

      case 'T':printThresholds();break;

      case 'M':if(stopLatched || !dhtValid || !vibValid || sensorMode()==CRITICAL_MODE)Serial.println("ARM BLOCKED: stop, missing sensor, or critical condition.");

               else {motorArmed=true;Serial.println("Motor ARMED - only if supply and fan rating verified.");}break;

      case 'F':startFan();break;

      case 'O':motorOff();Serial.println("Fan OFF (arm retained)");break;

      case 'X':latchStop("Serial X");break;

      case 'R':resetStop();break;

      case '?':help();break;

      default:break; // Ignore newlines and unrecognized chars.

    }

  }

  if(now-lastSample>=2000){lastSample=now;readSensors();}

  updateOutputs();

  if(autoPages && now-lastPage>=3000){lastPage=now;page=(page+1)%4;}

  if(now-lastLCD>=1000){lastLCD=now;updateLCD();}

  if(now-lastPrint>=2000){lastPrint=now;printStatus();}

}
