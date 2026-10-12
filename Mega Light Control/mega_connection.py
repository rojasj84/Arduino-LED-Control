"""Nonblocking connection to the existing laser_control_box.ino protocol."""

import json
import time
from dataclasses import dataclass

import serial

BAUD_RATE = 9600


@dataclass(frozen=True)
class ChannelState:
    mode: str
    brightness: int
    ttl: bool


def percent_to_pwm(value):
    return round(max(0, min(100, float(value))) * 255 / 100)


def parse_state(line):
    """Only accept complete replies from the two-channel Mega sketch."""
    try:
        data = json.loads(line)
        states = {}
        for channel in (1, 2):
            mode = data[f"mode{channel}"]
            level = data[f"led{channel}"]
            ttl = data[f"ttl{channel}"]
            if mode not in ("LOCAL", "REMOTE"):
                return None
            if type(level) is not int or not 0 <= level <= 255:
                return None
            if type(ttl) is not bool:
                return None
            states[channel] = ChannelState(mode, level, ttl)
        return states
    except (ValueError, KeyError, TypeError):
        return None


class MegaConnection:
    """One serial owner shared by every light window; call poll from Tk."""

    QUERY_INTERVAL = 0.5
    RESPONSE_TIMEOUT = 3.0
    HANDSHAKE_TIMEOUT = 5.0
    QUERY_IDLE_TIME = 0.15
    MAX_QUERY_INTERVAL = 1.0

    def __init__(self, on_status=None, on_state=None, on_log=None,
                 serial_factory=serial.Serial, clock=time.monotonic,
                 boot_delay=2.0):
        self.on_status = on_status or (lambda message: None)
        self.on_state = on_state or (lambda states: None)
        self.on_log = on_log or (lambda message: None)
        self.serial_factory = serial_factory
        self.clock = clock
        self.boot_delay = boot_delay
        self.port = None
        self.port_name = ""
        self.ready = False
        self.states = {}
        self.buffer = bytearray()
        self.boot_until = 0
        self.next_query = 0
        self.last_reply = None
        self.awaiting_query = False
        self.last_brightness_write = None
        self.last_query_time = None

    def connect(self, port_name):
        self.disconnect()
        try:
            self.port = self.serial_factory(
                port_name, BAUD_RATE, timeout=0, write_timeout=0.15)
            self.port_name = port_name
            self.boot_until = self.clock() + self.boot_delay
            self.next_query = self.boot_until
            self.on_status(f"Connecting to {port_name} - waiting for Mega...")
            self.on_log(f"Opened {port_name} at {BAUD_RATE} baud.")
            return True
        except (serial.SerialException, OSError) as exc:
            self.disconnect(f"Connection failed: {exc}")
            return False

    def disconnect(self, message="Disconnected"):
        if self.port is not None:
            try:
                self.port.close()
            except (serial.SerialException, OSError):
                pass
        self.port = None
        self.ready = False
        self.states = {}
        self.buffer.clear()
        self.last_reply = None
        self.awaiting_query = False
        self.last_brightness_write = None
        self.last_query_time = None
        self.on_state({})
        self.on_status(message)

    def _write(self, command):
        if self.port is None:
            return False
        try:
            packet = command.encode("ascii")
            if self.port.write(packet) != len(packet):
                raise serial.SerialTimeoutException("Incomplete serial write")
            self.on_log(f"> {command.strip()}")
            return True
        except (serial.SerialException, OSError) as exc:
            self.disconnect(f"Serial connection lost: {exc}")
            self.on_log(f"Serial error: {exc}")
            return False

    def poll(self):
        if self.port is None:
            return
        now = self.clock()
        try:
            available = self.port.in_waiting
            if available:
                self.buffer.extend(self.port.read(min(available, 4096)))
        except (serial.SerialException, OSError) as exc:
            self.disconnect(f"Serial connection lost: {exc}")
            return

        while b"\n" in self.buffer:
            raw, _, remainder = self.buffer.partition(b"\n")
            self.buffer = bytearray(remainder)
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            self.on_log(line)
            states = parse_state(line)
            # A valid unsolicited line must not enable an unverified device.
            if states is not None and self.awaiting_query:
                self.states = states
                self.last_reply = now
                self.awaiting_query = False
                self.ready = True
                self.on_status(f"Connected to {self.port_name} - Arduino Mega")
                self.on_state(dict(states))
        if len(self.buffer) > 8192:
            self.buffer.clear()
            self.on_log("Discarded oversized serial line.")

        if not self.ready and now >= self.boot_until + self.HANDSHAKE_TIMEOUT:
            self.disconnect("No Mega status reply. Check COM port, sketch and 9600 baud.")
            return
        if self.ready and now - self.last_reply >= self.RESPONSE_TIMEOUT:
            self.disconnect("Mega stopped responding. Reconnect to continue.")
            return
        # At 9600 baud the sketch's large JSON reply can occupy the board's
        # serial buffer. Prefer a brief gap in slider traffic, but keep polling
        # at least once per second to observe physical LOCAL/REMOTE switches.
        brightness_active = (self.last_brightness_write is not None and
                             now - self.last_brightness_write < self.QUERY_IDLE_TIME)
        query_overdue = (self.last_query_time is None or
                         now - self.last_query_time >= self.MAX_QUERY_INTERVAL)
        if (now >= self.next_query and not self.awaiting_query and
                (not brightness_active or query_overdue)):
            if self._write("Q\n"):
                self.awaiting_query = True
                self.last_query_time = now
                self.next_query = now + self.QUERY_INTERVAL

    def set_brightness(self, channel, percent):
        state = self.states.get(channel)
        if not self.ready or state is None or state.mode != "REMOTE":
            return False
        if self._write(f"L{channel}:{percent_to_pwm(percent)}\n"):
            self.last_brightness_write = self.clock()
            return True
        return False

    def all_off(self):
        """Return channels successfully sent zero; LOCAL channels remain local."""
        return [channel for channel in (1, 2)
                if self.set_brightness(channel, 0)]


class DemoSerial:
    """In-memory Mega for previewing the UI without opening a COM port."""

    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.levels = {1: 0, 2: 0}
        self.modes = {1: "REMOTE", 2: "REMOTE"}
        self.buffer = bytearray()

    @property
    def in_waiting(self):
        return len(self.buffer)

    def read(self, count):
        result = bytes(self.buffer[:count])
        del self.buffer[:count]
        return result

    def write(self, packet):
        command = packet.decode("ascii").strip()
        if command == "Q":
            state = {}
            for channel in (1, 2):
                state.update({f"mode{channel}": self.modes[channel],
                              f"led{channel}": self.levels[channel],
                              f"ttl{channel}": False})
            self.buffer.extend((json.dumps(state) + "\n").encode("ascii"))
        elif command.startswith(("L1:", "L2:")):
            channel = int(command[1])
            if self.modes[channel] == "REMOTE":
                self.levels[channel] = int(command.split(":")[1])
        return len(packet)

    def close(self):
        self.is_open = False
