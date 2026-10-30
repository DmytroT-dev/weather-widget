import tempfile
import unittest
from pathlib import Path

from ui.state import load_position, save_position


class StateTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "sub" / "state.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_round_trip(self):
        save_position(self.path, 100, -20)
        self.assertEqual(load_position(self.path), (100, -20))

    def test_missing_or_garbage_file_returns_none(self):
        self.assertIsNone(load_position(self.path))
        for content in ("not json", "[]", '{"x": 1}', '{"x": "1; destroy", "y": 2}', '{"x": true, "y": 2}'):
            with self.subTest(content=content):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(content, encoding="utf-8")
                self.assertIsNone(load_position(self.path))
