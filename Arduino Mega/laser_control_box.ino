// Arduino Mega 2560 R3 - Full System Sketch
// ---------------------------------------------------------------
// TTL Outputs      : Pin 53 (TTL1), Pin 48 (TTL2)
// 3-way Momentary 1: Pin 43 (HIGH), Pin 45 (LOW)
// 3-way Momentary 2: Pin 49 (HIGH), Pin 47 (LOW)
// Pots             : A0 (LED1), A1 (LED2)
// PWM LED Drivers  : Pin 5 (LED1 FemtoBuck), Pin 7 (LED2 FemtoBuck)
// Laser Feedback   : A2 (Laser1 0-4V), A3 (Laser2 0-4V)
// TM1637 Display 1 : CLK=22, DIO=23
// TM1637 Display 2 : CLK=24, DIO=25
// SPST Mode Switch1: Pin 30 (LOCAL=HIGH, REMOTE=LOW)
// SPST Mode Switch2: Pin 31 (LOCAL=HIGH, REMOTE=LOW)
// Serial           : 9600 baud, USB
// ---------------------------------------------------------------
// Serial commands (Remote mode):
//   L1:<0-255>\n  → Set LED1 brightness
//   L2:<0-255>\n  → Set LED2 brightness
//   Q\n           → Query current state (returns JSON)
// ---------------------------------------------------------------

#include <Wire.h>
#include <TM1637Display.h>

// --- TTL Pins ---
const int TTL1_PIN      = 53;
const int TTL2_PIN      = 48;

// --- 3-way Momentary Switch 1 (TTL1) ---
const int SW1_HIGH      = 43;
const int SW1_LOW       = 45;

// --- 3-way Momentary Switch 2 (TTL2) ---
const int SW2_HIGH      = 49;
const int SW2_LOW       = 47;

// --- Pots ---
const int POT_1         = A0;
const int POT_2         = A1;

// --- PWM Output to FemtoBuck LED Drivers ---
const int PWM_LED1      = 5;
const int PWM_LED2      = 7;

// --- LED Current Limits ---
// The driver sources DRIVER_MAX_MA at 100% PWM duty. Each LED channel is
// capped so a full-scale user request (pot at max / serial 255) never
// exceeds that LED's rated current. EDIT THESE to match the LEDs installed.
const int DRIVER_MAX_MA = 750;  // driver output at 100% duty
const int LED1_MAX_MA   = 700;   // LED1 rated max current
const int LED2_MAX_MA   = 700;    // LED2 rated max current

// Max PWM duty (0-255) allowed per channel, computed from the ratios above.
// (long math avoids int overflow: 255*700 > 32767)
const uint8_t PWM1_MAX = (uint8_t)((255L * LED1_MAX_MA) / DRIVER_MAX_MA);
const uint8_t PWM2_MAX = (uint8_t)((255L * LED2_MAX_MA) / DRIVER_MAX_MA);

// --- Laser Feedback Analog Inputs ---
const int LASER1_PIN    = A2;
const int LASER2_PIN    = A3;

// --- TM1637 Displays ---
const int CLK1          = 22;
const int DIO1          = 23;
const int CLK2          = 24;
const int DIO2          = 25;
TM1637Display display1(CLK1, DIO1);
TM1637Display display2(CLK2, DIO2);

// --- SPST Mode Switches ---
const int MODE_SW1      = 30;
const int MODE_SW2      = 31;

// --- State ---
bool ttl1State          = false;
bool ttl2State          = false;
uint8_t led1Brightness  = 0;
uint8_t led2Brightness  = 0;

// --- TTL debug print tracking ---
bool ttl1StatePrinted   = false;
bool ttl2StatePrinted   = false;
bool ttlStatusEverPrinted = false;

// --- Serial ---
String serialBuffer     = "";

void setup() {
  Serial.begin(9600);

  // TTL pins
  pinMode(TTL1_PIN,  OUTPUT); digitalWrite(TTL1_PIN, LOW);
  pinMode(TTL2_PIN,  OUTPUT); digitalWrite(TTL2_PIN, LOW);

  // Momentary switches
  pinMode(SW1_HIGH,  INPUT_PULLUP);
  pinMode(SW1_LOW,   INPUT_PULLUP);
  pinMode(SW2_HIGH,  INPUT_PULLUP);
  pinMode(SW2_LOW,   INPUT_PULLUP);

  // Mode switches
  pinMode(MODE_SW1,  INPUT_PULLUP);
  pinMode(MODE_SW2,  INPUT_PULLUP);

  // PWM
  pinMode(PWM_LED1,  OUTPUT);
  pinMode(PWM_LED2,  OUTPUT);
  analogWrite(PWM_LED1, 0);
  analogWrite(PWM_LED2, 0);

  // Displays
  display1.setBrightness(7);
  display2.setBrightness(7);
  display1.showNumberDecEx(0, 0b01000000, false); // "00.0"
  display2.showNumberDecEx(0, 0b01000000, false);
}

// --- Show x.x% on TM1637 (value = 0-1000 representing 0.0-100.0) ---
void showPercent(TM1637Display &disp, int tenths) {
  tenths = constrain(tenths, 0, 1000);
  // Display as 4 digits with decimal point after 3rd digit
  // e.g. 756 = "75.6", 1000 = "100.0" shown as "100.0"
  if (tenths >= 1000) {
    // Show "100.0" — use raw segments for "100.0"
    uint8_t segs[] = {
      disp.encodeDigit(1),
      disp.encodeDigit(0),
      disp.encodeDigit(0) | 0x80, // decimal point
      disp.encodeDigit(0)
    };
    disp.setSegments(segs);
  } else {
    disp.showNumberDecEx(tenths, 0b00100000, true); // decimal after 3rd digit
  }
}

// --- Read laser % (0-4V mapped to 0.0-100.0, returned as tenths 0-1000) ---
// Oversamples the ADC to knock down high-frequency noise before mapping.
int readLaserPercent(int pin) {
  const int NUM_SAMPLES = 8;
  long sum = 0;
  for (int i = 0; i < NUM_SAMPLES; i++) {
    sum += analogRead(pin);
  }
  int raw = sum / NUM_SAMPLES;
  // 0-4V on 5V ADC = 0-819 raw
  int tenths = map(raw, 0, 819, 0, 1000);
  return constrain(tenths, 0, 1000);
}

// --- Exponential moving average filter for display smoothing ---
// Slows down how fast the displayed value can change so residual jitter
// after oversampling doesn't show up as a flickering digit.
float laser1Filtered = -1;  // -1 = not yet seeded
float laser2Filtered = -1;
const float LASER_SMOOTHING_ALPHA = 0.15; // lower = smoother but slower to respond

int filterLaserReading(float &filtered, int rawTenths) {
  if (filtered < 0) {
    filtered = rawTenths; // seed with first real reading
  } else {
    filtered += LASER_SMOOTHING_ALPHA * (rawTenths - filtered);
  }
  return (int)(filtered + 0.5);
}

// --- Parse incoming serial commands ---
void handleSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      serialBuffer.trim();

      if (serialBuffer.startsWith("L1:")) {
        int val = serialBuffer.substring(3).toInt();
        led1Brightness = constrain(val, 0, 255);
      } else if (serialBuffer.startsWith("L2:")) {
        int val = serialBuffer.substring(3).toInt();
        led2Brightness = constrain(val, 0, 255);
      } else if (serialBuffer == "Q") {
        // Report current state as JSON
        Serial.print("{\"mode1\":\"");
        Serial.print(digitalRead(MODE_SW1) == HIGH ? "LOCAL" : "REMOTE");
        Serial.print("\",\"mode2\":\"");
        Serial.print(digitalRead(MODE_SW2) == HIGH ? "LOCAL" : "REMOTE");
        Serial.print("\",\"led1\":");
        Serial.print(led1Brightness);
        Serial.print(",\"led2\":");
        Serial.print(led2Brightness);
        Serial.print(",\"ttl1\":");
        Serial.print(ttl1State ? "true" : "false");
        Serial.print(",\"ttl2\":");
        Serial.print(ttl2State ? "true" : "false");
        Serial.print(",\"sw1_high_raw\":");
        Serial.print(digitalRead(SW1_HIGH));
        Serial.print(",\"sw1_low_raw\":");
        Serial.print(digitalRead(SW1_LOW));
        Serial.print(",\"sw2_high_raw\":");
        Serial.print(digitalRead(SW2_HIGH));
        Serial.print(",\"sw2_low_raw\":");
        Serial.print(digitalRead(SW2_LOW));
        Serial.println("}");
      }

      serialBuffer = "";
    } else {
      serialBuffer += c;
    }
  }
}

void loop() {

  // --- TTL 1 Switch ---
  if (digitalRead(SW1_HIGH) == LOW) {
    ttl1State = true;
    digitalWrite(TTL1_PIN, HIGH);
  } else if (digitalRead(SW1_LOW) == LOW) {
    ttl1State = false;
    digitalWrite(TTL1_PIN, LOW);
  }

  // --- TTL 2 Switch ---
  if (digitalRead(SW2_HIGH) == LOW) {
    ttl2State = true;
    digitalWrite(TTL2_PIN, HIGH);
  } else if (digitalRead(SW2_LOW) == LOW) {
    ttl2State = false;
    digitalWrite(TTL2_PIN, LOW);
  }

  // --- Print TTL status whenever it changes ---
  if (!ttlStatusEverPrinted || ttl1State != ttl1StatePrinted || ttl2State != ttl2StatePrinted) {
    Serial.print("TTL1: ");
    Serial.print(ttl1State ? "ON" : "OFF");
    Serial.print("  TTL2: ");
    Serial.println(ttl2State ? "ON" : "OFF");
    ttl1StatePrinted = ttl1State;
    ttl2StatePrinted = ttl2State;
    ttlStatusEverPrinted = true;
  }

  // --- LED Control ---
  bool local1 = (digitalRead(MODE_SW1) == HIGH);
  bool local2 = (digitalRead(MODE_SW2) == HIGH);

  if (local1) {
    led1Brightness = map(analogRead(POT_1), 0, 1023, 0, 255);
  }

  if (local2) {
    led2Brightness = map(analogRead(POT_2), 0, 1023, 0, 255);
  }

  // Remote mode: brightness set via serial, pots ignored
  handleSerial();

  // Scale the 0-255 user request onto the safe PWM range for each LED,
  // so 100% from the pot or serial = the LED's max current, never the
  // driver's full 1200 mA.
  analogWrite(PWM_LED1, map(led1Brightness, 0, 255, 0, PWM1_MAX));
  analogWrite(PWM_LED2, map(led2Brightness, 0, 255, 0, PWM2_MAX));

  // --- Laser Feedback → Displays ---
  int laser1Tenths = filterLaserReading(laser1Filtered, readLaserPercent(LASER1_PIN));
  int laser2Tenths = filterLaserReading(laser2Filtered, readLaserPercent(LASER2_PIN));
  showPercent(display1, laser1Tenths);
  showPercent(display2, laser2Tenths);

  delay(20);
}
