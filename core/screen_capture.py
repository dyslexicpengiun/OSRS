"""
Fast Screen Capture System
Provides high-performance screen capture with region support.
Uses mss for speed, with win32 fallback.
"""

import time
import numpy as np
import mss
import mss.tools
import cv2
from PIL import Image
import win32gui
import win32ui
import win32con
import ctypes
from ctypes import windll
import threading


class ScreenCapture:
    """High-performance screen capture with region caching."""

    # Known OSRS client window title substrings, in priority order.
    # Any window whose title contains one of these (case-insensitive) is valid.
    DEFAULT_CLIENT_TITLES = [
        "RuneLite",              # RuneLite (most common third-party client)
        "Old School RuneScape",  # Jagex official client
        "HDOS",                  # HDOS client
    ]

    def __init__(self, config: dict):
        self.config = config

        # Support both legacy single string and new list form in config.json
        cfg_titles = config.get("game_window_titles")
        if not cfg_titles:
            legacy = config.get("game_window_title")
            cfg_titles = [legacy] if legacy else []

        # Merge config-provided titles with built-ins (config order takes priority)
        seen = set()
        merged = []
        for t in cfg_titles + self.DEFAULT_CLIENT_TITLES:
            if t.lower() not in seen:
                seen.add(t.lower())
                merged.append(t)
        self._client_titles = merged

        # Back-compat attribute; updated to matched client after find_game_window()
        self.window_title = self._client_titles[0] if self._client_titles else "Old School RuneScape"
        self.detected_client: str = ""   # populated once a window is found

        self._sct = mss.mss()
        self._hwnd = None
        self._window_rect = None
        self._lock = threading.Lock()
        self._frame_cache = {}
        self._cache_ttl = 0.05  # 50ms cache validity
        self._last_capture_time = 0
        self._last_full_frame = None

        # Make DPI aware
        try:
            windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    def find_game_window(self) -> bool:
        """
        Find the OSRS game window handle.

        Enumerates all visible windows and matches against the configured
        client title list in priority order (RuneLite first, then official
        client, then HDOS, then any extras defined in config.json).

        Returns True if any known client window is found.
        Sets self.detected_client to the matched title string.
        """
        # Snapshot all visible windows once
        visible_windows: list = []

        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    visible_windows.append((hwnd, title))

        win32gui.EnumWindows(enum_callback, None)

        # Walk priority list — first match wins
        for client_title in self._client_titles:
            needle = client_title.lower()
            for hwnd, title in visible_windows:
                if needle in title.lower():
                    self._hwnd = hwnd
                    self.detected_client = client_title
                    self.window_title = client_title   # keep back-compat attr in sync
                    self._update_window_rect()
                    return True

        self.detected_client = ""
        return False

    def _update_window_rect(self):
        """Update cached window rectangle."""
        if self._hwnd and win32gui.IsWindow(self._hwnd):
            try:
                rect = win32gui.GetWindowRect(self._hwnd)
                # Account for window borders
                client_rect = win32gui.GetClientRect(self._hwnd)
                point = win32gui.ClientToScreen(self._hwnd, (0, 0))
                self._window_rect = {
                    "left": point[0],
                    "top": point[1],
                    "width": client_rect[2],
                    "height": client_rect[3]
                }
            except Exception:
                self._window_rect = None

    def get_window_rect(self) -> dict:
        """Get current game window rectangle."""
        self._update_window_rect()
        return self._window_rect

    def capture_full(self) -> np.ndarray:
        """
        Capture the full game window as a numpy array (BGR).

        Automatically retries find_game_window() if the window rect is
        missing or the stored handle is no longer valid.  This means the
        script will recover automatically if the game was minimised or
        hadn't been opened yet when the engine started.

        Returns None only if the game window genuinely cannot be found.
        """
        with self._lock:
            now = time.time()
            if self._last_full_frame is not None and (now - self._last_capture_time) < self._cache_ttl:
                return self._last_full_frame.copy()

            # Re-validate handle: covers start-up race and window-moved cases
            need_search = (
                not self._window_rect
                or not self._hwnd
                or not win32gui.IsWindow(self._hwnd)
            )
            if need_search:
                if not self.find_game_window():
                    return None  # game not open

            try:
                monitor = {
                    "left":   self._window_rect["left"],
                    "top":    self._window_rect["top"],
                    "width":  self._window_rect["width"],
                    "height": self._window_rect["height"],
                }
                screenshot = self._sct.grab(monitor)
                frame = np.array(screenshot, dtype=np.uint8)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                self._last_full_frame = frame
                self._last_capture_time = now
                return frame.copy()
            except Exception:
                # Position may have changed (e.g. window dragged); refresh and bail
                self._update_window_rect()
                self._last_full_frame = None
                return None

    def capture_region(self, region: tuple) -> np.ndarray:
        """
        Capture a specific region of the game window.
        region: (x, y, width, height) relative to game window
        Returns BGR numpy array.
        """
        full = self.capture_full()
        if full is None:
            return None

        x, y, w, h = region
        # Clamp to frame bounds
        fh, fw = full.shape[:2]
        x = max(0, min(x, fw))
        y = max(0, min(y, fh))
        w = min(w, fw - x)
        h = min(h, fh - y)

        return full[y:y+h, x:x+w].copy()

    def capture_region_absolute(self, region: tuple) -> np.ndarray:
        """
        Capture a region using absolute screen coordinates.
        region: (x, y, width, height) in screen coordinates
        """
        try:
            monitor = {
                "left": region[0],
                "top": region[1],
                "width": region[2],
                "height": region[3]
            }
            screenshot = self._sct.grab(monitor)
            frame = np.array(screenshot, dtype=np.uint8)
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        except Exception:
            return None

    def get_pixel_color(self, x: int, y: int) -> tuple:
        """Get the color of a pixel at game-window-relative coordinates. Returns (B, G, R)."""
        full = self.capture_full()
        if full is None:
            return None
        fh, fw = full.shape[:2]
        if 0 <= x < fw and 0 <= y < fh:
            return tuple(full[y, x])
        return None

    def get_pixel_color_absolute(self, x: int, y: int) -> tuple:
        """Get pixel color at absolute screen coordinates."""
        if self._window_rect:
            rel_x = x - self._window_rect["left"]
            rel_y = y - self._window_rect["top"]
            return self.get_pixel_color(rel_x, rel_y)
        return None

    def game_to_screen(self, x: int, y: int) -> tuple:
        """Convert game-window-relative coords to screen coords."""
        if self._window_rect:
            return (
                x + self._window_rect["left"],
                y + self._window_rect["top"]
            )
        return (x, y)

    def screen_to_game(self, x: int, y: int) -> tuple:
        """Convert screen coords to game-window-relative coords."""
        if self._window_rect:
            return (
                x - self._window_rect["left"],
                y - self._window_rect["top"]
            )
        return (x, y)

    def is_game_focused(self) -> bool:
        """Check if the game window is the foreground window."""
        try:
            return win32gui.GetForegroundWindow() == self._hwnd
        except Exception:
            return False

    def focus_game_window(self):
        """Bring the game window to focus."""
        if self._hwnd:
            try:
                win32gui.SetForegroundWindow(self._hwnd)
                time.sleep(0.1)
            except Exception:
                pass

    def invalidate_cache(self):
        """Force next capture to be fresh."""
        self._last_capture_time = 0
        self._last_full_frame = None