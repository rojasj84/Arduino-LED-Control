import json
import unittest

import serial

from mega_connection import (ChannelState, DemoSerial, MegaConnection,
                             parse_state, percent_to_pwm)


class FakeClock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.buffer = bytearray()
        self.commands = []
        self.closed = False
        self.fail_read = False
        self.fail_write = False
        self.short_write = False

    @property
    def in_waiting(self):
        if self.fail_read:
            raise serial.SerialException("Unplugged")
        return len(self.buffer)

    def read(self, count):
        data = bytes(self.buffer[:count])
        del self.buffer[:count]
        return data

    def write(self, packet):
        if self.fail_write:
            raise serial.SerialException("Unplugged")
        self.commands.append(packet)
        return len(packet) - 1 if self.short_write else len(packet)

    def close(self):
        self.closed = True

    def reply(self, mode1="REMOTE", mode2="REMOTE", led1=0, led2=0):
        self.buffer.extend((json.dumps(dict(mode1=mode1, mode2=mode2, led1=led1,
                                           led2=led2, ttl1=False, ttl2=True)) + "\n").encode())


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.port = FakeSerial()
        self.states = []
        self.statuses = []
        self.factory_args = None
        def factory(*args, **kwargs):
            self.factory_args = (args, kwargs)
            return self.port
        self.connection = MegaConnection(serial_factory=factory, clock=self.clock,
                                         on_state=self.states.append,
                                         on_status=self.statuses.append)
        self.connection.connect("COM8")

    def ready(self, **state):
        self.clock.now = 2
        self.connection.poll()
        self.port.reply(**state)
        self.connection.poll()
        self.assertTrue(self.connection.ready)

    def test_reset_delay_and_no_brightness_on_connect(self):
        self.assertEqual(self.factory_args, (("COM8", 9600), {"timeout": 0, "write_timeout": 0.15}))
        self.connection.poll()
        self.assertEqual(self.port.commands, [])
        self.assertFalse(self.connection.set_brightness(1, 100))
        self.clock.now = 2
        self.connection.poll()
        self.assertEqual(self.port.commands, [b"Q\n"])
        self.assertFalse(self.connection.ready)
        self.port.reply(led1=50, led2=190)
        self.connection.poll()
        self.assertEqual(self.port.commands, [b"Q\n"])
        self.assertEqual(self.connection.states[2].brightness, 190)

    def test_independent_channels_and_full_scale(self):
        self.ready()
        self.assertTrue(self.connection.set_brightness(1, 100))
        self.assertTrue(self.connection.set_brightness(2, 50))
        self.assertEqual(self.port.commands[-2:], [b"L1:255\n", b"L2:128\n"])
        self.assertFalse(self.connection.set_brightness(3, 50))

    def test_local_channel_and_all_off(self):
        self.ready(mode1="LOCAL", led1=170, led2=100)
        self.assertFalse(self.connection.set_brightness(1, 100))
        self.assertEqual(self.connection.all_off(), [2])
        self.assertEqual(self.port.commands, [b"Q\n", b"L2:0\n"])

    def test_mode_switch_updates(self):
        self.ready()
        self.clock.now = 2.5
        self.connection.poll()
        self.port.reply(mode2="LOCAL", led2=200)
        self.connection.poll()
        self.assertFalse(self.connection.set_brightness(2, 10))
        self.assertEqual(self.connection.states[2], ChannelState("LOCAL", 200, True))

    def test_fragmented_json_crlf_and_debug_output(self):
        self.clock.now = 2
        self.connection.poll()
        self.port.buffer.extend(b'TTL1: OFF  TTL2: ON\r\n{"mode1":"REMOTE",')
        self.connection.poll()
        self.assertFalse(self.connection.ready)
        self.port.buffer.extend(b'"mode2":"REMOTE","led1":255,"led2":19,"ttl1":false,"ttl2":true}\r\n')
        self.connection.poll()
        self.assertTrue(self.connection.ready)
        self.assertEqual(self.connection.states[1].brightness, 255)

    def test_bad_replies_do_not_enable_controls(self):
        self.clock.now = 2
        self.connection.poll()
        self.port.buffer.extend(b'{"mode1":"REMOTE"}\nnot json\n')
        self.connection.poll()
        self.assertFalse(self.connection.ready)

    def test_boot_noise_cannot_enable_controls(self):
        self.port.reply()
        self.connection.poll()
        self.assertFalse(self.connection.ready)
        self.assertEqual(self.connection.states, {})

    def test_only_one_query_in_flight(self):
        self.clock.now = 2
        self.connection.poll()
        self.clock.now = 3
        self.connection.poll()
        self.assertEqual(self.port.commands, [b"Q\n"])

    def test_handshake_timeout(self):
        self.clock.now = 2
        self.connection.poll()
        self.clock.now = 7
        self.connection.poll()
        self.assertIsNone(self.connection.port)
        self.assertTrue(self.port.closed)
        self.assertIn("No Mega status reply", self.statuses[-1])

    def test_stale_status_disables_controls(self):
        self.ready()
        self.clock.now = 5
        self.connection.poll()
        self.assertFalse(self.connection.ready)
        self.assertEqual(self.connection.states, {})
        self.assertFalse(self.connection.set_brightness(1, 100))

    def test_read_failure(self):
        self.ready()
        self.port.fail_read = True
        self.connection.poll()
        self.assertFalse(self.connection.ready)
        self.assertTrue(self.port.closed)

    def test_write_failure_stops_all_off(self):
        self.ready()
        self.port.fail_write = True
        self.assertEqual(self.connection.all_off(), [])
        self.assertFalse(self.connection.ready)
        self.assertTrue(self.port.closed)

    def test_partial_write_disconnects(self):
        self.ready()
        self.port.short_write = True
        self.assertFalse(self.connection.set_brightness(1, 50))
        self.assertFalse(self.connection.ready)

    def test_reconnect_does_not_replay_brightness(self):
        self.ready()
        self.connection.set_brightness(1, 100)
        self.connection.disconnect()
        fresh_port = FakeSerial()
        self.connection.serial_factory = lambda *args, **kwargs: fresh_port
        self.connection.connect("COM9")
        self.assertFalse(self.connection.ready)
        self.clock.now += 2
        self.connection.poll()
        self.assertEqual(fresh_port.commands, [b"Q\n"])

    def test_port_open_failure(self):
        def failed(*args, **kwargs):
            raise serial.SerialException("Port in use")
        self.connection.serial_factory = failed
        self.assertFalse(self.connection.connect("COM9"))
        self.assertIsNone(self.connection.port)
        self.assertIn("Port in use", self.statuses[-1])

    def test_oversized_unterminated_line(self):
        self.port.buffer.extend(b"x" * 10000)
        for _ in range(3):
            self.connection.poll()
        self.assertEqual(self.connection.buffer, bytearray())


class ProtocolTests(unittest.TestCase):
    def test_percent_mapping(self):
        for percent, pwm in [(-1, 0), (0, 0), (50, 128), (100, 255), (101, 255)]:
            with self.subTest(percent=percent):
                self.assertEqual(percent_to_pwm(percent), pwm)

    def test_reject_invalid_json_values(self):
        valid = dict(mode1="REMOTE", mode2="LOCAL", led1=0, led2=255, ttl1=False, ttl2=True)
        self.assertIsNotNone(parse_state(json.dumps(valid)))
        for key, value in [("led1", 256), ("led2", -1), ("led1", True),
                           ("led2", "15"), ("ttl1", 1), ("mode1", "UNKNOWN")]:
            with self.subTest(key=key, value=value):
                self.assertIsNone(parse_state(json.dumps({**valid, key: value})))
        for bad in ["null", "[]", "19", '"text"', "{broken}"]:
            self.assertIsNone(parse_state(bad))

    def test_demo_end_to_end(self):
        clock = FakeClock()
        connection = MegaConnection(serial_factory=DemoSerial, clock=clock, boot_delay=0)
        connection.connect("DEMO")
        connection.poll()
        connection.poll()
        connection.set_brightness(1, 100)
        connection.set_brightness(2, 25)
        clock.now = 0.5
        connection.poll()
        connection.poll()
        self.assertEqual(connection.states[1].brightness, 255)
        self.assertEqual(connection.states[2].brightness, 64)
        self.assertEqual(connection.all_off(), [1, 2])
        self.assertEqual(connection.port.levels, {1: 0, 2: 0})


if __name__ == "__main__":
    unittest.main()
