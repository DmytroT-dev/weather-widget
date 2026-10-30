import unittest

from ui.formatting import format_temperature, format_wind
from ui.state import visible_position


class FormattingTest(unittest.TestCase):
    def test_temperature(self):
        cases = {8.4: "+8°C", -12.6: "-13°C", -0.3: "0°C", 0.4: "0°C", 0.0: "0°C", 0.5: "0°C", 1.5: "+2°C"}
        for celsius, expected in cases.items():
            with self.subTest(celsius=celsius):
                self.assertEqual(format_temperature(celsius), expected)

    def test_wind(self):
        self.assertEqual(format_wind(3.4), "3 m/s")
        self.assertEqual(format_wind(0.2), "0 m/s")


class VisiblePositionTest(unittest.TestCase):
    SCREEN = (0, 0, 1920, 1080)
    SIZE = (475, 254)

    def test_visible_position_is_kept(self):
        self.assertEqual(visible_position((100, 200), self.SIZE, self.SCREEN), (100, 200))

    def test_off_screen_position_is_pulled_back(self):
        self.assertEqual(visible_position((5000, 3000), self.SIZE, self.SCREEN), (1920 - 475, 1080 - 254))
        self.assertEqual(visible_position((-900, -50), self.SIZE, self.SCREEN), (0, 0))

    def test_monitor_left_of_primary_has_negative_coordinates(self):
        two_monitors = (-1920, 0, 3840, 1080)
        self.assertEqual(visible_position((-1500, 100), self.SIZE, two_monitors), (-1500, 100))
        self.assertEqual(visible_position((-2500, 100), self.SIZE, two_monitors), (-1920, 100))
