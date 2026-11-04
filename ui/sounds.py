"""Pomodoro chimes: which sound plays when a phase starts. Files are made by scripts/make_sounds.py."""
from pathlib import Path

from focus.pomodoro import Phase

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

# Keyed by the phase that is about to START: a break starting means focus just ended, and vice versa.
PHASE_START_SOUNDS = {
    Phase.FOCUS: SOUNDS_DIR / "focus-start.wav",  # rising: back to work
    Phase.SHORT_BREAK: SOUNDS_DIR / "break-start.wav",  # falling: time to rest
    Phase.LONG_BREAK: SOUNDS_DIR / "break-start.wav",
}
