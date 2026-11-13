"""
client/win32_utils.py - Windows native integration for click-through overlays and global hotkeys.
Uses ctypes for zero-dependency Win32 user32/kernel32 calls.
"""

import os
import sys
import time
import threading
from typing import Callable, Optional

if os.name == "nt":
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:
    user32 = None
    kernel32 = None

# Windows Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080

# Layered window attributes (SetLayeredWindowAttributes)
LWA_COLORKEY = 0x00000001
LWA_ALPHA = 0x00000002
AC_SRC_ALPHA = 0x01

# DPI awareness constants
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE = -3
DPI_AWARENESS_CONTEXT_SYSTEM_AWARE = -2

VK_CONTROL = 0x11
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_INSERT = 0x2D
VK_HOME = 0x24

# Track whether DPI awareness has been set for this process
_dpi_awareness_set = False


def set_dpi_awareness():
    """
    Make the process per-monitor DPI aware so Tk geometry and Win32 HWND
    coordinates stay in sync on scaled (e.g. 4K / 150%) displays.
    Safe to call multiple times; only applies once per process.
    """
    global _dpi_awareness_set
    if not user32 or _dpi_awareness_set:
        return
    try:
        # Prefer the modern per-monitor-v2 context (Win10 1703+)
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        elif hasattr(user32, "SetProcessDpiAwareness"):
            # PROCESS_PER_MONITOR_DPI_AWARE = 3
            user32.SetProcessDpiAwareness(3)
        _dpi_awareness_set = True
    except Exception:
        # Fall back silently; not fatal
        pass


def get_actual_window_hwnd(tk_window) -> int:
    """
    Retrieve the actual Win32 top-level HWND for a Tkinter window.

    For a frameless (overrideredirect) Tk window, winfo_id() already returns the
    top-level HWND. For a normal Toplevel, winfo_id() returns a child HWND and we
    must walk up to the real top-level via GetParent / GetAncestor.
    """
    if not user32:
        return 0
    try:
        hwnd = tk_window.winfo_id()
        if not hwnd:
            return 0

        # Walk up to the top-level (root) window. GA_ROOT = 2.
        root = user32.GetAncestor(hwnd, 2)
        if root:
            return root

        # Fallback: GetParent chain
        parent = user32.GetParent(hwnd)
        return parent if parent != 0 else hwnd
    except Exception:
        return 0


def _apply_layered_alpha(hwnd: int, alpha: int = 255):
    """
    Apply a per-window alpha blend to a layered window.

    CRITICAL: Setting WS_EX_LAYERED without calling SetLayeredWindowAttributes
    causes the window to render as an opaque black rectangle on Windows 10/11.
    This helper ensures the layered window has a valid blend function.
    """
    if not user32 or not hwnd:
        return
    try:
        user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)
    except Exception as e:
        print(f"Error applying layered alpha ({alpha}): {e}")


def set_click_through(tk_window, enabled: bool):
    """
    Toggle click-through behavior for a window.
    When enabled, mouse clicks pass directly into the underlying game (WS_EX_TRANSPARENT).

    Also ensures the window is a properly-blended layered window so it does not
    render as a black rectangle (the classic Windows 10/11 overlay bug).
    """
    if not user32:
        return

    try:
        hwnd = get_actual_window_hwnd(tk_window)
        if not hwnd:
            return

        current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enabled:
            new_style = current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            new_style = (current_style & ~WS_EX_TRANSPARENT) | WS_EX_LAYERED

        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)

        # Re-apply layered alpha so the window stays visible (not black).
        # 235 ~ 0.92 opacity, matching the Tk -alpha 0.88 intent closely enough.
        _apply_layered_alpha(hwnd, 235)
    except Exception as e:
        print(f"Error setting click-through ({enabled}): {e}")


def set_always_on_top(tk_window, enabled: bool):
    """Ensure window stays on top of full-screen borderless games."""
    if not user32:
        return
    try:
        hwnd = get_actual_window_hwnd(tk_window)
        if not hwnd:
            return
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        target = HWND_TOPMOST if enabled else HWND_NOTOPMOST
        user32.SetWindowPos(hwnd, target, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    except Exception:
        pass


class GlobalHotkeyListener:
    """
    Background listener for safe global hotkeys using GetAsyncKeyState.
    Avoids bare F9/F10 to prevent conflicting with ETS2 multiplayer chat (F9)
    and uncompressed screenshot writes (F10).

    Supported Hotkeys:
    - Toggle Visibility: Ctrl+F9, Insert, or F11
    - Toggle Lock / Drag: Ctrl+F10 or Home
    """

    def __init__(
        self,
        on_toggle_visibility: Optional[Callable[[], None]] = None,
        on_toggle_lock: Optional[Callable[[], None]] = None,
        on_f9: Optional[Callable[[], None]] = None,
        on_f10: Optional[Callable[[], None]] = None
    ):
        self.on_toggle_visibility = on_toggle_visibility or on_f9
        self.on_toggle_lock = on_toggle_lock or on_f10
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running or not user32:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="ConvoyPace-Hotkeys")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _poll_loop(self):
        vis_pressed = False
        lock_pressed = False

        while self._running:
            try:
                ctrl_down = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                f9_down = bool(user32.GetAsyncKeyState(VK_F9) & 0x8000)
                f10_down = bool(user32.GetAsyncKeyState(VK_F10) & 0x8000)
                f11_down = bool(user32.GetAsyncKeyState(VK_F11) & 0x8000)
                insert_down = bool(user32.GetAsyncKeyState(VK_INSERT) & 0x8000)
                home_down = bool(user32.GetAsyncKeyState(VK_HOME) & 0x8000)

                # Check Toggle Visibility (Ctrl+F9, Insert, or F11) - excludes bare F9
                state_vis = (ctrl_down and f9_down) or insert_down or f11_down
                if state_vis and not vis_pressed:
                    vis_pressed = True
                    if self.on_toggle_visibility:
                        self.on_toggle_visibility()
                elif not state_vis:
                    vis_pressed = False

                # Check Toggle Lock / Drag (Ctrl+F10 or Home) - excludes bare F10
                state_lock = (ctrl_down and f10_down) or home_down
                if state_lock and not lock_pressed:
                    lock_pressed = True
                    if self.on_toggle_lock:
                        self.on_toggle_lock()
                elif not state_lock:
                    lock_pressed = False

            except Exception:
                pass

            time.sleep(0.04)  # 25 Hz polling rate (negligible CPU impact < 0.1%)

