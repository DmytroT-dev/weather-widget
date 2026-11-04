import unittest
import wave

from focus.pomodoro import Phase
from ui.sounds import PHASE_START_SOUNDS


class PhaseSoundsTest(unittest.TestCase):
    def test_every_phase_has_a_sound(self):
        self.assertEqual(set(PHASE_START_SOUNDS), set(Phase))

    def test_sound_files_exist_and_are_short(self):
        for phase, path in PHASE_START_SOUNDS.items():
            with self.subTest(phase=phase):
                self.assertTrue(path.exists(), path)
                with wave.open(str(path)) as wav:
                    self.assertLess(wav.getnframes() / wav.getframerate(), 1.0)

    def test_focus_and_break_sound_different(self):
        self.assertNotEqual(PHASE_START_SOUNDS[Phase.FOCUS], PHASE_START_SOUNDS[Phase.SHORT_BREAK])


if __name__ == "__main__":
    unittest.main()
