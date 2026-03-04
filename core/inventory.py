"""
Inventory Management System
Detects, tracks, and interacts with the inventory.
"""

import time
import random
import cv2
import numpy as np
from typing import Optional, List, Tuple, Dict

from core.screen_capture import ScreenCapture
from core.vision import Vision, TemplateMatch
from core.input_handler import HumanizedInput
from core.color_detection import ColorDetection


class InventorySlot:
    """Represents a single inventory slot."""

    def __init__(self, index: int, x: int, y: int, width: int = 36, height: int = 32):
        self.index = index
        self.row = index // 4
        self.col = index % 4
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.item: Optional[str] = None
        self.empty: bool = True
        self.stack_size: Optional[int] = None

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def region(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def __repr__(self):
        status = f"'{self.item}'" if not self.empty else "empty"
        return f"InventorySlot({self.index}, {status})"


class Inventory:
    """
    Manages the 28-slot OSRS inventory.
    Handles detection, item identification, and interaction.
    """

    SLOT_COUNT = 28
    COLS = 4
    ROWS = 7

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

        self.regions = config.get("regions", {})
        self.inv_region = self.regions.get("inventory", [1630, 621, 280, 260])

        # Build slot grid
        self.slots: List[InventorySlot] = []
        self._build_slot_grid()

        # State
        self._last_scan_time: float = 0
        self._scan_interval: float = 0.5

    def _build_slot_grid(self):
        """Calculate pixel positions for all 28 inventory slots."""
        # OSRS inventory slot dimensions (resizable modern layout)
        x_start = self.inv_region[0] + 13
        y_start = self.inv_region[1] + 9
        x_spacing = 42
        y_spacing = 36
        slot_w = 36
        slot_h = 32

        self.slots = []
        for i in range(self.SLOT_COUNT):
            row = i // self.COLS
            col = i % self.COLS
            x = x_start + col * x_spacing
            y = y_start + row * y_spacing
            self.slots.append(InventorySlot(i, x, y, slot_w, slot_h))

    def get_slot(self, index: int) -> Optional[InventorySlot]:
        """Get a slot by index (0-27)."""
        if 0 <= index < self.SLOT_COUNT:
            return self.slots[index]
        return None

    def scan(self, screen: np.ndarray = None) -> List[InventorySlot]:
        """
        Scan the inventory to update slot states.
        Returns list of all slots with updated empty/item status.
        """
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return self.slots

        for slot in self.slots:
            slot.empty = self._is_slot_empty(screen, slot)

        self._last_scan_time = time.time()
        return self.slots

    def _is_slot_empty(self, screen: np.ndarray, slot: InventorySlot) -> bool:
        """
        Determine if an inventory slot is empty by checking the
        characteristic dark brown background color.
        """
        rx, ry, rw, rh = slot.region
        # Sample a few pixels in the center of the slot
        cx, cy = slot.center
        sample_points = [
            (cx, cy),
            (cx - 6, cy),
            (cx + 6, cy),
            (cx, cy - 5),
        ]

        match_count = 0
        for px, py in sample_points:
            if self.color.check_color_at(screen, px, py, 'inventory_slot_empty'):
                match_count += 1

        # If most sample points match the empty color, slot is empty
        return match_count >= 2

    def count_empty(self) -> int:
        """Return number of empty slots."""
        return sum(1 for s in self.slots if s.empty)

    def count_filled(self) -> int:
        """Return number of filled slots."""
        return sum(1 for s in self.slots if not s.empty)

    def is_full(self) -> bool:
        """Check if inventory is completely full."""
        return self.count_empty() == 0

    def is_empty(self) -> bool:
        """Check if inventory is completely empty."""
        return self.count_filled() == 0

    def get_empty_slots(self) -> List[InventorySlot]:
        """Get list of empty slots."""
        return [s for s in self.slots if s.empty]

    def get_filled_slots(self) -> List[InventorySlot]:
        """Get list of filled slots."""
        return [s for s in self.slots if not s.empty]

    def find_item(
        self,
        template_path: str,
        screen: np.ndarray = None,
        threshold: float = 0.80
    ) -> Optional[InventorySlot]:
        """
        Find the first slot containing a specific item by template matching.
        Returns the slot, or None if not found.
        """
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return None

        match = self.vision.find_template(
            screen, template_path,
            threshold=threshold,
            region=tuple(self.inv_region)
        )

        if match:
            # Find which slot this match falls in
            for slot in self.slots:
                sx, sy, sw, sh = slot.region
                if (sx <= match.center_x <= sx + sw and
                        sy <= match.center_y <= sy + sh):
                    slot.item = template_path
                    slot.empty = False
                    return slot
        return None

    def find_all_items(
        self,
        template_path: str,
        screen: np.ndarray = None,
        threshold: float = 0.80
    ) -> List[InventorySlot]:
        """Find all slots containing a specific item."""
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return []

        matches = self.vision.find_all_templates(
            screen, template_path,
            threshold=threshold,
            region=tuple(self.inv_region)
        )

        found_slots = []
        for match in matches:
            for slot in self.slots:
                sx, sy, sw, sh = slot.region
                if (sx <= match.center_x <= sx + sw and
                        sy <= match.center_y <= sy + sh):
                    slot.item = template_path
                    slot.empty = False
                    found_slots.append(slot)
                    break

        return found_slots

    def click_slot(self, slot_index: int, button: str = "left", variance: int = 5):
        """Click a specific inventory slot."""
        slot = self.get_slot(slot_index)
        if slot:
            cx, cy = slot.center
            # Add natural variance within the slot
            cx += random.randint(-variance, variance)
            cy += random.randint(-variance, variance)
            self.input.click(cx, cy, button=button)

    def click_item(
        self,
        template_path: str,
        screen: np.ndarray = None,
        button: str = "left",
        variance: int = 5
    ) -> bool:
        """Find and click an item in the inventory. Returns True if clicked."""
        slot = self.find_item(template_path, screen)
        if slot:
            self.click_slot(slot.index, button=button, variance=variance)
            return True
        return False

    def drop_item(self, slot_index: int):
        """Drop an item from a slot (shift+click)."""
        slot = self.get_slot(slot_index)
        if slot:
            self.input.press_key('shift')
            time.sleep(random.uniform(0.05, 0.1))
            self.click_slot(slot_index)

    def drop_all_items(self, exclude_slots: List[int] = None, delay_range=(0.1, 0.3)):
        """
        Drop all items from inventory.
        exclude_slots: List of slot indices to skip.
        """
        exclude = set(exclude_slots or [])
        filled = [s for s in self.get_filled_slots() if s.index not in exclude]

        for slot in filled:
            self.drop_item(slot.index)
            time.sleep(random.uniform(*delay_range))

    def open_tab(self):
        """Click the inventory tab to open it."""
        inv_tab = self.regions.get("tabs", {}).get("inventory")
        if inv_tab:
            cx = inv_tab[0] + inv_tab[2] // 2
            cy = inv_tab[1] + inv_tab[3] // 2
            self.input.click(cx, cy)
            time.sleep(random.uniform(0.1, 0.25))

    def use_item_on_item(self, slot_a: int, slot_b: int):
        """Use item in slot_a on item in slot_b."""
        self.click_slot(slot_a)
        time.sleep(random.uniform(0.08, 0.18))
        self.click_slot(slot_b)

    def get_item_count(self, template_path: str, screen: np.ndarray = None) -> int:
        """Count how many of a specific item are in the inventory."""
        return len(self.find_all_items(template_path, screen))

    def __repr__(self):
        return (f"Inventory(filled={self.count_filled()}/28, "
                f"empty={self.count_empty()})")
