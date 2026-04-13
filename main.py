import tkinter as tk
from tkinter import ttk
import serial
import time
import serial.tools.list_ports # Import for listing serial ports

# --- CONFIGURATION ---
BAUD_RATE = 115200
arduino = None

def get_ports():
    """Get available COM ports and format them for the dropdown."""
    ports = serial.tools.list_ports.comports()
    return [f"{port.device} - {port.description}" for port in ports]

def connect_arduino():
    """Connect to the selected COM port."""
    global arduino
    selected_port = port_var.get()
    if not selected_port:
        log_message("Please select a COM port.\n")
        return
        
    port_name = selected_port.split(" - ")[0]
    
    if arduino and arduino.is_open:
        arduino.close()
        
    try:
        arduino = serial.Serial(port_name, BAUD_RATE, timeout=0.1)
        time.sleep(2)  # Wait for Arduino to reset after connection
        log_message(f"Connected to {port_name}\n")
    except Exception as e:
        log_message(f"Error connecting: {e}\n")
        arduino = None

def read_serial():
    """Periodically check for serial data and display it."""
    if arduino and arduino.is_open:
        try:
            if arduino.in_waiting > 0:
                data = arduino.read(arduino.in_waiting).decode('utf-8', errors='replace')
                log_message(data)
        except Exception:
            pass
    root.after(100, read_serial)

def open_com_dialog():
    """Opens a dialog to select and connect to a COM port."""
    dialog = tk.Toplevel(root)
    dialog.title("Connection Settings")
    dialog.geometry("420x80")
    dialog.transient(root)
    dialog.grab_set()
    
    frame = ttk.Frame(dialog, padding="15")
    frame.pack(fill="both", expand=True)
    
    ttk.Label(frame, text="Port:").pack(side="left")
    port_cb = ttk.Combobox(frame, textvariable=port_var, values=get_ports(), width=28, state="readonly")
    port_cb.pack(side="left", padx=5)
    
    ttk.Button(frame, text="Refresh", command=lambda: port_cb.config(values=get_ports())).pack(side="left", padx=2)
    ttk.Button(frame, text="Connect", command=lambda: [connect_arduino(), dialog.destroy()]).pack(side="left", padx=2)

def send_values(val):
    """Formats slider value as percentage, maps to 0-255, and sends to Arduino."""
    percent = int(float(val))
    intensity_label.config(text=f"Intensity: {percent}%")
    if arduino and arduino.is_open:
        # Map 0-100% to 0-255 for Arduino PWM
        pwm_val = int(percent * 2.55)
        command = f"{pwm_val}\n"
        try:
            arduino.write(command.encode())
        except Exception as e:
            log_message(f"Error sending: {e}\n")

def log_message(msg):
    """Inserts text into the serial output box."""
    serial_output.config(state=tk.NORMAL)
    serial_output.insert(tk.END, msg)
    serial_output.see(tk.END)
    serial_output.config(state=tk.DISABLED)

# --- GUI SETUP ---
root = tk.Tk()
root.title("Arduino Single Light Control")
root.geometry("400x350")

port_var = tk.StringVar()

# --- MENU BAR ---
menubar = tk.Menu(root)
settings_menu = tk.Menu(menubar, tearoff=0)
settings_menu.add_command(label="COM Port Settings...", command=open_com_dialog)
menubar.add_cascade(label="Settings", menu=settings_menu)
root.config(menu=menubar)

main_frame = ttk.Frame(root, padding="20")
main_frame.pack(expand=True, fill="both")

ttk.Label(main_frame, text="Remote Light Control", font=('Segoe UI', 16, 'bold')).pack(pady=(10, 5))

control_frame = ttk.LabelFrame(main_frame, text="LED Control (Pin 5)", padding="15")
control_frame.pack(fill="x", pady=10)

intensity_label = ttk.Label(control_frame, text="Intensity: 0%", font=('Segoe UI', 12))
intensity_label.pack(pady=(0, 10))

slider = ttk.Scale(control_frame, from_=0, to=100, orient="horizontal", command=send_values)
slider.pack(fill="x")

# --- SERIAL OUTPUT ---
ttk.Label(main_frame, text="Serial Output:", font=('Arial', 10, 'bold')).pack(anchor="w", pady=(15, 5))

output_frame = ttk.Frame(main_frame)
output_frame.pack(expand=True, fill="both")

scrollbar = ttk.Scrollbar(output_frame)
scrollbar.pack(side="right", fill="y")

serial_output = tk.Text(output_frame, height=8, yscrollcommand=scrollbar.set, state=tk.DISABLED)
serial_output.pack(expand=True, fill="both")
scrollbar.config(command=serial_output.yview)

root.after(100, read_serial) # Start serial reading loop
root.mainloop()

# Close serial port on exit
if arduino and arduino.is_open:
    arduino.close()