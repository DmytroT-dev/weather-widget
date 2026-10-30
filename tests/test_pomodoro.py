import unittest

from focus.pomodoro import Phase, Pomodoro


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class PomodoroTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.timer = Pomodoro(focus_s=100, short_break_s=10, long_break_s=30, focus_sessions_per_long_break=2, clock=self.clock)

    def finish_phase(self):
        if not self.timer.running:
            self.timer.toggle()
        self.clock.now += self.timer.remaining_s()
        return self.timer.update()

    def test_starts_paused_in_focus(self):
        self.assertIs(self.timer.phase, Phase.FOCUS)
        self.assertFalse(self.timer.running)
        self.clock.now += 50
        self.assertEqual(self.timer.remaining_s(), 100)

    def test_counts_down_while_running(self):
        self.timer.toggle()
        self.clock.now += 40
        self.assertEqual(self.timer.remaining_s(), 60)
        self.assertIsNone(self.timer.update())

    def test_pause_freezes_remaining_time(self):
        self.timer.toggle()
        self.clock.now += 30
        self.timer.toggle()
        self.clock.now += 500
        self.assertEqual(self.timer.remaining_s(), 70)
        self.timer.toggle()
        self.clock.now += 20
        self.assertEqual(self.timer.remaining_s(), 50)

    def test_cycle_with_long_break_and_paused_transitions(self):
        self.assertIs(self.finish_phase(), Phase.SHORT_BREAK)
        self.assertFalse(self.timer.running)
        self.assertEqual(self.timer.remaining_s(), 10)
        self.assertIs(self.finish_phase(), Phase.FOCUS)
        self.assertIs(self.finish_phase(), Phase.LONG_BREAK)
        self.assertEqual(self.timer.completed_focus_sessions, 2)
        self.assertEqual(self.timer.remaining_s(), 30)
        self.assertIs(self.finish_phase(), Phase.FOCUS)

    def test_update_reports_phase_change_only_once(self):
        self.finish_phase()
        self.clock.now += 1000
        self.assertIsNone(self.timer.update())

    def test_reset(self):
        self.finish_phase()
        self.timer.toggle()
        self.timer.reset()
        self.assertIs(self.timer.phase, Phase.FOCUS)
        self.assertFalse(self.timer.running)
        self.assertEqual(self.timer.remaining_s(), 100)
        self.assertEqual(self.timer.completed_focus_sessions, 0)
