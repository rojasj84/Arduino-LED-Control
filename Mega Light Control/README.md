# Arduino Mega Light Control

A new PC controller for `Arduino Mega/laser_control_box.ino`. Both light windows
share one USB serial connection to the Mega at **9600 baud**. The original Nano
programs and Mega sketch are left in place.

## Run on Windows

1. Upload the existing `Arduino Mega/laser_control_box.ino` to an Arduino Mega
   2560 using the Arduino IDE. The sketch needs the `TM1637Display` library.
2. Connect the Mega by USB. Close the Arduino IDE Serial Monitor so the new app
   can open its COM port.
3. Install Python 3 with Tkinter and the serial dependency:
   `python -m pip install -r requirements.txt` (run from this folder).
4. Double-click **Start Mega Light Control.bat**, or run
   `python mega_light_control.py` from this folder.
5. Select the Mega in **Settings > COM port settings** if it isn't detected automatically.
   Move each physical mode switch to **REMOTE** to enable its PC controls.

Preview without connecting hardware: `python mega_light_control.py --demo`.
The shortcut uses `python` when available and falls back to the Windows `py -3`
launcher. It starts the GUI through `pythonw` so no console stays open alongside
the two light windows.

## Controls and wiring

| Window | Mega channel | PWM output | Local knob | Mode switch |
| --- | --- | --- | --- | --- |
| Left Light | LED1 (`L1`) | D5 | A0 | D30 |
| Right Light | LED2 (`L2`) | D7 | A1 | D31 |

Only two compact light control windows appear at startup: **L-Light** in blue and
**R-Light** in red, each with a percentage readout and vertical slider. The LED's
**LOCAL** or **REMOTE** mode appears below the slider. **Settings**, **Lights**,
and **View** menus are available in either window; both use the same connection.
Detailed connection status appears in the Settings menu and connection dialog.

Closing one light window hides it and leaves that light at its current level.
Use the other window's **View** menu to reopen it. Closing the last light window
exits the application. **Settings > Exit** in either window also exits both.
The serial monitor and connection dialog only appear when requested.

- Each slider sends a 0–100% request as `L1:0`–`L1:255` or `L2:0`–`L2:255`,
  followed by a newline. The Mega applies its existing current cap; the app does
  not rescale the request again.
- **Lights > Light off** turns off that window's channel. **Lights > All lights
  off** sends zero to every channel
  currently reported as REMOTE. LOCAL channels remain controlled by their knobs;
  switch them to REMOTE or turn their knobs down to turn them off.
- Dragging sends its first changed brightness immediately and streams the latest
  value at up to 40 updates per second, sending the final value on mouse release.
  Identical PWM values are skipped; older status replies do not pull the thumb
  backward while dragging. This works with the existing 9600-baud Mega sketch;
  no firmware update is needed for the new interface or slider behavior.
- `Q` normally polls the Mega every half second. During slider activity, it
  prefers a 150 ms pause in brightness traffic, while still querying modes at
  least once a second when the previous reply has arrived. Windows display brightness and
  LOCAL/REMOTE mode. Flipper mirror TTL signals aren't displayed in the light
  controls. Laser feedback isn't included in the sketch's JSON reply and isn't
  displayed in this app.
- The app waits for the Mega reset and a valid status reply before enabling
  sliders. LOCAL controls are disabled. It does not send saved brightness on
  reconnect. A lost or unresponsive connection disables all controls.
- Disconnecting or exiting tries to turn off REMOTE channels before closing the
  port. USB failure cannot guarantee delivery; the supplied sketch retains its
  current brightness without a PC connection. LOCAL channels remain local.
- **View > Serial monitor** shows outgoing commands and device responses.

If left and right are wired the other way around, change the labels in `CHANNELS`
at the top of `mega_light_control.py`, or swap the driver connections to D5/D7.
The supplied Mega design has two LED channels; additional LEDs require firmware
and wiring changes.

## Verification

Run `python -m unittest discover -s tests -v` from this folder. Tests use simulated
serial I/O, including fragmented replies, independent channels, LOCAL mode,
disconnects, timeouts and query pacing during dragging. GUI checks exercise
immediate and continuous drag updates, final release, stale status replies,
compact layouts and separate window themes using the real Tk widgets with a
simulated Mega. Physical hardware still needs a bench check.
