"""Pillow drawing helpers: anti-aliased text with a soft shadow, clipped compositing, the news strip."""
import os
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont, ImageFilter

FONTS_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
REGULAR = "segoeui.ttf"
SEMIBOLD = "seguisb.ttf"
BOLD = "segoeuib.ttf"
SYMBOL = "seguisym.ttf"  # Segoe UI has no arrows like ↺

Rgb = tuple[int, int, int]


def rgb(hex_color: str) -> Rgb:
    return ImageColor.getrgb(hex_color)[:3]


@lru_cache(maxsize=32)
def load_font(name: str, size_px: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONTS_DIR / name), size_px)
    except OSError:
        return ImageFont.load_default(size_px)


def with_shadow(image: Image.Image, radius: float) -> tuple[Image.Image, int]:
    """Puts a soft dark halo under the opaque parts of `image` so it reads on any wallpaper.

    Returns the new image and the padding added on each side; draw it at (x - pad, y - pad).
    """
    pad = int(radius * 3) + 1
    alpha = Image.new("L", (image.width + 2 * pad, image.height + 2 * pad), 0)
    alpha.paste(image.getchannel("A"), (pad, pad + max(1, int(radius / 2))))  # light comes from above
    tight = alpha.filter(ImageFilter.GaussianBlur(radius / 2))
    soft = alpha.filter(ImageFilter.GaussianBlur(radius))
    shadow = ImageChops.lighter(tight, soft).point(lambda a: min(210, int(a * 1.6)))
    result = Image.new("RGBA", alpha.size, (0, 0, 0, 0))
    result.putalpha(shadow)
    result.alpha_composite(image, (pad, pad))
    return result, pad


def draw_text(text: str, font_name: str, size_px: int, color: Rgb) -> Image.Image:
    font = load_font(font_name, size_px)
    _, _, right, bottom = font.getbbox(text)
    image = Image.new("RGBA", (max(1, right + 1), max(1, bottom + 1)), color + (0,))
    ImageDraw.Draw(image).text((0, 0), text, font=font, fill=color + (255,))
    return image


@lru_cache(maxsize=256)  # the timer text changes every second; everything else is stable
def shadowed_text(text: str, font_name: str, size_px: int, color: Rgb, shadow_radius: float) -> tuple[Image.Image, int]:
    return with_shadow(draw_text(text, font_name, size_px, color), shadow_radius)


def composite(dest: Image.Image, src: Image.Image, x: int, y: int) -> None:
    """alpha_composite that clips instead of failing when `src` sticks out of `dest`."""
    sx, sy = max(0, -x), max(0, -y)
    x, y = max(0, x), max(0, y)
    width, height = min(src.width - sx, dest.width - x), min(src.height - sy, dest.height - y)
    if width > 0 and height > 0:
        dest.alpha_composite(src, (x, y), (sx, sy, sx + width, sy + height))


def news_strip(titles: list[str], font_name: str, size_px: int, color: Rgb, gap_px: int) -> tuple[Image.Image, list[tuple[int, int]]]:
    """Renders all headlines into one long image. Returns it with each headline's (x0, x1) span."""
    pieces = [draw_text(f"•  {title}", font_name, size_px, color) for title in titles]
    height = max((p.height for p in pieces), default=1)
    strip = Image.new("RGBA", (max(1, sum(p.width + gap_px for p in pieces)), height), (0, 0, 0, 0))
    spans, x = [], 0
    for piece in pieces:
        strip.paste(piece, (x, height - piece.height))
        spans.append((x, x + piece.width))
        x += piece.width + gap_px
    return strip, spans


def rounded_panel(width: int, height: int, radius: int, color: Rgb, opacity: int) -> Image.Image:
    # Drawn at 4x and scaled down: Pillow's rounded_rectangle has no anti-aliasing of its own.
    big = Image.new("RGBA", (width * 4, height * 4), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle((0, 0, width * 4 - 1, height * 4 - 1), radius * 4, fill=color + (opacity,))
    return big.resize((width, height), Image.LANCZOS)


def horizontal_fade(width: int, height: int, fade_px: int) -> Image.Image:
    """Alpha mask that fades the strip out at both ends instead of cutting letters in half."""
    row = [min(255, int(255 * min(x, width - 1 - x) / fade_px)) if fade_px else 255 for x in range(width)]
    mask = Image.new("L", (width, 1))
    mask.putdata(row)
    return mask.resize((width, height))
