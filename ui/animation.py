"""Lottie playback with rlottie: returns the frame for a point in time as a Pillow image."""
from pathlib import Path

from PIL import Image
from rlottie_python import LottieAnimation

from ui.render import with_shadow

TARGET_FPS = 30


class LottiePlayer:
    def __init__(self, size_px: int, shadow_radius: float) -> None:
        self._size = size_px
        self._shadow_radius = shadow_radius
        self._animation: LottieAnimation | None = None
        self._path: Path | None = None
        self._frames: dict[int, tuple[Image.Image, int]] = {}
        self._total = 1
        self._fps = TARGET_FPS
        self._step = 1

    def load(self, path: Path) -> None:
        if path == self._path:
            return
        self._path = path
        self._animation = LottieAnimation.from_file(str(path))
        self._total = max(1, self._animation.lottie_animation_get_totalframe())
        self._fps = self._animation.lottie_animation_get_framerate() or TARGET_FPS
        # Skip source frames: 60 fps icons played at 30 fps keep their duration and halve the CPU cost.
        self._step = max(1, round(self._fps / TARGET_FPS))
        self._frames = {}

    def frame_at(self, seconds: float) -> tuple[Image.Image, int] | None:
        """Returns (image with shadow, shadow padding) or None before anything is loaded."""
        if self._animation is None:
            return None
        number = int(seconds * self._fps) % self._total
        number -= number % self._step
        if number not in self._frames:  # lazy: each frame is rendered once, then reused for every loop
            frame = self._animation.render_pillow_frame(frame_num=number, width=self._size, height=self._size)
            self._frames[number] = with_shadow(frame.convert("RGBA"), self._shadow_radius)
        return self._frames[number]
