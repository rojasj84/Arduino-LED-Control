# Laser Control Box Pinout & System Summary

This document provides a comprehensive summary of the pin configuration, peripheral connections, and system logic for the **Laser Control Box** based on the Arduino Mega 2560 R3.

---

## 1. Pin Configuration Table

| Pin Number | Pin Label | Component / Connection | Type | Description |
|:---:|---|---|:---:|---|
| **D5** | `PWM_LED1` | LED1 FemtoBuck Driver | PWM Output | Control PWM signal for LED Channel 1 |
| **D7** | `PWM_LED2` | LED2 FemtoBuck Driver | PWM Output | Control PWM signal for LED Channel 2 |
| **D22** | `CLK1` | TM1637 Display 1 CLK | Digital Output | Clock line for Display 1 |
| **D23** | `DIO1` | TM1637 Display 1 DIO | Digital I/O | Data line for Display 1 |
| **D24** | `CLK2` | TM1637 Display 2 CLK | Digital Output | Clock line for Display 2 |
| **D25** | `DIO2` | TM1637 Display 2 DIO | Digital I/O | Data line for Display 2 |
| **D30** | `MODE_SW1` | SPST Mode Switch 1 | Digital Input (Pullup) | LOCAL mode when HIGH, REMOTE mode when LOW (Channel 1) |
| **D31** | `MODE_SW2` | SPST Mode Switch 2 | Digital Input (Pullup) | LOCAL mode when HIGH, REMOTE mode when LOW (Channel 2) |
| **D43** | `SW1_HIGH` | 3-way Momentary Switch 1 (Up) | Digital Input (Pullup) | Set TTL1 to ON / HIGH |
| **D45** | `SW1_LOW` | 3-way Momentary Switch 1 (Down) | Digital Input (Pullup) | Set TTL1 to OFF / LOW |
| **D47** | `SW2_LOW` | 3-way Momentary Switch 2 (Down) | Digital Input (Pullup) | Set TTL2 to OFF / LOW |
| **D48** | `TTL2_PIN` | TTL Output 2 | Digital Output | Control TTL Channel 2 |
| **D49** | `SW2_HIGH` | 3-way Momentary Switch 2 (Up) | Digital Input (Pullup) | Set TTL2 to ON / HIGH |
| **D53** | `TTL1_PIN` | TTL Output 1 | Digital Output | Control TTL Channel 1 |
| **A0** | `POT_1` | Potentiometer 1 | Analog Input | Local brightness control for LED Channel 1 |
| **A1** | `POT_2` | Potentiometer 2 | Analog Input | Local brightness control for LED Channel 2 |
| **A2** | `LASER1_PIN` | Laser 1 Feedback (0-4V) | Analog Input | Laser 1 voltage feedback |
| **A3** | `LASER2_PIN` | Laser 2 Feedback (0-4V) | Analog Input | Laser 2 voltage feedback |

---

## 2. Functional Description

### 2.1 Mode Control (LOCAL vs. REMOTE)
* **Mode Switches (`MODE_SW1` / `MODE_SW2`)**:
  * **LOCAL Mode (Switch state = HIGH)**: LED brightness is directly mapped from the respective analog potentiometer (`POT_1` or `POT_2`).
  * **REMOTE Mode (Switch state = LOW)**: LED brightness commands are received over USB Serial. Potentiometer inputs are ignored.

### 2.2 LED Brightness & Current Safeguards
To protect the connected LEDs, a firmware current cap is implemented. The maximum PWM duty cycle is scaled based on the ratio between the rated max current of the LED and the max output of the FemtoBuck driver:
* **Driver Maximum Output**: 750 mA
* **LED1 / LED2 Maximum Rating**: 700 mA
* **Maximum Safe PWM Duty**: `238` out of `255` (~93.3% maximum output power)

The system automatically scales the input range (0-255 from either pot or serial) to a safe output range of `0` to `PWM_MAX` (238) before outputting to pins `D5` and `D7`.

### 2.3 TTL Output Logic (Momentary Switches)
The system uses 3-way momentary switches (biased to center-off, where pins read HIGH due to internal pullups) to control the TTL outputs:
* **Switch Up (Pin pulled LOW)**: Forces the corresponding TTL Output (`TTL1_PIN` / `TTL2_PIN`) to **HIGH**.
* **Switch Down (Pin pulled LOW)**: Forces the corresponding TTL Output to **LOW**.
* **Switch Idle (Center position)**: The output remains in its last set state.

### 2.4 Laser Feedback & Displays
* **Oversampling**: The feedback voltages on pins `A2` and `A3` are read 8 times and averaged to filter high-frequency noise.
* **Voltage Mapping**: The 0-4V range maps to a 0-819 analog read value, which is then mapped to `0.0%` to `100.0%`.
* **Smoothing**: An exponential moving average (EMA) filter with an alpha of `0.15` is applied to eliminate display flicker.
* **Displays**: The results are shown on two TM1637 4-digit displays.

### 2.5 Serial Interface (9600 Baud)
When channels are in REMOTE mode, they respond to the following serial commands:
* `L1:<0-255>\n`: Sets LED1 brightness.
* `L2:<0-255>\n`: Sets LED2 brightness.
* `Q\n`: Queries the current state of the device, returning a JSON block with the status of all modes, LEDs, TTL lines, and switch inputs.

---

## 3. Fiber Laser DB-15 Pinout Summary

This section summarizes the DB-15 connections for the fiber laser, cross-referencing handwritten pinout notes with the official interface signal names.

| DB-15 Pin | Original Wire # | Wire Color | Official Signal Name / Function |
|:---:|:---:|---|---|
| **1** | 12 | Red | Analog Current Control Input (10V DC Var) |
| **2** | 13 | Orange Thick | Analog Power Monitor Output |
| **3** | 14 | Black | Isolated Analog Com |
| **7** | 15 | Blue | Modulation+ |
| **8** | 16 | Black | Modulation- |
| **9** | 18 | White thin | Emission Enable |
| **10** | 20 | Black thin | System Common |
| **11** | 24 | White thick | Emission ON (Indicator) |
| **14** | 10 | Yellow | Remote Start Button |
| **15** | 11 | Grey | Remote Start Button |

### 3.1 Additional Interlock & System Notes
* **DB-15 Pins 14 and 15 (Original Wires 10 & 11)**: Function as a temporary short for the Remote Start Button.
* **Original Wires 1, 2, 3, and 4 (Green)**: Shorted internally. These correspond to the safety interlocks: Interlock Ch1A, Interlock Ch2A, Interlock Ch2B, and Interlock Ch1B.
* **Original Wires 8 and 9 (Grey)**: Shorted internally. These correspond to the Remote Key Switch.
* **Black thick long wire**: Connected to the body of the connector.
