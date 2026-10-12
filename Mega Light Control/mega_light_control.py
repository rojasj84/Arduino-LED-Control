"""Separate left/right light windows sharing one Arduino Mega connection."""

import argparse
import tkinter as tk
from tkinter import ttk

from serial.tools import list_ports

from mega_connection import DemoSerial, MegaConnection

BG = "#25292e"
FG = "#f0f3f6"
CHANNELS = {1: ("Left", 5), 2: ("Right", 7)}
THEMES = {
    1: {"bg": "#11243b", "panel": "#193753", "accent": "#69baff", "active": "#24527b"},
    2: {"bg": "#351b23", "panel": "#522933", "accent": "#ff8994", "active": "#793845"},
}


class LightWindow:
    def __init__(self, app, channel):
        self.app = app
        self.channel = channel
        name, _ = CHANNELS[channel]
        self.theme = THEMES[channel]
        self.window = tk.Toplevel(app.root)
        self.window.title(f"{name} Light - Arduino Mega")
        self.window.geometry(f"320x560+{80 + (channel - 1) * 350}+160")
        self.window.minsize(320, 560)
        self.window.configure(bg=self.theme["bg"])
        self.window.protocol("WM_DELETE_WINDOW", lambda: app.hide_light(channel))
        frame = ttk.Frame(self.window, padding=20, style=f"{name}.TFrame")
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"{name} Light", style=f"{name}.Heading.TLabel").pack(pady=(0, 14))
        self.mode = tk.StringVar(value="Mode: --")
        self.mode_label = ttk.Label(frame, textvariable=self.mode, style=f"{name}.Mode.TLabel")
        self.mode_label.pack()
        self.mode_hint = tk.StringVar(value="Connect to read the LED mode")
        ttk.Label(frame, textvariable=self.mode_hint, style=f"{name}.TLabel").pack(pady=(4, 10))
        self.level_text = tk.StringVar(value="Intensity: --")
        ttk.Label(frame, textvariable=self.level_text, style=f"{name}.Level.TLabel").pack(pady=8)
        self.level = tk.DoubleVar(value=0)
        self.slider = ttk.Scale(frame, from_=100, to=0, orient="vertical",
                                variable=self.level, command=self.change, length=160,
                                style=f"{name}.Vertical.TScale")
        self.slider.pack(pady=8)
        buttons = ttk.Frame(frame, style=f"{name}.TFrame")
        buttons.pack(fill="x", pady=(12, 8))
        self.off_button = ttk.Button(buttons, text="Light off", command=self.off, style=f"{name}.TButton")
        self.off_button.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.all_off_button = ttk.Button(buttons, text="All lights off", command=app.all_off,
                                         state="disabled", style=f"{name}.TButton")
        self.all_off_button.pack(side="left", expand=True, fill="x", padx=(4, 0))
        ttk.Button(frame, text="Connection settings", style=f"{name}.TButton",
                   command=lambda: app.open_settings(channel)).pack(fill="x")
        if app.demo:
            ttk.Label(frame, text="DEMO - no hardware connected", style=f"{name}.Small.TLabel").pack(pady=(8, 0))
        ttk.Label(frame, textvariable=app.status, wraplength=275,
                  style=f"{name}.Small.TLabel").pack(fill="x", pady=(10, 0))
        self.pending = None
        self.update(None)

    def show(self):
        self.window.deiconify()
        self.window.lift()

    def cancel_pending(self):
        if self.pending is not None:
            self.window.after_cancel(self.pending)
            self.pending = None

    def change(self, value):
        self.cancel_pending()
        self.level_text.set(f"Intensity: {round(float(value))}%")
        self.pending = self.window.after(70, self.send)

    def send(self):
        self.pending = None
        if not self.app.connection.set_brightness(self.channel, self.level.get()):
            self.update(self.app.connection.states.get(self.channel))

    def off(self):
        self.cancel_pending()
        if self.app.connection.set_brightness(self.channel, 0):
            self.level.set(0)
            self.level_text.set("Intensity: 0%")

    def update(self, state):
        enabled = self.app.connection.ready and state is not None and state.mode == "REMOTE"
        self.slider.configure(state="normal" if enabled else "disabled")
        self.off_button.configure(state="normal" if enabled else "disabled")
        if not enabled:
            self.cancel_pending()
        if state is None:
            self.mode.set("Mode: --")
            self.mode_hint.set("Connect to read the LED mode")
            self.mode_label.configure(foreground=self.theme["accent"])
            self.level_text.set("Intensity: --")
        else:
            self.mode.set(state.mode)
            self.mode_hint.set("PC brightness control" if enabled else "Physical knob control")
            self.mode_label.configure(foreground=self.theme["accent"] if enabled else "#ffd28a")
            if self.pending is None:
                self.level.set(state.brightness * 100 / 255)
                self.level_text.set(f"Intensity: {round(self.level.get())}%")


class MegaLightApp:
    def __init__(self, root, demo=False):
        self.root = root
        self.demo = demo
        self.closing = False
        self.settings_window = None
        self.port_choices = {}
        self.root.title("Arduino Mega Light Control")
        # Tk owns the shared event loop without adding a third control window.
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("TButton", background="#3c434b", padding=6)
        style.map("TButton", background=[("active", "#515e6c")],
                  foreground=[("disabled", "#8b949e")])
        style.configure("TCombobox", fieldbackground="#3c434b", background="#3c434b")
        style.map("TCombobox", fieldbackground=[("readonly", "#3c434b")],
                  foreground=[("readonly", FG)])
        style.configure("TScale", troughcolor="#465361", background=BG)
        style.configure("Heading.TLabel", font=("Segoe UI", 17, "bold"))
        for channel, (name, _) in CHANNELS.items():
            theme = THEMES[channel]
            style.configure(f"{name}.TFrame", background=theme["bg"])
            style.configure(f"{name}.TLabel", background=theme["bg"], foreground=FG)
            style.configure(f"{name}.Heading.TLabel", background=theme["bg"],
                            foreground=theme["accent"], font=("Segoe UI", 22, "bold"))
            style.configure(f"{name}.Mode.TLabel", background=theme["bg"],
                            foreground=theme["accent"], font=("Segoe UI", 15, "bold"))
            style.configure(f"{name}.Level.TLabel", background=theme["bg"],
                            foreground=FG, font=("Segoe UI", 17))
            style.configure(f"{name}.Small.TLabel", background=theme["bg"],
                            foreground="#bfcede" if channel == 1 else "#dfbfc5", font=("Segoe UI", 9))
            style.configure(f"{name}.TButton", background=theme["panel"], foreground=FG, padding=7)
            style.map(f"{name}.TButton", background=[("active", theme["active"])],
                      foreground=[("disabled", "#8b949e")])
            style.configure(f"{name}.Vertical.TScale", background=theme["panel"],
                            troughcolor=theme["active"], sliderlength=25)
            style.map(f"{name}.Vertical.TScale", background=[("active", theme["accent"])])
        self.status = tk.StringVar(value="Disconnected")
        self.port_choice = tk.StringVar()
        self.build_monitor()
        options = {"serial_factory": DemoSerial, "boot_delay": 0} if demo else {}
        self.connection = MegaConnection(on_status=self.status.set, on_state=self.update_state,
                                         on_log=self.log, **options)
        self.lights = {c: LightWindow(self, c) for c in CHANNELS}
        for channel in CHANNELS:
            self.build_menu(channel)
        self.poll_job = self.root.after(50, self.poll)
        self.startup_job = self.root.after(100, self.auto_connect)

    def build_menu(self, owner):
        window = self.lights[owner].window
        theme = THEMES[owner]
        menu = tk.Menu(window, bg=theme["panel"], fg=FG)
        settings = tk.Menu(menu, tearoff=False)
        settings.add_command(label="COM port settings...", command=lambda: self.open_settings(owner))
        settings.add_command(label="Disconnect", command=self.disconnect)
        settings.add_separator()
        settings.add_command(label="Exit", command=self.close)
        menu.add_cascade(label="Settings", menu=settings)
        view = tk.Menu(menu, tearoff=False)
        for channel, (name, _) in CHANNELS.items():
            view.add_command(label=f"{name} light window", command=self.lights[channel].show)
        view.add_separator()
        view.add_command(label="Serial monitor", command=self.serial_window.deiconify)
        menu.add_cascade(label="View", menu=view)
        window.configure(menu=menu)

    def hide_light(self, channel):
        self.lights[channel].window.withdraw()
        if all(light.window.state() == "withdrawn" for light in self.lights.values()):
            self.close()

    def build_monitor(self):
        self.serial_window = tk.Toplevel(self.root)
        self.serial_window.title("Arduino Mega Serial Monitor")
        self.serial_window.geometry("680x350")
        self.serial_window.protocol("WM_DELETE_WINDOW", self.serial_window.withdraw)
        frame = ttk.Frame(self.serial_window, padding=10)
        frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        self.serial_output = tk.Text(frame, state="disabled", bg="#161b22", fg="#88ddaa",
                                     yscrollcommand=scrollbar.set, wrap="word")
        self.serial_output.pack(fill="both", expand=True)
        scrollbar.configure(command=self.serial_output.yview)
        self.serial_window.withdraw()

    def log(self, message):
        self.serial_output.configure(state="normal")
        self.serial_output.insert("end", message + "\n")
        if int(self.serial_output.index("end-1c").split(".")[0]) > 1000:
            self.serial_output.delete("1.0", "101.0")
        self.serial_output.see("end")
        self.serial_output.configure(state="disabled")

    def update_state(self, states):
        for channel, light in self.lights.items():
            state = states.get(channel)
            light.update(state)
        any_remote = self.connection.ready and any(state.mode == "REMOTE" for state in states.values())
        for light in self.lights.values():
            light.all_off_button.configure(state="normal" if any_remote else "disabled")

    def cancel_pending(self):
        for light in self.lights.values():
            light.cancel_pending()

    def all_off(self):
        self.cancel_pending()
        channels = self.connection.all_off()
        for channel in channels:
            self.lights[channel].level.set(0)
            self.lights[channel].level_text.set("Intensity: 0%")
        local = [CHANNELS[c][0].lower() for c, state in self.connection.states.items()
                 if state.mode == "LOCAL"]
        if local:
            self.log(f"All lights off: {', '.join(local)} light remains under its physical knob (LOCAL).")

    def disconnect(self):
        self.cancel_pending()
        # Best effort zero for remotely controlled channels before releasing USB.
        self.connection.all_off()
        self.connection.disconnect()

    def poll(self):
        self.poll_job = None
        if not self.closing:
            self.connection.poll()
            self.poll_job = self.root.after(50, self.poll)

    def refresh_ports(self):
        ports = list_ports.comports()
        self.port_choices = {f"{p.device} - {p.description}": p.device for p in ports}
        return list(self.port_choices)

    def auto_connect(self):
        self.startup_job = None
        if self.closing or self.connection.port is not None:
            return
        if self.demo:
            self.connection.connect("DEMO")
            return
        try:
            ports = list_ports.comports()
        except OSError as exc:
            self.log(f"Could not list COM ports: {exc}")
            return
        megas = [p for p in ports if "mega" in (p.description or "").lower()
                 or (p.vid, p.pid) in {(0x2341, 0x0042), (0x2A03, 0x0042),
                                      (0x2341, 0x0010), (0x2A03, 0x0010)}]
        if len(megas) == 1:
            port = megas[0]
            self.port_choice.set(f"{port.device} - {port.description}")
            self.connection.connect(port.device)
        else:
            self.status.set("Select the Mega COM port in Connection settings.")

    def open_settings(self, owner=1):
        if self.demo:
            self.log("Demo mode uses a simulated Mega. Restart without --demo for hardware.")
            self.serial_window.deiconify()
            return
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        dialog = self.settings_window = tk.Toplevel(self.root)
        dialog.title("Mega Connection Settings")
        dialog.resizable(False, False)
        dialog.transient(self.lights[owner].window)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Arduino Mega COM port (9600 baud)").pack(anchor="w")
        combo = ttk.Combobox(frame, textvariable=self.port_choice, state="readonly", width=55)
        combo.pack(fill="x", pady=10)
        def refresh():
            try:
                values = self.refresh_ports()
                combo.configure(values=values)
                if self.port_choice.get() not in values:
                    self.port_choice.set(values[0] if len(values) == 1 else "")
            except OSError as exc:
                self.log(f"Could not list COM ports: {exc}")
        def connect():
            selected = self.port_choices.get(self.port_choice.get())
            if not selected:
                self.status.set("Select a COM port first.")
                return
            self.disconnect()
            if self.connection.connect(selected):
                dialog.destroy()
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Button(row, text="Refresh", command=refresh).pack(side="left")
        ttk.Button(row, text="Disconnect", command=self.disconnect).pack(side="left", padx=8)
        ttk.Button(row, text="Connect", command=connect).pack(side="right")
        ttk.Label(frame, text="Close Arduino IDE Serial Monitor before connecting.").pack(pady=(12, 0))
        refresh()

    def close(self):
        if self.closing:
            return
        self.closing = True
        for job in (self.poll_job, self.startup_job):
            if job is not None:
                self.root.after_cancel(job)
        self.disconnect()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Preview with a simulated Mega")
    args = parser.parse_args()
    root = tk.Tk()
    app = MegaLightApp(root, demo=args.demo)
    try:
        root.mainloop()
    finally:
        if not app.closing:
            app.close()


if __name__ == "__main__":
    main()
