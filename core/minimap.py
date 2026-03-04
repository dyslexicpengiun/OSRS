"""
Minimap System
Reads minimap data for navigation, obstacle avoidance, and position awareness.
Handles clicking the minimap to walk to locations and reading dot positions.
"""

import time
import random
import math
import cv2
import numpy as np
from typing import Optional, Tuple, List

from core.screen_capture import ScreenCapture
from core.vision import Vision
from core.input_handler import HumanizedInput
from core.color_detection import ColorDetection


class MinimapNavigator:
    """
    Handles minimap-based navigation in OSRS.
    Can click minimap tiles to walk, detect player dot, and read map colors.
    """

    # Minimap is a circle; these are the display bounds
    MM_CENTER_OFFSET = (103, 103)   # Center of minimap within its region
    MM_RADIUS = 73                  # Usable radius in pixels

    # Minimap colors (BGR)
    COLOR_WATER = (180, 120, 60)
    COLOR_PATH = (90, 80, 65)
    COLOR_GRASS = (50, 90, 40)
    COLOR_WALL = (30, 30, 30)
    COLOR_PLAYER_DOT = (255, 255, 255)
    COLOR_NPC_DOT = (255, 255, 0)
    COLOR_ITEM_DOT = (0, 200, 200)

    def __init__(
        self,
        config: dict,
        capture: ScreenCapture,
        vision: Vision,
        input_handler: HumanizedInput,
        color: ColorDetection
    ):
        self.config = config
        self.capture = capture
        self.vision = vision
        self.input = input_handler
        self.color = color

        regions = config.get("regions", {})
        mm = regions.get("minimap", [1714, 0, 206, 206])
        self.mm_x, self.mm_y, self.mm_w, self.mm_h = mm
        self.mm_cx = self.mm_x + self.MM_CENTER_OFFSET[0]
        self.mm_cy = self.mm_y + self.MM_CENTER_OFFSET[1]

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def click_tile(self, dx: int, dy: int):
        """
        Click a minimap tile relative to center (player position).
        dx, dy: pixel offset from minimap center (positive = east/south).
        Clamps to within the circular minimap boundary.
        """
        # Clamp to minimap circle
        dist = math.hypot(dx, dy)
        if dist > self.MM_RADIUS:
            scale = self.MM_RADIUS / dist * 0.92  # 8% margin
            dx = int(dx * scale)
            dy = int(dy * scale)

        target_x = self.mm_cx + dx + random.randint(-2, 2)
        target_y = self.mm_cy + dy + random.randint(-2, 2)

        self.input.click(target_x, target_y)
        time.sleep(random.uniform(0.08, 0.2))

    def walk_towards(self, direction: str, steps: int = 1):
        """
        Click the minimap to walk in a cardinal direction.
        direction: 'north', 'south', 'east', 'west', or ordinals.
        steps: How many minimap clicks to make (each click ~15 tiles).
        """
        dir_map = {
            'north':     (0, -50),
            'south':     (0, 50),
            'east':      (50, 0),
            'west':      (-50, 0),
            'northeast': (35, -35),
            'northwest': (-35, -35),
            'southeast': (35, 35),
            'southwest': (-35, 35),
        }
        offset = dir_map.get(direction.lower())
        if offset is None:
            return

        for _ in range(steps):
            dx = offset[0] + random.randint(-5, 5)
            dy = offset[1] + random.randint(-5, 5)
            self.click_tile(dx, dy)
            time.sleep(random.uniform(0.5, 1.2))

    def click_minimap_absolute(self, world_x: int, world_y: int, player_x: int, player_y: int):
        """
        Click the minimap at a world tile position.
        Converts world coordinates to minimap pixel offsets.
        OSRS minimap: 1 tile ≈ 4 pixels at default zoom.
        """
        px_per_tile = 4.0
        dx = int((world_x - player_x) * px_per_tile)
        dy = int((player_y - world_y) * px_per_tile)  # Y is inverted
        self.click_tile(dx, dy)

    # ------------------------------------------------------------------
    # Dot detection
    # ------------------------------------------------------------------

    def find_player_dot(self, screen: np.ndarray = None) -> Optional[Tuple[int, int]]:
        """
        Find the white player dot on the minimap.
        Returns (x, y) in screen coordinates, or None.
        """
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return None

        mm_roi = screen[self.mm_y:self.mm_y+self.mm_h, self.mm_x:self.mm_x+self.mm_w]

        # Player dot: bright white, small
        lower = np.array([240, 240, 240], dtype=np.uint8)
        upper = np.array([255, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(mm_roi, lower, upper)

        # Player dot is ~3x3 pixels
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        best_size = 0
        for c in contours:
            area = cv2.contourArea(c)
            if 2 < area < 40:
                M = cv2.moments(c)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"]) + self.mm_x
                    cy = int(M["m01"] / M["m00"]) + self.mm_y
                    if area > best_size:
                        best = (cx, cy)
                        best_size = area

        return best

    def find_npc_dots(self, screen: np.ndarray = None) -> List[Tuple[int, int]]:
        """Find yellow NPC dots on the minimap."""
        return self._find_dots(
            screen,
            lower=(0, 200, 200),
            upper=(50, 255, 255),
            min_area=2,
            max_area=30
        )

    def find_item_dots(self, screen: np.ndarray = None) -> List[Tuple[int, int]]:
        """Find cyan item dots on the minimap."""
        return self._find_dots(
            screen,
            lower=(180, 180, 0),
            upper=(255, 255, 50),
            min_area=2,
            max_area=20
        )

    def _find_dots(
        self,
        screen: np.ndarray,
        lower: tuple,
        upper: tuple,
        min_area: int,
        max_area: int
    ) -> List[Tuple[int, int]]:
        """Generic dot finder on the minimap."""
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return []

        mm_roi = screen[self.mm_y:self.mm_y+self.mm_h, self.mm_x:self.mm_x+self.mm_w]
        mask = cv2.inRange(mm_roi, np.array(lower, dtype=np.uint8), np.array(upper, dtype=np.uint8))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        results = []
        for c in contours:
            area = cv2.contourArea(c)
            if min_area <= area <= max_area:
                M = cv2.moments(c)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"]) + self.mm_x
                    cy = int(M["m01"] / M["m00"]) + self.mm_y
                    results.append((cx, cy))

        return results

    # ------------------------------------------------------------------
    # Tile color reading
    # ------------------------------------------------------------------

    def get_tile_color_at_offset(
        self,
        screen: np.ndarray,
        dx: int,
        dy: int
    ) -> Optional[Tuple[int, int, int]]:
        """
        Sample the minimap color at a pixel offset from the player position.
        Useful for detecting water, paths, walls etc. before clicking.
        """
        px = self.mm_cx + dx
        py = self.mm_cy + dy

        # Check bounds
        if not (self.mm_x <= px < self.mm_x + self.mm_w and
                self.mm_y <= py < self.mm_y + self.mm_h):
            return None

        h, w = screen.shape[:2]
        if 0 <= py < h and 0 <= px < w:
            b, g, r = screen[py, px]
            return (int(b), int(g), int(r))

        return None

    def is_walkable_at_offset(self, screen: np.ndarray, dx: int, dy: int) -> bool:
        """Check if a minimap tile is walkable (not wall/water)."""
        color = self.get_tile_color_at_offset(screen, dx, dy)
        if color is None:
            return False

        b, g, r = color

        # Water: high blue
        if b > 140 and g < 120 and r < 80:
            return False

        # Very dark (wall/object)
        if b < 20 and g < 20 and r < 20:
            return False

        return True

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @property
    def center(self) -> Tuple[int, int]:
        return (self.mm_cx, self.mm_cy)

    def distance_on_minimap(self, dot_screen_pos: Tuple[int, int]) -> float:
        """Return pixel distance from minimap center to a dot position."""
        return math.hypot(
            dot_screen_pos[0] - self.mm_cx,
            dot_screen_pos[1] - self.mm_cy
        )
