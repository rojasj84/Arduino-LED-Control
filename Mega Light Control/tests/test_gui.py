"""Real Tk widget checks; no physical serial port is opened."""

import time
import tkinter as tk
import unittest

from mega_light_control import MegaLightApp, THEMES


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.app = MegaLightApp(self.root, demo=True)
        self.app.connection.connect("DEMO")
        self.app.connection.poll()
        self.app.connection.poll()
        self.port = self.app.connection.port

    def tearDown(self):
        if not self.app.closing:
            self.app.close()
        self.assertEqual(self.errors, [])

    def pump(self, duration=0.12):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.005)

    def query(self):
        self.app.connection.next_query = 0
        self.app.connection.poll()
        self.app.connection.poll()

    def test_separate_windows_and_channel_routing(self):
        self.assertNotEqual(self.app.lights[1].window, self.app.lights[2].window)
        left, right = self.app.lights.values()
        left.level.set(100)
        left.change("100")
        right.level.set(50)
        right.change("50")
        self.pump()
        self.assertEqual(self.port.levels, {1: 255, 2: 128})
        self.query()
        self.assertEqual(left.level_text.get(), "100%")
        self.assertEqual(right.level_text.get(), "50%")

    def test_all_off_cancels_queued_slider_commands(self):
        left, right = self.app.lights.values()
        left.level.set(100)
        left.change("100")
        right.level.set(80)
        right.change("80")
        self.app.all_off()
        self.pump()
        self.assertEqual(self.port.levels, {1: 0, 2: 0})
        self.assertIsNone(left.pending)
        self.assertIsNone(right.pending)

    def test_local_mode_disables_its_window_only(self):
        self.port.modes[1] = "LOCAL"
        self.port.levels[1] = 90
        self.query()
        self.assertIn("disabled", self.app.lights[1].slider.state())
        self.assertNotIn("disabled", self.app.lights[2].slider.state())
        self.assertEqual(self.app.lights[1].mode.get(), "LOCAL")
        self.assertEqual(self.app.lights[2].mode.get(), "REMOTE")
        self.app.all_off()
        self.assertEqual(self.port.levels[1], 90)
        self.assertEqual(self.port.levels[2], 0)

    def test_hide_and_reopen_preserves_connection(self):
        self.app.lights[1].window.withdraw()
        self.assertEqual(self.app.lights[1].window.state(), "withdrawn")
        self.app.lights[1].show()
        self.pump()
        self.assertEqual(self.app.lights[1].window.state(), "normal")
        self.assertIs(self.app.connection.port, self.port)
        self.assertTrue(self.app.connection.ready)

    def test_disconnect_cancels_commands_and_zeros_remote_lights(self):
        self.port.levels = {1: 140, 2: 250}
        left = self.app.lights[1]
        left.level.set(90)
        left.change("90")
        self.app.disconnect()
        self.pump()
        self.assertEqual(self.port.levels, {1: 0, 2: 0})
        self.assertIsNone(left.pending)
        self.assertIn("disabled", left.slider.state())

    def test_close_zeros_remote_channels_and_closes_port(self):
        self.port.levels = {1: 255, 2: 255}
        self.app.close()
        self.assertEqual(self.port.levels, {1: 0, 2: 0})
        self.assertFalse(self.port.is_open)

    def test_default_windows_fit_their_contents(self):
        self.root.update_idletasks()
        for window in [light.window for light in self.app.lights.values()]:
            with self.subTest(title=window.title()):
                self.assertGreaterEqual(window.winfo_height(), window.winfo_reqheight())
                self.assertGreaterEqual(window.winfo_width(), window.winfo_reqwidth())
                self.assertLessEqual(window.winfo_width(), 210)
                self.assertLessEqual(window.winfo_height(), 350)

    def test_startup_shows_exactly_two_light_windows(self):
        self.pump()
        self.assertEqual(self.root.state(), "withdrawn")
        visible = [w for w in self.root.winfo_children()
                   if isinstance(w, tk.Toplevel) and w.state() != "withdrawn"]
        self.assertEqual(set(visible), {light.window for light in self.app.lights.values()})
        self.assertEqual(self.app.serial_window.state(), "withdrawn")
        self.assertTrue(all(not hasattr(light, "ttl") for light in self.app.lights.values()))

    def test_windows_have_independent_blue_and_red_styles(self):
        for channel, light in self.app.lights.items():
            self.assertEqual(light.window.cget("bg"), THEMES[channel]["bg"])
            style = tk.ttk.Style(self.root)
            self.assertEqual(style.lookup(light.slider.cget("style"), "troughcolor"),
                             THEMES[channel]["active"])
        self.assertNotEqual(self.app.lights[1].slider.cget("style"),
                            self.app.lights[2].slider.cget("style"))

    def test_closing_last_light_exits_application(self):
        self.app.hide_light(1)
        self.assertFalse(self.app.closing)
        self.assertEqual(self.app.lights[1].window.state(), "withdrawn")
        self.assertTrue(self.app.connection.ready)
        self.app.hide_light(2)
        self.assertTrue(self.app.closing)
        self.assertFalse(self.port.is_open)

    def test_settings_are_accessible_from_each_light(self):
        self.app.demo = False
        for channel in (1, 2):
            with self.subTest(channel=channel):
                self.app.open_settings(channel)
                self.assertEqual(str(self.app.settings_window.transient()),
                                 str(self.app.lights[channel].window))
                self.app.settings_window.destroy()

    def test_first_slider_movement_sends_immediately(self):
        left = self.app.lights[1]
        left.level.set(65)
        left.change("65")
        # Assert before processing timers or releasing the mouse.
        self.assertEqual(self.port.levels[1], 166)

    def test_brightness_updates_during_continuous_drag(self):
        left = self.app.lights[1]
        sent = []
        original_write = self.port.write
        def record(packet):
            if packet.startswith(b"L1:"):
                sent.append(packet)
            return original_write(packet)
        self.port.write = record
        left.start_drag()
        for value in range(10, 100, 5):
            left.level.set(value)
            left.change(str(value))
            self.pump(0.006)
        self.assertTrue(left.dragging)
        self.assertGreaterEqual(len(sent), 3)
        self.assertGreater(self.port.levels[1], 150)
        left.finish_drag()
        self.assertEqual(self.port.levels[1], 242)
        self.assertIsNone(left.pending)

    def test_old_status_reply_does_not_pull_slider_back(self):
        left = self.app.lights[1]
        old_state = self.app.connection.states[1]
        left.level.set(85)
        left.change("85")
        left.update(old_state)
        self.assertEqual(left.level.get(), 85)
        self.assertEqual(left.level_text.get(), "85%")

    def test_dragged_value_survives_status_reply_between_updates(self):
        left = self.app.lights[1]
        left.start_drag()
        left.level.set(70)
        left.change("70")
        self.query()
        left.level.set(75)
        left.update(self.app.connection.states[1])
        self.assertEqual(left.level.get(), 75)
        left.finish_drag()
        self.assertEqual(self.port.levels[1], 191)

    def test_local_switch_cancels_pending_drag_update(self):
        left = self.app.lights[1]
        left.start_drag()
        left.level.set(10)
        left.change("10")
        left.level.set(100)
        left.change("100")
        self.assertIsNotNone(left.pending)
        self.port.modes[1] = "LOCAL"
        self.port.levels[1] = 50
        self.app.connection.last_brightness_write = None
        self.query()
        self.pump(0.04)
        self.assertIsNone(left.pending)
        self.assertFalse(left.dragging)
        self.assertEqual(left.mode.get(), "LOCAL")
        self.assertEqual(self.port.levels[1], 50)

    def test_repeated_identical_value_does_not_flood_serial(self):
        left = self.app.lights[1]
        sent = []
        original_write = self.port.write
        def record(packet):
            if packet.startswith(b"L1:"):
                sent.append(packet)
            return original_write(packet)
        self.port.write = record
        for _ in range(10):
            left.level.set(50)
            left.change("50")
            self.pump(0.006)
        self.pump(0.04)
        self.assertEqual(sent, [b"L1:128\n"])

    def test_device_change_after_settling_resets_duplicate_filter(self):
        left = self.app.lights[1]
        left.level.set(50)
        left.change("50")
        self.port.levels[1] = 20
        left.last_sent_at -= 2
        self.app.connection.last_brightness_write = None
        self.query()
        self.assertEqual(left.last_sent_pwm, 20)
        left.level.set(50)
        left.change("50")
        self.assertEqual(self.port.levels[1], 128)


if __name__ == "__main__":
    unittest.main()
