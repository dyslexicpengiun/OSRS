"""
Interface Detection System
Handles generic OSRS UI elements: right-click menus, dialog boxes,
level-up popups, make-X interfaces, and tab management.
"""

import time
import random
import cv2
import numpy as np
from typing import Optional, List, Tuple, Dict

from core.screen_capture import ScreenCapture
from core.vision import Vision
from core.input_handler import HumanizedInput
from core.color_detection import ColorDetection
from core.ocr import OSRSTextReader


class InterfaceManager:
    """
    Detects and interacts with OSRS UI interfaces.
    """

    # Right-click menu header color (yellow text on dark bg)
    MENU_HEADER_COLOR = (0, 255, 255)  # BGR yellow

    # Dialog/popup background
    DIALOG_BG_COLOR = (66, 56, 43)

    # Level up banner: bright golden-yellow area at top of screen
    LEVEL_UP_REGION = (300, 40, 900, 80)

    # Make-X interface (smithing, cooking, etc.)
    MAKE_X_REGION = (200, 300, 800, 200)

    # "Click here to continue" chatbox prompt
    CONTINUE_REGION = (0, 870, 519, 210)

    def __init__(
        self,
        config: dict,
        capture: ScreenCapture,
        vision: Vision,
        input_handler: HumanizedInput,
        color: ColorDetection,
        ocr: OSRSTextReader
    ):
        self.config = config
        self.capture = capture
        self.vision = vision
        self.input = input_handler
        self.color = color
        self.ocr = ocr

        regions = config.get("regions", {})
        self.chatbox_region = regions.get("chatbox", [0, 870, 519, 210])
        self.tabs = regions.get("tabs", {})

    # ------------------------------------------------------------------
    # Right-click menu
    # ------------------------------------------------------------------

    def is_menu_open(self, screen: np.ndarray = None) -> bool:
        """Check if a right-click context menu is currently visible."""
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return False

        # Right-click menu always has a yellow "Choose Option" header
        regions = self.color.find_color_region(
            screen,
            profile_name=None,
            search_region=None
        )
        # Use vision to check for the context menu template
        match = self.vision.find_template(
            screen, "interfaces/context_menu_header.png",
            threshold=0.75
        )
        return match is not None

    def find_menu_option(
        self,
        option_text: str,
        screen: np.ndarray = None,
        search_region: Tuple[int, int, int, int] = None
    ) -> Optional[Tuple[int, int]]:
        """
        Find a specific option in an open right-click menu.
        Returns the (x, y) center of the option, or None.
        Uses OCR to read menu text.
        """
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return None

        result = self.ocr.find_text_on_screen(
            screen,
            option_text,
            text_color='white',
            region=search_region,
            threshold=0.75
        )
        return result

    def click_menu_option(
        self,
        option_text: str,
        screen: np.ndarray = None,
        fallback_close: bool = True
    ) -> bool:
        """
        Find and click a right-click menu option.
        Returns True if the option was found and clicked.
        """
        pos = self.find_menu_option(option_text, screen)
        if pos:
            self.input.click(
                pos[0] + random.randint(-3, 3),
                pos[1] + random.randint(-2, 2)
            )
            time.sleep(random.uniform(0.1, 0.25))
            return True

        if fallback_close:
            # Close menu if option not found
            self.input.press_key('escape')
            time.sleep(random.uniform(0.1, 0.2))

        return False

    def close_menu(self):
        """Close any open right-click menu."""
        self.input.press_key('escape')
        time.sleep(random.uniform(0.1, 0.2))

    # ------------------------------------------------------------------
    # Level up interface
    # ------------------------------------------------------------------

    def is_level_up_visible(self, screen: np.ndarray = None) -> bool:
        """Check if a level-up congratulations banner is visible."""
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return False

        match = self.vision.find_template(
            screen, "interfaces/level_up.png",
            threshold=0.80,
            region=self.LEVEL_UP_REGION
        )
        return match is not None

    def dismiss_level_up(self, screen: np.ndarray = None) -> bool:
        """Dismiss a level-up popup by clicking it. Returns True if dismissed."""
        if screen is None:
            screen = self.capture.capture_full()

        match = self.vision.find_template(
            screen, "interfaces/level_up.png",
            threshold=0.80,
            region=self.LEVEL_UP_REGION
        )
        if match:
            self.input.click(match.center_x, match.center_y)
            time.sleep(random.uniform(0.3, 0.6))
            return True
        return False

    # ------------------------------------------------------------------
    # Make-X / Make-All interface
    # ------------------------------------------------------------------

    def is_make_interface_open(self, screen: np.ndarray = None) -> bool:
        """Check if a Make-X or Make-All interface is open."""
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return False

        match = self.vision.find_template(
            screen, "interfaces/make_interface.png",
            threshold=0.80,
            region=self.MAKE_X_REGION
        )
        return match is not None

    def click_make_all(self, screen: np.ndarray = None) -> bool:
        """Click the 'Make All' or space bar to confirm Make-X."""
        # Spacebar is the fastest way to confirm Make-All
        self.input.press_key('space')
        time.sleep(random.uniform(0.1, 0.25))
        return True

    def click_make_quantity(self, quantity: int) -> bool:
        """Set a specific quantity in a Make-X dialog."""
        screen = self.capture.capture_full()
        match = self.vision.find_template(
            screen, "interfaces/make_x_qty_box.png",
            threshold=0.78,
            region=self.MAKE_X_REGION
        )
        if match:
            self.input.click(match.center_x, match.center_y)
            time.sleep(random.uniform(0.2, 0.4))
            self.input.type_text(str(quantity))
            time.sleep(random.uniform(0.1, 0.2))
            self.input.press_key('enter')
            return True
        return False

    # ------------------------------------------------------------------
    # Chat / Dialog continuation
    # ------------------------------------------------------------------

    def is_continue_prompt_visible(self, screen: np.ndarray = None) -> bool:
        """Check if 'Click here to continue' is showing in the chatbox."""
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return False

        match = self.vision.find_template(
            screen, "interfaces/click_continue.png",
            threshold=0.78,
            region=tuple(self.chatbox_region)
        )
        return match is not None

    def click_continue(self, screen: np.ndarray = None) -> bool:
        """Click 'Click here to continue' in the chatbox."""
        if screen is None:
            screen = self.capture.capture_full()

        match = self.vision.find_template(
            screen, "interfaces/click_continue.png",
            threshold=0.78,
            region=tuple(self.chatbox_region)
        )
        if match:
            self.input.click(match.center_x, match.center_y)
            time.sleep(random.uniform(0.2, 0.4))
            return True

        # Fallback: click chatbox area
        cx = self.chatbox_region[0] + 200
        cy = self.chatbox_region[1] + 100
        self.input.click(cx + random.randint(-10, 10), cy + random.randint(-5, 5))
        time.sleep(random.uniform(0.2, 0.4))
        return False

    def dismiss_all_dialogs(self, max_clicks: int = 5):
        """Repeatedly dismiss any visible dialogs/continues."""
        for _ in range(max_clicks):
            screen = self.capture.capture_full()
            if self.is_continue_prompt_visible(screen):
                self.click_continue(screen)
                time.sleep(random.uniform(0.25, 0.5))
            elif self.is_level_up_visible(screen):
                self.dismiss_level_up(screen)
                time.sleep(random.uniform(0.25, 0.5))
            else:
                break

    # ------------------------------------------------------------------
    # Tab navigation
    # ------------------------------------------------------------------

    def click_tab(self, tab_name: str):
        """
        Click a game interface tab by name.
        Valid names: combat, stats, quests, inventory, equipment,
                     prayer, magic, clan, friends, account, logout,
                     settings, emotes, music
        """
        region = self.tabs.get(tab_name.lower())
        if not region:
            return

        cx = region[0] + region[2] // 2 + random.randint(-3, 3)
        cy = region[1] + region[3] // 2 + random.randint(-2, 2)
        self.input.click(cx, cy)
        time.sleep(random.uniform(0.15, 0.3))

    # ------------------------------------------------------------------
    # Generic popup / overlay detection
    # ------------------------------------------------------------------

    def has_overlay(self, screen: np.ndarray = None) -> bool:
        """
        Quick check for any modal overlay/popup being visible.
        Returns True if a dialog background is detected center-screen.
        """
        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return False

        h, w = screen.shape[:2]
        center_region = (w // 4, h // 4, w // 2, h // 2)
        rx, ry, rw, rh = center_region
        sample = screen[ry:ry+rh, rx:rx+rw]

        mean_color = sample.mean(axis=(0, 1))  # BGR
        b, g, r = mean_color

        # Dialog background is dark brownish
        return (40 < b < 80) and (30 < g < 70) and (20 < r < 60)
