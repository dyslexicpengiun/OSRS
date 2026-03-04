"""
Color Detection System
Handles all color-based game state detection.
"""

import cv2
import numpy as np
from typing import Tuple, List, Optional, Dict


class ColorProfile:
    """Defines a color profile for a game element."""

    def __init__(self, name: str, bgr: Tuple[int, int, int],
                 tolerance: int = 15, hsv_range: Tuple = None):
        self.name = name
        self.bgr = bgr
        self.tolerance = tolerance
        self.hsv_range = hsv_range  # (lower_hsv, upper_hsv)


# Pre-defined OSRS color profiles
OSRS_COLORS = {
    # Health/Prayer/Run orbs
    'health_green': ColorProfile('health_green', (0, 188, 42), 20),
    'health_red': ColorProfile('health_red', (0, 0, 210), 30),
    'prayer_blue': ColorProfile('prayer_blue', (200, 140, 30), 25),
    'run_yellow': ColorProfile('run_yellow', (0, 200, 200), 25),

    # Inventory
    'inventory_slot_empty': ColorProfile('inventory_slot_empty', (62, 53, 41), 10),

    # Objects / Rocks
    'tin_rock': ColorProfile('tin_rock', (140, 140, 130), hsv_range=((0, 0, 100), (180, 40, 180))),
    'copper_rock': ColorProfile('copper_rock', (30, 90, 160), hsv_range=((5, 80, 80), (25, 255, 200))),
    'iron_rock': ColorProfile('iron_rock', (40, 50, 80), hsv_range=((0, 30, 40), (20, 150, 120))),
    'coal_rock': ColorProfile('coal_rock', (30, 30, 30), hsv_range=((0, 0, 10), (180, 80, 60))),
    'mithril_rock': ColorProfile('mithril_rock', (140, 80, 40), hsv_range=((100, 60, 60), (130, 200, 180))),
    'adamant_rock': ColorProfile('adamant_rock', (60, 100, 50), hsv_range=((35, 60, 50), (85, 200, 140))),
    'rune_rock': ColorProfile('rune_rock', (140, 140, 100), hsv_range=((90, 20, 80), (120, 100, 180))),

    # Depleted rock
    'depleted_rock': ColorProfile('depleted_rock', (80, 75, 65), 15),

    # Trees
    'tree_trunk': ColorProfile('tree_trunk', (30, 50, 70), hsv_range=((10, 40, 30), (30, 150, 100))),
    'tree_leaves': ColorProfile('tree_leaves', (20, 80, 30), hsv_range=((35, 40, 30), (85, 200, 120))),

    # Water / Fishing spots
    'water_blue': ColorProfile('water_blue', (180, 120, 60), hsv_range=((90, 50, 50), (130, 255, 200))),
    'fishing_spot_swirl': ColorProfile('fishing_spot_swirl', (200, 200, 200), 30),

    # Interface
    'bank_background': ColorProfile('bank_background', (48, 39, 30), 10),
    'dialog_background': ColorProfile('dialog_background', (66, 56, 43), 10),

    # Minimap
    'minimap_player_white': ColorProfile('minimap_player_white', (255, 255, 255), 5),

    # XP drops
    'xp_drop_white': ColorProfile('xp_drop_white', (255, 255, 255), 10),
}


class ColorDetection:
    """Advanced color detection for OSRS game state analysis."""

    def __init__(self):
        self.profiles = OSRS_COLORS.copy()

    def add_profile(self, name: str, profile: ColorProfile):
        """Add or update a color profile."""
        self.profiles[name] = profile

    def check_color_at(
        self,
        image: np.ndarray,
        x: int, y: int,
        profile_name: str
    ) -> bool:
        """Check if pixel at (x,y) matches a named color profile."""
        if image is None or profile_name not in self.profiles:
            return False

        profile = self.profiles[profile_name]
        h, w = image.shape[:2]
        if x < 0 or x >= w or y < 0 or y >= h:
            return False

        pixel = image[y, x]
        return all(
            abs(int(pixel[i]) - int(profile.bgr[i])) <= profile.tolerance
            for i in range(3)
        )

    def find_color_region(
        self,
        image: np.ndarray,
        profile_name: str,
        search_region: Tuple[int, int, int, int] = None,
        min_area: int = 20
    ) -> List[Tuple[int, int, int, int]]:
        """Find all regions matching a color profile."""
        if profile_name not in self.profiles:
            return []

        profile = self.profiles[profile_name]
        roi = image
        offset_x, offset_y = 0, 0

        if search_region:
            rx, ry, rw, rh = search_region
            roi = image[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry

        if profile.hsv_range:
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            lower, upper = profile.hsv_range
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        else:
            lower = np.array([max(0, c - profile.tolerance) for c in profile.bgr], dtype=np.uint8)
            upper = np.array([min(255, c + profile.tolerance) for c in profile.bgr], dtype=np.uint8)
            mask = cv2.inRange(roi, lower, upper)

        # Clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results = []
        for contour in contours:
            if cv2.contourArea(contour) >= min_area:
                x, y, w, h = cv2.boundingRect(contour)
                results.append((x + offset_x, y + offset_y, w, h))

        return results


    def find_color_region_hsv(
        self,
        image: np.ndarray,
        lower_hsv: Tuple[int, int, int],
        upper_hsv: Tuple[int, int, int],
        search_region: Tuple[int, int, int, int] = None,
        min_area: int = 20
    ) -> List[Tuple[int, int, int, int]]:
        """
        Find regions matching a raw HSV range without needing a named profile.
        Useful as a broad fallback when a named profile is too narrow.
        lower_hsv / upper_hsv are (H, S, V) tuples matching OpenCV HSV ranges
        (H: 0-179, S: 0-255, V: 0-255).
        """
        if image is None:
            return []

        roi = image
        offset_x, offset_y = 0, 0
        if search_region:
            rx, ry, rw, rh = search_region
            roi = image[ry:ry+rh, rx:rx+rw]
            offset_x, offset_y = rx, ry

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(lower_hsv), np.array(upper_hsv))

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        results = []
        for contour in contours:
            if cv2.contourArea(contour) >= min_area:
                x, y, w, h = cv2.boundingRect(contour)
                results.append((x + offset_x, y + offset_y, w, h))
        return results

    def get_percentage(
        self,
        image: np.ndarray,
        region: Tuple[int, int, int, int],
        fill_color_profile: str,
        axis: str = 'x'
    ) -> float:
        """
        Get the fill percentage of a bar (health, prayer, run, etc.)
        by detecting how far the fill color extends.
        """
        if fill_color_profile not in self.profiles:
            return 0.0

        profile = self.profiles[fill_color_profile]
        rx, ry, rw, rh = region
        roi = image[ry:ry+rh, rx:rx+rw]

        lower = np.array([max(0, c - profile.tolerance) for c in profile.bgr], dtype=np.uint8)
        upper = np.array([min(255, c + profile.tolerance) for c in profile.bgr], dtype=np.uint8)
        mask = cv2.inRange(roi, lower, upper)

        if axis == 'x':
            # Percentage along horizontal axis
            col_sums = np.sum(mask > 0, axis=0)
            threshold = rh * 0.3
            filled_cols = np.sum(col_sums > threshold)
            return filled_cols / rw if rw > 0 else 0.0
        else:
            # Percentage along vertical axis
            row_sums = np.sum(mask > 0, axis=1)
            threshold = rw * 0.3
            filled_rows = np.sum(row_sums > threshold)
            return filled_rows / rh if rh > 0 else 0.0

    def is_rock_depleted(
        self,
        image: np.ndarray,
        rock_region: Tuple[int, int, int, int]
    ) -> bool:
        """Check if a mining rock has been depleted (turned gray)."""
        rx, ry, rw, rh = rock_region
        roi = image[ry:ry+rh, rx:rx+rw]

        # Convert to HSV
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Depleted rocks are very low saturation (gray)
        mean_saturation = np.mean(hsv[:, :, 1])
        mean_value = np.mean(hsv[:, :, 2])

        # Gray rocks: low saturation, medium value
        return mean_saturation < 30 and 50 < mean_value < 150

    def count_color_pixels(
        self,
        image: np.ndarray,
        color_bgr: Tuple[int, int, int],
        tolerance: int = 15,
        region: Tuple[int, int, int, int] = None
    ) -> int:
        """Count pixels matching a color."""
        roi = image
        if region:
            rx, ry, rw, rh = region
            roi = image[ry:ry+rh, rx:rx+rw]

        lower = np.array([max(0, c - tolerance) for c in color_bgr], dtype=np.uint8)
        upper = np.array([min(255, c + tolerance) for c in color_bgr], dtype=np.uint8)
        mask = cv2.inRange(roi, lower, upper)

        return cv2.countNonZero(mask)