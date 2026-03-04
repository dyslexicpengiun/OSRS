"""
Player State Tracker
Monitors and tracks the player's current state: idle, animating, moving, etc.
Used by scripts to know when an action has completed before proceeding.
"""

import time
import cv2
import numpy as np
from enum import Enum, auto
from typing import Optional, Tuple
from collections import deque

from core.screen_capture import ScreenCapture
from core.vision import Vision
from core.color_detection import ColorDetection


class PlayerState(Enum):
    UNKNOWN = auto()
    IDLE = auto()
    ANIMATING = auto()    # Performing an action (mining, chopping, etc.)
    MOVING = auto()       # Walking or running
    IN_MENU = auto()      # Right-click or interface open
    BANKING = auto()
    DEAD = auto()
    LOADING = auto()      # Area transition / loading screen


class PlayerStateTracker:
    """
    Tracks the player's current state by analyzing screen regions.
    Uses pixel comparison, XP drops, and animation frame differences.
    """

    # Region of interest around the player character (center-ish of game view)
    # Adjust if using fixed/resizable layout
    PLAYER_ROI_RELATIVE = (760, 400, 400, 280)  # x, y, w, h

    def __init__(
        self,
        config: dict,
        capture: ScreenCapture,
        vision: Vision,
        color: ColorDetection
    ):
        self.config = config
        self.capture = capture
        self.vision = vision
        self.color = color

        regions = config.get("regions", {})
        self.health_region = regions.get("health_orb", [1549, 52, 30, 30])
        self.prayer_region = regions.get("prayer_orb", [1586, 94, 30, 30])
        self.run_region = regions.get("run_orb", [1584, 137, 30, 30])
        self.chatbox_region = regions.get("chatbox", [0, 870, 519, 210])

        self._state = PlayerState.UNKNOWN
        self._last_frame: Optional[np.ndarray] = None
        self._frame_history: deque = deque(maxlen=6)
        self._last_state_change = time.time()
        self._idle_start: Optional[float] = None
        self._animation_frames_same: int = 0

        # XP drop tracking
        self._last_xp_drop_time: float = 0
        self._xp_drop_region = (1560, 60, 200, 80)  # Typical XP drop position

        # Health tracking
        self._last_health: float = 1.0
        self._last_prayer: float = 1.0

    @property
    def state(self) -> PlayerState:
        return self._state

    def update(self, screen: np.ndarray = None) -> PlayerState:
        """
        Update player state from a screenshot.
        Should be called regularly (e.g. every 200-600ms) during script loops.
        """
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return self._state

        new_state = self._detect_state(screen)
        if new_state != self._state:
            self._last_state_change = time.time()
        self._state = new_state

        # Cache frame for next comparison
        roi = self._get_player_roi(screen)
        self._frame_history.append(roi)
        self._last_frame = roi

        return self._state

    def _detect_state(self, screen: np.ndarray) -> PlayerState:
        """Run all state detection checks and return the most likely state."""

        # Check for loading screen (very dark, low variance frame)
        if self._is_loading(screen):
            return PlayerState.LOADING

        # Check health - if zero, player is dead
        health = self.get_health_percent(screen)
        if health is not None and health <= 0.02:
            return PlayerState.DEAD

        # Compare current frame to history for animation/movement detection
        if len(self._frame_history) >= 2:
            roi = self._get_player_roi(screen)
            prev_roi = self._frame_history[-1]

            if prev_roi is not None and roi.shape == prev_roi.shape:
                similarity = self.vision.compare_images(roi, prev_roi)

                if similarity < 0.90:
                    # Frame changed significantly - player is active
                    self._animation_frames_same = 0
                    self._idle_start = None

                    # Distinguish moving vs animating by checking minimap change
                    if self._is_minimap_changing(screen):
                        return PlayerState.MOVING
                    else:
                        return PlayerState.ANIMATING
                else:
                    # Frame is similar - trending toward idle
                    self._animation_frames_same += 1
                    if self._animation_frames_same >= 3:
                        if self._idle_start is None:
                            self._idle_start = time.time()
                        return PlayerState.IDLE

        return self._state if self._state != PlayerState.UNKNOWN else PlayerState.IDLE

    def _get_player_roi(self, screen: np.ndarray) -> Optional[np.ndarray]:
        """Extract the player region of interest from the screen."""
        x, y, w, h = self.PLAYER_ROI_RELATIVE
        fh, fw = screen.shape[:2]
        x = min(x, fw - 1)
        y = min(y, fh - 1)
        w = min(w, fw - x)
        h = min(h, fh - y)
        return screen[y:y+h, x:x+w].copy()

    def _is_loading(self, screen: np.ndarray) -> bool:
        """Detect loading screens (very dark, nearly uniform)."""
        # Sample the game view center
        h, w = screen.shape[:2]
        center = screen[h//3:2*h//3, w//4:3*w//4]
        mean_brightness = np.mean(center)
        std_brightness = np.std(center)
        # Loading: very dark and uniform
        return mean_brightness < 15 and std_brightness < 8

    def _is_minimap_changing(self, screen: np.ndarray) -> bool:
        """
        Check if the minimap dot positions are changing (player is walking).
        Uses pixel comparison of minimap region.
        """
        import cv2
        mm_region = self.config.get("regions", {}).get("minimap", [1714, 0, 206, 206])
        x, y, w, h = mm_region
        mm = screen[y:y+h, x:x+w]

        if len(self._frame_history) >= 2:
            # Check if white player dot exists (indicates in-game and position trackable)
            white_lower = np.array([230, 230, 230], dtype=np.uint8)
            white_upper = np.array([255, 255, 255], dtype=np.uint8)
            mask_now = cv2.inRange(mm, white_lower, white_upper)
            return bool(np.sum(mask_now) > 0)

        return False

    def get_health_percent(self, screen: np.ndarray) -> Optional[float]:
        """
        Read the health orb fill percentage.
        Returns 0.0-1.0, or None if unreadable.
        """
        rx, ry, rw, rh = self.health_region
        try:
            return self.color.get_percentage(
                screen,
                (rx, ry, rw, rh),
                'health_green',
                axis='y'
            )
        except Exception:
            return None

    def get_prayer_percent(self, screen: np.ndarray) -> Optional[float]:
        """Read the prayer orb fill percentage."""
        rx, ry, rw, rh = self.prayer_region
        try:
            return self.color.get_percentage(
                screen,
                (rx, ry, rw, rh),
                'prayer_blue',
                axis='y'
            )
        except Exception:
            return None

    def is_idle(self) -> bool:
        return self._state == PlayerState.IDLE

    def is_animating(self) -> bool:
        return self._state == PlayerState.ANIMATING

    def is_moving(self) -> bool:
        return self._state == PlayerState.MOVING

    def is_dead(self) -> bool:
        return self._state == PlayerState.DEAD

    def wait_until_idle(
        self,
        timeout: float = 15.0,
        poll_interval: float = 0.3,
        min_idle_frames: int = 3
    ) -> bool:
        """
        Block until the player becomes idle or timeout is reached.
        Returns True if idle, False if timed out.
        """
        start = time.time()
        idle_count = 0

        while (time.time() - start) < timeout:
            screen = self.capture.capture_full()
            state = self.update(screen)

            if state == PlayerState.IDLE:
                idle_count += 1
                if idle_count >= min_idle_frames:
                    return True
            else:
                idle_count = 0

            time.sleep(poll_interval)

        return False

    def wait_until_animating(self, timeout: float = 5.0, poll_interval: float = 0.2) -> bool:
        """Block until the player starts animating. Returns True if animating detected."""
        start = time.time()
        while (time.time() - start) < timeout:
            screen = self.capture.capture_full()
            state = self.update(screen)
            if state == PlayerState.ANIMATING:
                return True
            time.sleep(poll_interval)
        return False

    def time_since_state_change(self) -> float:
        """Seconds since the last state transition."""
        return time.time() - self._last_state_change

    def time_idle(self) -> float:
        """Seconds the player has been idle. 0 if not idle."""
        if self._idle_start and self._state == PlayerState.IDLE:
            return time.time() - self._idle_start
        return 0.0


