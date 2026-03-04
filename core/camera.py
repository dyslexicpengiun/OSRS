"""
Camera Control System
Manages in-game camera rotation, pitch, and zoom.
Uses middle-mouse-drag and keyboard shortcuts for natural movement.
"""

import time
import random
import math
from typing import Tuple, Optional

from core.input_handler import HumanizedInput
from core.screen_capture import ScreenCapture


class Camera:
    """
    Controls the OSRS camera via middle-mouse-drag and arrow keys.
    Tracks approximate yaw (compass heading) and pitch.
    """

    # OSRS compass is top-right of minimap area
    COMPASS_REGION = (1785, 3, 30, 30)

    def __init__(self, config: dict, input_handler: HumanizedInput, capture: ScreenCapture):
        self.config = config
        self.input = input_handler
        self.capture = capture

        resolution = config.get("resolution", {})
        self.screen_w = resolution.get("width", 1920)
        self.screen_h = resolution.get("height", 1080)

        # Camera state (approximate - can't read exact angle without OCR on compass)
        self._yaw: float = 0.0    # 0 = north, degrees clockwise
        self._pitch: float = 383  # OSRS pitch units, default ~383 (middle)

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------

    def rotate(self, direction: str, degrees: float = 15.0):
        """
        Rotate the camera left or right using middle mouse drag.

        Args:
            direction: 'left' or 'right'
            degrees: approximate visual degrees to rotate
        """
        # Middle of game view as drag origin
        cx = self.screen_w // 2 + random.randint(-80, 80)
        cy = self.screen_h // 2 + random.randint(-60, 60)

        # Pixels per degree is roughly 3-4 in OSRS
        px_per_degree = random.uniform(3.0, 4.2)
        drag_px = int(degrees * px_per_degree)

        if direction == 'left':
            end_x = cx - drag_px
        else:
            end_x = cx + drag_px

        end_y = cy + random.randint(-10, 10)

        # Middle mouse drag
        self.input.drag(cx, cy, end_x, end_y, button="middle")

        if direction == 'left':
            self._yaw = (self._yaw - degrees) % 360
        else:
            self._yaw = (self._yaw + degrees) % 360

        time.sleep(random.uniform(0.05, 0.15))

    def face_north(self):
        """Reset camera to face north (click compass)."""
        compass = self.COMPASS_REGION
        cx = compass[0] + compass[2] // 2 + random.randint(-3, 3)
        cy = compass[1] + compass[3] // 2 + random.randint(-3, 3)
        self.input.click(cx, cy)
        self._yaw = 0.0
        time.sleep(random.uniform(0.3, 0.6))

    def rotate_to_angle(self, target_yaw: float, tolerance: float = 10.0):
        """Rotate to approximately face a target compass heading (0 = north)."""
        diff = (target_yaw - self._yaw + 360) % 360
        if diff <= tolerance or diff >= (360 - tolerance):
            return  # Already roughly facing the right direction

        if diff > 180:
            direction = 'left'
            degrees = 360 - diff
        else:
            direction = 'right'
            degrees = diff

        self.rotate(direction, degrees)

    # ------------------------------------------------------------------
    # Pitch (vertical angle)
    # ------------------------------------------------------------------

    def set_pitch_up(self):
        """Tilt camera up (more top-down view)."""
        presses = random.randint(2, 5)
        for _ in range(presses):
            self.input.press_key('up')
            time.sleep(random.uniform(0.05, 0.12))

    def set_pitch_down(self):
        """Tilt camera down (more horizontal view)."""
        presses = random.randint(2, 5)
        for _ in range(presses):
            self.input.press_key('down')
            time.sleep(random.uniform(0.05, 0.12))

    def set_max_pitch(self):
        """Set camera to maximum height (most top-down)."""
        for _ in range(12):
            self.input.press_key('up')
            time.sleep(random.uniform(0.04, 0.09))

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def zoom_in(self, clicks: int = 3):
        """Zoom in using scroll wheel."""
        self.input.scroll("up", clicks)

    def zoom_out(self, clicks: int = 3):
        """Zoom out using scroll wheel."""
        self.input.scroll("down", clicks)

    def set_default_zoom(self):
        """Reset zoom to a standard level."""
        # Zoom all the way out then back in a set amount
        self.input.scroll("down", 10)
        time.sleep(random.uniform(0.2, 0.4))
        self.input.scroll("up", 4)
        time.sleep(random.uniform(0.1, 0.2))

    # ------------------------------------------------------------------
    # Random humanization
    # ------------------------------------------------------------------

    def random_adjustment(self):
        """
        Make a small random camera adjustment to simulate a human
        glancing around naturally.
        """
        choice = random.random()
        if choice < 0.4:
            # Small rotation
            direction = random.choice(['left', 'right'])
            degrees = random.uniform(3, 18)
            self.rotate(direction, degrees)
        elif choice < 0.65:
            # Slight pitch change
            if random.random() < 0.5:
                self.set_pitch_up()
            else:
                self.set_pitch_down()
        elif choice < 0.80:
            # Scroll zoom nudge
            direction = random.choice(['up', 'down'])
            self.input.scroll(direction, random.randint(1, 2))
        # else: no adjustment

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def yaw(self) -> float:
        return self._yaw

    def __repr__(self):
        return f"Camera(yaw={self._yaw:.1f}°)"
