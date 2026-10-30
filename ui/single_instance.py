"""Allows only one running widget per user session, using a named Win32 mutex."""
import ctypes
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]

_handle = None  # kept for the whole process lifetime: Windows releases the mutex when the process exits


def acquire(name: str) -> bool:
    """Returns False if another instance already holds the mutex."""
    global _handle
    # "Local\" scopes the name to the current logon session, so other users are not affected.
    _handle = kernel32.CreateMutexW(None, False, f"Local\\{name}")
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS
