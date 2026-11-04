"""Generates the short pomodoro chimes in assets/sounds/ (standard library only).

Run from the project root: .venv\\Scripts\\python scripts\\make_sounds.py
"""
import math
import struct
import wave
from pathlib import Path

RATE = 44100
VOLUME = 0.45  # of full scale, leaves headroom so overlapping notes never clip
OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

C6, E6, G6, C7 = 1046.50, 1318.51, 1567.98, 2093.00


def bell(freq: float, length_s: float, decay: float) -> list[float]:
    """One soft bell-like note: sine plus a quiet octave, fast attack, exponential fade."""
    samples = []
    for i in range(int(RATE * length_s)):
        t = i / RATE
        attack = min(1.0, t / 0.004)  # 4 ms ramp avoids an audible click at the start
        envelope = attack * math.exp(-t * decay)
        tone = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(2 * math.pi * 2 * freq * t)
        samples.append(envelope * tone / 1.25)
    return samples


def chime(notes: list[float], step_s: float, tail_s: float) -> list[float]:
    """Notes start step_s apart and ring on top of each other, like a music box."""
    total = int(RATE * (step_s * (len(notes) - 1) + tail_s))
    mix = [0.0] * total
    for n, freq in enumerate(notes):
        offset = int(RATE * step_s * n)
        for i, value in enumerate(bell(freq, tail_s, decay=9.0)):
            if offset + i < total:
                mix[offset + i] += value
    peak = max(abs(v) for v in mix)
    return [v / peak * VOLUME for v in mix]


def save(name: str, samples: list[float]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT_DIR / name), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit PCM
        wav.setframerate(RATE)
        wav.writeframes(b"".join(struct.pack("<h", int(v * 32767)) for v in samples))


if __name__ == "__main__":
    save("break-start.wav", chime([G6, C6], step_s=0.14, tail_s=0.45))  # down: focus is over, rest
    save("focus-start.wav", chime([C6, E6, G6, C7], step_s=0.07, tail_s=0.35))  # up: back to work
    print(f"written to {OUT_DIR}")
