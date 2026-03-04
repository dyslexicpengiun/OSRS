"""
Overlay Widget Definitions
Higher-level overlay components built on top of core/overlay.py.
Scripts use these to draw useful on-screen info during execution.
"""

import time
import math
from typing import Optional, Tuple, Dict

from core.overlay import GameOverlay


class DebugBox:
    """Draws a labeled bounding box around a detected object."""
    def __init__(self, overlay: GameOverlay, widget_id: str, color: str = "#00FF00"):
        self.overlay = overlay
        self.id = widget_id
        self.color = color

    def show(self, x: int, y: int, w: int, h: int,
             label: str = "", ttl: float = 2.0):
        self.overlay.draw_rect(self.id, x, y, w, h, color=self.color, ttl=ttl)
        if label:
            self.overlay.draw_text(f"{self.id}_lbl", x, y - 14, label,
                                    color=self.color, size=9, ttl=ttl)

    def hide(self):
        self.overlay.remove_widget(self.id)
        self.overlay.remove_widget(f"{self.id}_lbl")


class ClickMarker:
    """Shows a brief crosshair/dot where a click was performed."""
    def __init__(self, overlay: GameOverlay):
        self.overlay = overlay
        self._counter = 0

    def mark(self, x: int, y: int, color: str = "#FF4400", ttl: float = 0.8):
        uid = f"click_{self._counter % 20}"
        self._counter += 1
        self.overlay.draw_circle(uid, x, y, radius=6, color=color, ttl=ttl)
        # Crosshair lines
        self.overlay.draw_text(f"{uid}_x", x - 4, y - 14, "+",
                                color=color, size=14, ttl=ttl)


class HealthBar:
    """
    Renders a health bar at a fixed screen position showing current %.
    Useful for mirroring the in-game orb value in a more readable way.
    """
    def __init__(self, overlay: GameOverlay, x: int, y: int,
                 width: int = 120, height: int = 12):
        self.overlay = overlay
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def update(self, pct: float, label: str = "HP"):
        """pct: 0.0-1.0"""
        pct = max(0.0, min(1.0, pct))
        color = "#00FF00" if pct > 0.6 else ("#FFD700" if pct > 0.3 else "#FF2200")
        fill_w = int(self.width * pct)

        # Background bar
        self.overlay.draw_rect("hpbar_bg", self.x, self.y,
                                self.width, self.height, color="#333333", ttl=2.5)
        # Fill
        if fill_w > 0:
            self.overlay.draw_rect("hpbar_fill", self.x, self.y,
                                    fill_w, self.height, color=color, ttl=2.5)
        # Label
        self.overlay.draw_text("hpbar_lbl",
                                self.x + self.width + 5, self.y,
                                f"{label}: {pct*100:.0f}%",
                                color=color, size=9, ttl=2.5)


class Compass:
    """Draws a simple compass rose on the overlay showing current camera yaw."""
    DIRECTIONS = {0: "N", 45: "NE", 90: "E", 135: "SE",
                  180: "S", 225: "SW", 270: "W", 315: "NW"}

    def __init__(self, overlay: GameOverlay, x: int = 50, y: int = 50, radius: int = 30):
        self.overlay = overlay
        self.x = x
        self.y = y
        self.radius = radius

    def update(self, yaw_degrees: float):
        """Redraw the compass pointer."""
        rad = math.radians(yaw_degrees)
        ex = int(self.x + self.radius * math.sin(rad))
        ey = int(self.y - self.radius * math.cos(rad))

        self.overlay.draw_circle("compass_bg", self.x, self.y,
                                  radius=self.radius, color="#445566", ttl=2.5)
        self.overlay.draw_text("compass_N", self.x - 4, self.y - self.radius - 14,
                                "N", color="#FF4444", size=9, ttl=2.5)
        self.overlay.draw_circle("compass_arrow_tip", ex, ey,
                                  radius=4, color="#FF4444", ttl=2.5)
        self.overlay.draw_text("compass_yaw",
                                self.x - 15, self.y + self.radius + 4,
                                f"{yaw_degrees:.0f}°", color="#AAAAAA", size=8, ttl=2.5)


class MinimapDotOverlay:
    """Highlights detected minimap dots with colored circles."""
    def __init__(self, overlay: GameOverlay):
        self.overlay = overlay
        self._dot_count = 0

    def show_dots(self, dots, color: str = "#FFFF00", ttl: float = 2.0):
        """dots: list of (screen_x, screen_y) tuples."""
        self._dot_count = 0
        for x, y in dots:
            uid = f"mmdot_{self._dot_count}"
            self._dot_count += 1
            self.overlay.draw_circle(uid, x, y, radius=4, color=color, ttl=ttl)

    def clear(self):
        for i in range(self._dot_count):
            self.overlay.remove_widget(f"mmdot_{i}")
        self._dot_count = 0


class ScriptStatusPanel:
    """
    Compact script status block shown in a corner of the screen.
    Displays script name, state, runtime, key metrics.
    """
    def __init__(self, overlay: GameOverlay, x: int = 10, y: int = 10):
        self.overlay = overlay
        self.x = x
        self.y = y

    def update(self, data: Dict[str, str]):
        """data: dict of label->value pairs to display."""
        lines = [f"{k}: {v}" for k, v in data.items()]
        for i, line in enumerate(lines):
            self.overlay.draw_text(
                f"status_line_{i}",
                self.x, self.y + i * 15,
                line,
                color="#AAFFAA",
                size=9,
                ttl=3.0
            )
