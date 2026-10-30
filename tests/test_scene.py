import unittest

from ui.scene import Scene


def center(box):
    return (box[0] + box[2]) // 2, (box[1] + box[3]) // 2


class SceneHitTest(unittest.TestCase):
    def setUp(self):
        self.scene = Scene(1.25, "Arnhem")
        self.scene.temperature, self.scene.wind = "+8°C", "3 m/s"
        self.scene.timer = "●  24:37   focus"
        self.scene.compose(0.0)

    def test_reset_button_sits_left_of_timer_and_is_clickable(self):
        reset, timer = self.scene._reset_box, self.scene._timer_box
        self.assertLess(reset[2], timer[0] + self.scene.px(5))
        self.assertEqual(self.scene.region_at(*center(reset)), "reset")
        self.assertEqual(self.scene.region_at(*center(timer)), "timer")

    def test_close_button_only_reacts_while_hovered(self):
        x, y = center(self.scene._close_box)
        self.assertNotEqual(self.scene.region_at(x, y), "close")
        self.scene.hovered = True
        self.assertEqual(self.scene.region_at(x, y), "close")

    def test_frame_is_clickable_everywhere(self):
        frame = self.scene.compose(1.0)
        self.assertGreaterEqual(frame.getchannel("A").getextrema()[0], 1)

    def test_settings_button_only_reacts_while_hovered(self):
        x, y = center(self.scene.settings_box)
        self.assertNotEqual(self.scene.region_at(x, y), "settings")
        self.scene.hovered = True
        self.assertEqual(self.scene.region_at(x, y), "settings")
        self.assertNotEqual(center(self.scene._close_box), (x, y))
