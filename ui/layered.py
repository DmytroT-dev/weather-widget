"""Per-pixel transparent window on Windows via UpdateLayeredWindow.

Tk can only make one colour fully transparent, which leaves jagged text edges. A layered window instead
takes a ready ARGB bitmap: every pixel has its own alpha, so anti-aliasing and soft shadows survive.
Mouse input only reaches pixels with alpha > 0; fully transparent pixels click through to the desktop.
"""
import ctypes
import tkinter as tk
from ctypes import wintypes

from PIL import Image, ImageChops

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080  # keeps the widget out of the taskbar and Alt+Tab
WS_EX_NOACTIVATE = 0x08000000  # clicks still arrive, but never bring the widget in front of other windows
HWND_BOTTOM = 1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
ULW_ALPHA = 0x02
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
DIB_RGB_COLORS = 0


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


# Explicit signatures: without them ctypes assumes 32-bit int results and truncates 64-bit handles.
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, wintypes.UINT]
user32.UpdateLayeredWindow.restype = wintypes.BOOL
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE),
    wintypes.HDC, ctypes.POINTER(wintypes.POINT), wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]


def virtual_screen() -> tuple[int, int, int, int]:
    """Bounding box of all monitors: (left, top, width, height) in physical pixels."""
    sm_xvirtualscreen, sm_yvirtualscreen, sm_cxvirtualscreen, sm_cyvirtualscreen = 76, 77, 78, 79
    return tuple(user32.GetSystemMetrics(i) for i in
                 (sm_xvirtualscreen, sm_yvirtualscreen, sm_cxvirtualscreen, sm_cyvirtualscreen))


def enable_dpi_awareness() -> float:
    """Must run before the first Tk window. Returns the UI scale factor (1.25 at 125%).

    Without it Windows renders the window at 96 DPI and stretches the bitmap, which blurs all text.
    """
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)  # per-monitor aware
    except (OSError, AttributeError):
        user32.SetProcessDPIAware()
    try:
        return user32.GetDpiForSystem() / 96
    except AttributeError:
        return 1.0


class LayeredWindow:
    def __init__(self, window: tk.Tk) -> None:
        window.update_idletasks()
        # Tk wraps every toplevel in a frame window; the frame is the real top-level HWND.
        self._hwnd = int(window.wm_frame(), 16)
        style = user32.GetWindowLongPtrW(self._hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(self._hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        self._blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)

    def send_to_bottom(self) -> None:
        """Puts the widget under every other window, like a desktop gadget."""
        user32.SetWindowPos(self._hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)

    def show(self, image: Image.Image) -> None:
        """Replaces the window content (and size) with an RGBA image. Position stays unchanged."""
        width, height = image.size
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        screen_dc = user32.GetDC(None)
        if not screen_dc:
            return
        memory_dc = gdi32.CreateCompatibleDC(screen_dc)
        bits = ctypes.c_void_p()
        bitmap = None
        try:
            if not memory_dc:
                return
            bitmap = gdi32.CreateDIBSection(memory_dc, ctypes.byref(header), DIB_RGB_COLORS, ctypes.byref(bits),
                                            None, 0)
            if not bitmap or not bits:  # out of GDI resources: skip this frame rather than write to NULL
                return
            data = _premultiplied_bgra(image)
            ctypes.memmove(bits, data, len(data))
            old = gdi32.SelectObject(memory_dc, bitmap)
            user32.UpdateLayeredWindow(self._hwnd, screen_dc, None, ctypes.byref(wintypes.SIZE(width, height)),
                                       memory_dc, ctypes.byref(wintypes.POINT(0, 0)), 0,
                                       ctypes.byref(self._blend), ULW_ALPHA)
            gdi32.SelectObject(memory_dc, old)
        finally:
            if bitmap:
                gdi32.DeleteObject(bitmap)
            if memory_dc:
                gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(None, screen_dc)


def _premultiplied_bgra(image: Image.Image) -> bytes:
    # Windows expects colour channels already multiplied by alpha, in BGRA byte order.
    r, g, b, a = image.split()
    r, g, b = (ImageChops.multiply(channel, a) for channel in (r, g, b))
    return Image.merge("RGBA", (b, g, r, a)).tobytes()
