"""What the widget looks like: layout, per-frame compositing and hit testing. No Tk and no Win32 here.

All layout constants are in logical pixels (100% scale) and multiplied by the DPI scale factor.
"""
from pathlib import Path

from PIL import Image, ImageChops

from ui.animation import LottiePlayer
from ui.render import (BOLD, REGULAR, SEMIBOLD, SYMBOL, composite, horizontal_fade, news_strip, rgb, rounded_panel,
                       shadowed_text)

WIDTH = 380
FG = rgb("#FFFFFF")
MUTED = rgb("#E3E8EF")
ERROR = rgb("#FF8A80")
FOCUS = rgb("#FF7A6B")
BREAK = rgb("#7CD992")
ACCENT = rgb("#FFB45C")
TICKER_BG = rgb("#000000")

# Everything above the ticker is designed at base size and enlarged by this factor, so the weather
# block roughly spans the ticker's width. One knob instead of a dozen hand-tuned numbers.
UPPER_SCALE = 1.2


def _upper(*values: float) -> tuple[int, ...]:
    return tuple(round(v * UPPER_SCALE) for v in values)


# Weather block: x is relative to the block's left edge; the block is right-aligned at draw time
# because its width depends on the text ("+8°C" vs "-12°C").
ICON = _upper(0, 0, 104)
TEMPERATURE = _upper(112, 4, 38)
WIND_ICON = _upper(106, 54, 36)
WIND_TEXT = _upper(144, 61, 16)
STATUS = _upper(113, 90, 15)
TEXT_COLUMN_X = _upper(112)[0]
RIGHT_MARGIN = 12
TIMER = _upper(0, 116, 18)  # right-aligned at draw time, so x is unused
TICKER = (8, _upper(145)[0], WIDTH - 16, 23)  # x, y, width, height of the black panel
HEIGHT = TICKER[1] + TICKER[3] + 6
TICKER_FONT_SIZE = 12
TICKER_PADDING = 9
# Hover-only window buttons, top left because the weather block is on the right: x, y, size.
CLOSE = (4, 2, 22)
SETTINGS = (30, 2, 22)
RESET_SIZE = _upper(18)[0]
RESET_GAP = 14
SCROLL_PX_PER_S = 45
SHADOW_RADIUS = 2.5

# Alpha 1 of 255 is invisible, but a layered window only receives clicks on pixels with alpha > 0.
# Filling the whole rectangle with it makes the widget easy to grab instead of only on the letters.
CLICKABLE_BACKDROP = (0, 0, 0, 1)
HOVER_ONLY = ("close", "settings")


class Scene:
    def __init__(self, scale: float, city: str) -> None:
        self._s = scale
        self.size = (self.px(WIDTH), self.px(HEIGHT))
        self._shadow = SHADOW_RADIUS * scale
        self._weather_icon = LottiePlayer(self.px(ICON[2]), self._shadow)
        self._wind_icon = LottiePlayer(self.px(WIND_ICON[2]), self._shadow)
        self.temperature = "…"
        self.wind = ""
        self.status = city
        self.status_color = MUTED
        self.timer = ""
        self.timer_color = MUTED
        self.hovered = False
        self.hover_x: int | None = None  # pointer x while it is over the ticker
        self.hover_region: str | None = None
        self._timer_box = (0, 0, 0, 0)
        self._reset_box = (0, 0, 0, 0)

        tx, ty, tw, th = (self.px(v) for v in TICKER)
        self._ticker_box = (tx, ty, tx + tw, ty + th)
        self._ticker_panel = rounded_panel(tw, th, self.px(6), TICKER_BG, 215)
        self._ticker_view_width = tw - 2 * self.px(TICKER_PADDING)
        self._ticker_fade = horizontal_fade(self._ticker_view_width, th, self.px(14))
        self._strip: Image.Image | None = None
        self._accent_strip: Image.Image | None = None
        self._spans: list[tuple[int, int]] = []
        self._urls: list[str] = []
        self._offset = 0.0
        self._last_time: float | None = None

        self._close_box = self._button_box(CLOSE)
        self._settings_box = self._button_box(SETTINGS)
        size = self.px(CLOSE[2])
        self._button_panel = rounded_panel(size, size, size // 2, TICKER_BG, 190)

    def px(self, value: float) -> int:
        return round(value * self._s)

    def _button_box(self, spec: tuple[int, int, int]) -> tuple[int, int, int, int]:
        x, y, size = (self.px(v) for v in spec)
        return x, y, x + size, y + size

    @property
    def settings_box(self) -> tuple[int, int, int, int]:
        return self._settings_box

    # --- state ----------------------------------------------------------------------------------

    def set_weather_icons(self, weather_icon: Path, wind_icon: Path) -> None:
        self._weather_icon.load(weather_icon)
        self._wind_icon.load(wind_icon)

    def set_stories(self, titles: list[str], urls: list[str]) -> None:
        size = self.px(TICKER_FONT_SIZE)
        gap = self.px(40)
        self._strip, self._spans = news_strip(titles, REGULAR, size, FG, gap)
        self._accent_strip, _ = news_strip(titles, REGULAR, size, ACCENT, gap)
        self._urls = urls
        self._offset = -float(self._ticker_view_width)  # start just off the right edge

    # --- hit testing ----------------------------------------------------------------------------

    def region_at(self, x: int, y: int) -> str | None:
        regions = (("close", self._close_box), ("settings", self._settings_box), ("reset", self._reset_box),
                   ("timer", self._timer_box), ("ticker", self._ticker_box))
        for name, box in regions:
            if box[0] <= x < box[2] and box[1] <= y < box[3]:
                if name in HOVER_ONLY and not self.hovered:
                    return None  # invisible buttons must not catch clicks
                return name
        return None

    def url_at(self, x: int) -> str | None:
        index = self._story_index_at(x)
        return self._urls[index] if index is not None else None

    def _story_index_at(self, x: int) -> int | None:
        if not self._strip or not self._spans:
            return None
        strip_x = (x - self._ticker_box[0] - self.px(TICKER_PADDING) + self._offset) % self._strip.width
        for index, (x0, x1) in enumerate(self._spans):
            if x0 <= strip_x < x1:
                return index
        return None

    # --- drawing --------------------------------------------------------------------------------

    def compose(self, now: float) -> Image.Image:
        frame = Image.new("RGBA", self.size, CLICKABLE_BACKDROP)
        block_x = self._weather_block_x()
        self._draw_icon(frame, self._weather_icon, ICON, now, block_x)
        self._draw_icon(frame, self._wind_icon, WIND_ICON, now, block_x)
        self._draw_text(frame, self.temperature, BOLD, TEMPERATURE, FG, block_x)
        self._draw_text(frame, self.wind, SEMIBOLD, WIND_TEXT, FG, block_x)
        self._draw_text(frame, self.status, SEMIBOLD, STATUS, self.status_color, block_x)
        timer_x = self.size[0] - self.px(RIGHT_MARGIN) - self._text_width(self.timer, SEMIBOLD, TIMER)
        self._timer_box = self._draw_text(frame, self.timer, SEMIBOLD, TIMER, self.timer_color, timer_x)
        self._draw_reset(frame)
        self._draw_ticker(frame, now)
        if self.hovered:
            self._draw_button(frame, self._close_box, "×", SEMIBOLD, 18, "close")
            self._draw_button(frame, self._settings_box, "⚙", SYMBOL, 17, "settings")
        return frame

    def _weather_block_x(self) -> int:
        """Left edge of the weather block such that its widest text line ends at the right margin."""
        text_column = max(
            self._text_width(self.temperature, BOLD, TEMPERATURE),
            self.px(WIND_TEXT[0] - TEXT_COLUMN_X) + self._text_width(self.wind, SEMIBOLD, WIND_TEXT),
            self.px(STATUS[0] - TEXT_COLUMN_X) + self._text_width(self.status, SEMIBOLD, STATUS),
        )
        return self.size[0] - self.px(RIGHT_MARGIN) - text_column - self.px(TEXT_COLUMN_X)

    def _text_width(self, text: str, font: str, spec: tuple) -> int:
        if not text:
            return 0
        image, pad = shadowed_text(text, font, self.px(spec[2]), FG, self._shadow)
        return image.width - 2 * pad

    def _draw_icon(self, frame: Image.Image, player: LottiePlayer, spec: tuple, now: float, offset_x: int) -> None:
        rendered = player.frame_at(now)
        if rendered:
            image, pad = rendered
            composite(frame, image, offset_x + self.px(spec[0]) - pad, self.px(spec[1]) - pad)

    def _draw_text(self, frame: Image.Image, text: str, font: str, spec: tuple, color,
                   offset_x: int) -> tuple[int, int, int, int]:
        if not text:
            return 0, 0, 0, 0
        image, pad = shadowed_text(text, font, self.px(spec[2]), color, self._shadow)
        x, y = offset_x + self.px(spec[0]), self.px(spec[1])
        composite(frame, image, x - pad, y - pad)
        return x, y, x + image.width - 2 * pad, y + image.height - 2 * pad

    def _draw_ticker(self, frame: Image.Image, now: float) -> None:
        x0, y0, x1, y1 = self._ticker_box
        composite(frame, self._ticker_panel, x0, y0)
        if not self._strip:
            return
        elapsed = 0.0 if self._last_time is None else now - self._last_time
        self._last_time = now
        if self.hover_x is None:  # hovering pauses the line so a headline can be read and clicked
            self._offset = (self._offset + elapsed * SCROLL_PX_PER_S * self._s) % self._strip.width

        view = Image.new("RGBA", (self._ticker_view_width, y1 - y0), (0, 0, 0, 0))
        top = (view.height - self._strip.height) // 2
        hovered = self._story_index_at(self.hover_x) if self.hover_x is not None else None
        # The strip loops: draw it twice so its end is followed by its beginning.
        for copy in (0, 1):
            left = int(-self._offset) + copy * self._strip.width
            view.paste(self._strip, (left, top))
            if hovered is not None:
                sx0, sx1 = self._spans[hovered]
                view.paste(self._accent_strip.crop((sx0, 0, sx1, self._strip.height)), (left + sx0, top))
        view.putalpha(ImageChops.multiply(view.getchannel("A"), self._ticker_fade))
        composite(frame, view, x0 + self.px(TICKER_PADDING), y0)

    def _draw_reset(self, frame: Image.Image) -> None:
        """A visible reset button left of the timer; the click target is padded to be easy to hit."""
        if not self.timer:
            self._reset_box = (0, 0, 0, 0)
            return
        color = ACCENT if self.hover_region == "reset" else MUTED
        icon, pad = shadowed_text("↺", SYMBOL, self.px(RESET_SIZE), color, self._shadow)
        timer_x0, timer_y0, _, timer_y1 = self._timer_box
        width, height = icon.width - 2 * pad, icon.height - 2 * pad
        x = timer_x0 - self.px(RESET_GAP) - width
        y = (timer_y0 + timer_y1 - height) // 2
        composite(frame, icon, x - pad, y - pad)
        grow = self.px(4)
        self._reset_box = (x - grow, timer_y0 - grow, x + width + grow, timer_y1 + grow)

    def _draw_button(self, frame: Image.Image, box: tuple[int, int, int, int], glyph: str, font: str,
                     size: int, region: str) -> None:
        x0, y0, x1, y1 = box
        composite(frame, self._button_panel, x0, y0)
        color = ACCENT if self.hover_region == region else FG
        image, pad = shadowed_text(glyph, font, self.px(size), color, 0.1)
        # Centre the glyph's ink, not its text box: fonts put symbols at different heights.
        left, top, right, bottom = image.getchannel("A").getbbox() or (0, 0, image.width, image.height)
        composite(frame, image, x0 + (x1 - x0 - (right - left)) // 2 - left, y0 + (y1 - y0 - (bottom - top)) // 2 - top)

