"""
Banking System
Handles all bank interface interactions: opening, depositing, withdrawing.
Supports both chest and booth-style banks.
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
from core.inventory import Inventory


class BankInterface:
    """
    Manages the OSRS bank interface.
    Detects when the bank is open, reads slots, and performs deposit/withdraw.
    """

    # Bank interface background color (dark brown)
    BANK_BG_COLOR = (48, 39, 30)

    # Approximate bank interface region (resizable modern)
    BANK_REGION = (30, 40, 500, 540)

    # "Deposit inventory" button region (approximate)
    DEPOSIT_INV_REGION = (260, 485, 80, 22)

    # "Deposit equipment" button region
    DEPOSIT_EQUIP_REGION = (350, 485, 90, 22)

    # Bank tab regions (8 tabs)
    TAB_REGIONS = [
        (66 + i * 45, 72, 40, 30) for i in range(9)
    ]

    def __init__(
        self,
        config: dict,
        capture: ScreenCapture,
        vision: Vision,
        input_handler: HumanizedInput,
        color: ColorDetection,
        inventory: Inventory
    ):
        self.config = config
        self.capture = capture
        self.vision = vision
        self.input = input_handler
        self.color = color
        self.inventory = inventory

        self._is_open: bool = False
        self._last_check_time: float = 0

    # ------------------------------------------------------------------
    # State detection
    # ------------------------------------------------------------------

    def is_open(self, screen: np.ndarray = None) -> bool:
        """Check if the bank interface is currently open."""
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return False

        # Check for bank background color in expected region
        bx, by, bw, bh = self.BANK_REGION
        sample_x = bx + 30
        sample_y = by + 30

        is_open = self.color.check_color_at(screen, sample_x, sample_y, 'bank_background')

        # Secondary check: look for "Bank of Gielinor" title template
        if not is_open:
            match = self.vision.find_template(
                screen,
                "interfaces/bank_title.png",
                threshold=0.80,
                region=(0, 30, 600, 60)
            )
            is_open = match is not None

        self._is_open = is_open
        return is_open

    def wait_for_open(self, timeout: float = 8.0) -> bool:
        """Wait until the bank interface opens. Returns True if opened."""
        start = time.time()
        while (time.time() - start) < timeout:
            if self.is_open():
                time.sleep(random.uniform(0.2, 0.4))  # Brief settle
                return True
            time.sleep(0.3)
        return False

    def wait_for_close(self, timeout: float = 5.0) -> bool:
        """Wait until the bank interface closes."""
        start = time.time()
        while (time.time() - start) < timeout:
            if not self.is_open():
                return True
            time.sleep(0.3)
        return False

    # ------------------------------------------------------------------
    # Opening the bank
    # ------------------------------------------------------------------

    def open_nearest(self, bank_object_region: Tuple[int, int, int, int] = None):
        """
        Right-click the nearest bank booth/chest and select 'Use Bank'.
        If bank_object_region is provided, targets that region.
        Otherwise relies on the caller to have already positioned the camera.
        """
        if bank_object_region:
            cx = bank_object_region[0] + bank_object_region[2] // 2
            cy = bank_object_region[1] + bank_object_region[3] // 2
            self.input.right_click(cx + random.randint(-5, 5), cy + random.randint(-5, 5))
            time.sleep(random.uniform(0.3, 0.6))
            self._select_menu_option("Bank")

    def close(self):
        """Close the bank interface."""
        self.input.press_key('escape')
        time.sleep(random.uniform(0.2, 0.4))
        self._is_open = False

    # ------------------------------------------------------------------
    # Deposit actions
    # ------------------------------------------------------------------

    def deposit_inventory(self):
        """Click the 'Deposit inventory' button."""
        if not self._is_open:
            return

        bx, by = self.BANK_REGION[0], self.BANK_REGION[1]
        # Try template first, fall back to approximate position
        screen = self.capture.capture_full()
        match = self.vision.find_template(
            screen, "interfaces/deposit_inv_btn.png",
            threshold=0.82, region=self.BANK_REGION
        )

        if match:
            self.input.click(match.center_x, match.center_y)
        else:
            # Approximate fallback position
            rx, ry, rw, rh = self.DEPOSIT_INV_REGION
            cx = bx + rx + rw // 2 + random.randint(-3, 3)
            cy = by + ry + rh // 2 + random.randint(-2, 2)
            self.input.click(cx, cy)

        time.sleep(random.uniform(0.3, 0.6))

    def deposit_equipment(self):
        """Click the 'Deposit worn items' button."""
        if not self._is_open:
            return

        screen = self.capture.capture_full()
        match = self.vision.find_template(
            screen, "interfaces/deposit_equip_btn.png",
            threshold=0.82, region=self.BANK_REGION
        )

        if match:
            self.input.click(match.center_x, match.center_y)
        else:
            bx, by = self.BANK_REGION[0], self.BANK_REGION[1]
            rx, ry, rw, rh = self.DEPOSIT_EQUIP_REGION
            cx = bx + rx + rw // 2 + random.randint(-3, 3)
            cy = by + ry + rh // 2 + random.randint(-2, 2)
            self.input.click(cx, cy)

        time.sleep(random.uniform(0.3, 0.6))

    def deposit_item(
        self,
        template_path: str,
        quantity: str = "all",
        screen: np.ndarray = None
    ) -> bool:
        """
        Find and deposit a specific item from the inventory panel inside the bank.
        quantity: 'all', '1', '5', '10', 'x'
        Returns True if item was found and clicked.
        """
        if not self._is_open:
            return False

        if screen is None:
            screen = self.capture.capture_full()

        match = self.vision.find_template(
            screen, template_path,
            threshold=0.80, region=self.BANK_REGION
        )

        if not match:
            return False

        if quantity == "all":
            self.input.right_click(match.center_x, match.center_y)
            time.sleep(random.uniform(0.25, 0.45))
            self._select_menu_option("Deposit-All")
        else:
            self.input.click(match.center_x, match.center_y)

        time.sleep(random.uniform(0.2, 0.4))
        return True

    # ------------------------------------------------------------------
    # Withdraw actions
    # ------------------------------------------------------------------

    def withdraw_item(
        self,
        template_path: str,
        quantity: str = "1",
        screen: np.ndarray = None
    ) -> bool:
        """
        Find and withdraw a specific item from the bank.
        quantity: '1', '5', '10', 'all', 'x'
        Returns True if item was found and clicked.
        """
        if not self._is_open:
            return False

        if screen is None:
            screen = self.capture.capture_full()

        match = self.vision.find_template(
            screen, template_path,
            threshold=0.80,
            region=self.BANK_REGION
        )

        if not match:
            return False

        if quantity == "1":
            self.input.click(match.center_x, match.center_y)
        else:
            self.input.right_click(match.center_x, match.center_y)
            time.sleep(random.uniform(0.25, 0.45))
            self._select_menu_option(f"Withdraw-{quantity.capitalize()}")

        time.sleep(random.uniform(0.25, 0.5))
        return True

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def switch_tab(self, tab_index: int):
        """Click a bank tab (0-8). Tab 0 is 'All items'."""
        if not (0 <= tab_index < len(self.TAB_REGIONS)):
            return

        bx, by = self.BANK_REGION[0], self.BANK_REGION[1]
        rx, ry, rw, rh = self.TAB_REGIONS[tab_index]
        cx = bx + rx + rw // 2 + random.randint(-3, 3)
        cy = by + ry + rh // 2 + random.randint(-2, 2)
        self.input.click(cx, cy)
        time.sleep(random.uniform(0.2, 0.4))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_menu_option(self, option_text: str, search_region: tuple = None):
        """
        Find and click a right-click menu option by its text label.
        Uses template matching for menu option icons or color-based text search.
        """
        if search_region is None:
            # Default: search right side of screen for context menus
            search_region = (200, 100, 600, 500)

        screen = self.capture.capture_full()
        match = self.vision.find_template(
            screen,
            f"interfaces/menu_{option_text.lower().replace(' ', '_').replace('-', '_')}.png",
            threshold=0.78,
            region=search_region
        )

        if match:
            self.input.click(match.center_x, match.center_y)
            time.sleep(random.uniform(0.1, 0.25))
        else:
            # OCR-based fallback would go here; for now log a warning
            import logging
            logging.getLogger(__name__).warning(
                f"[Bank] Could not find menu option: {option_text}"
            )

    def full_bank_cycle(
        self,
        deposit_all: bool = True,
        items_to_withdraw: List[Tuple[str, str]] = None
    ) -> bool:
        """
        Complete a full bank cycle: deposit → withdraw.
        items_to_withdraw: list of (template_path, quantity) tuples.
        Returns True if cycle completed successfully.
        """
        if not self.is_open():
            return False

        if deposit_all:
            self.deposit_inventory()
            time.sleep(random.uniform(0.3, 0.6))

        if items_to_withdraw:
            screen = self.capture.capture_full()
            for template_path, qty in items_to_withdraw:
                self.withdraw_item(template_path, qty, screen=screen)
                screen = self.capture.capture_full()  # Refresh after each withdrawal
                time.sleep(random.uniform(0.2, 0.45))

        return True
