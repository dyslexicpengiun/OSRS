"""
Fishing Script
Finds fishing spots by color/template, clicks them,
waits for inventory fill, and handles banking or power-fishing.
"""

import time
import random
import logging
from typing import Optional, List, Tuple
from enum import Enum, auto

import numpy as np

from scripts.base_script import BaseScript
from core.engine import Engine
from core.vision import TemplateMatch

logger = logging.getLogger(__name__)


class FishingState(Enum):
    FIND_SPOT = auto()
    FISHING = auto()
    FULL_INVENTORY = auto()
    DROPPING = auto()
    BANKING = auto()
    WALKING_TO_BANK = auto()
    WALKING_TO_SPOTS = auto()


FISHING_METHODS = {
    # Each entry: option string + list of spot variant templates.
    # Fishing spots animate between 2-3 frames so multiple variants improve detection.
    "shrimp":    {"option": "Net",      "templates": ["objects/fishing/spot_net_1.png",
                                                       "objects/fishing/spot_net_2.png"]},
    "sardine":   {"option": "Bait",     "templates": ["objects/fishing/spot_bait_1.png",
                                                       "objects/fishing/spot_bait_2.png"]},
    "herring":   {"option": "Bait",     "templates": ["objects/fishing/spot_bait_1.png",
                                                       "objects/fishing/spot_bait_2.png"]},
    "trout":     {"option": "Lure",     "templates": ["objects/fishing/spot_lure_1.png",
                                                       "objects/fishing/spot_lure_2.png"]},
    "salmon":    {"option": "Lure",     "templates": ["objects/fishing/spot_lure_1.png",
                                                       "objects/fishing/spot_lure_2.png"]},
    "lobster":   {"option": "Cage",     "templates": ["objects/fishing/spot_cage_1.png",
                                                       "objects/fishing/spot_cage_2.png"]},
    "swordfish": {"option": "Harpoon",  "templates": ["objects/fishing/spot_harpoon_1.png",
                                                       "objects/fishing/spot_harpoon_2.png"]},
    "tuna":      {"option": "Harpoon",  "templates": ["objects/fishing/spot_harpoon_1.png",
                                                       "objects/fishing/spot_harpoon_2.png"]},
    "shark":     {"option": "Harpoon",  "templates": ["objects/fishing/spot_harpoon_1.png",
                                                       "objects/fishing/spot_harpoon_2.png"]},
    "barbarian": {"option": "Use-rod",  "templates": ["objects/fishing/spot_rod_1.png",
                                                       "objects/fishing/spot_rod_2.png"]},
    "monkfish":  {"option": "Net",      "templates": ["objects/fishing/spot_net_1.png",
                                                       "objects/fishing/spot_net_2.png"]},
    "karambwan": {"option": "Bait",     "templates": ["objects/fishing/spot_bait_1.png",
                                                       "objects/fishing/spot_bait_2.png"]},
}


class FishingScript(BaseScript):
    """
    Fishes at spots detected by the swirling water animation color.
    """

    def __init__(self, engine: Engine, script_config: dict = None):
        super().__init__(engine, script_config)
        cfg = self.script_config

        self.fish_type: str = cfg.get("fish_type", "lobster")
        method_info = FISHING_METHODS.get(self.fish_type, FISHING_METHODS["lobster"])
        self.fishing_option: str = method_info["option"]
        self.spot_templates: list = method_info["templates"]

        self.power_fish: bool = cfg.get("power_fish", True)
        self.bank_location: Optional[str] = cfg.get("bank_location", None)
        self.spots_location: Optional[str] = cfg.get("spots_location", None)
        self.search_region: Optional[Tuple] = cfg.get("search_region", None)

        self._state = FishingState.FIND_SPOT
        self._fish_caught: int = 0
        self._last_click_time: float = 0
        self._current_spot: Optional[Tuple] = None
        self._failed_finds: int = 0

    def setup(self) -> bool:
        self.log(f"Fishing script starting. Fish: {self.fish_type} ({self.fishing_option})")
        if self.fish_type not in FISHING_METHODS:
            self.log(f"Unknown fish type: {self.fish_type}", "error")
            return False
        self.engine.camera.set_max_pitch()
        time.sleep(random.uniform(0.5, 1.0))
        return True

    def loop(self) -> bool:
        screen = self.engine.screenshot()
        if screen is None:
            time.sleep(1.0)
            return True   # keep running, wait for window

        if self._state == FishingState.FIND_SPOT:
            return self._find_and_click_spot(screen)
        elif self._state == FishingState.FISHING:
            return self._wait_for_fish(screen)
        elif self._state == FishingState.FULL_INVENTORY:
            self._state = FishingState.DROPPING if self.power_fish else FishingState.WALKING_TO_BANK
        elif self._state == FishingState.DROPPING:
            self._drop_fish()
            self._state = FishingState.FIND_SPOT
        elif self._state == FishingState.WALKING_TO_BANK:
            return self._walk_to_bank()
        elif self._state == FishingState.BANKING:
            return self._do_banking()
        elif self._state == FishingState.WALKING_TO_SPOTS:
            return self._walk_to_spots()
        return True

    def teardown(self):
        self.log(f"Stopped. Fish caught approx: {self._fish_caught}")

    def get_paint_data(self):
        return {
            "Script": f"Fishing ({self.fish_type})",
            "State": self._state.name,
            "Fish Caught": self._fish_caught,
            "Fish/hr": f"{self.stats.items_per_hour():.0f}",
            "Runtime": self._format_elapsed(),
        }

    def _find_and_click_spot(self, screen: np.ndarray) -> bool:
        """Locate a fishing spot and click it."""
        # Primary: template match across all spot variants
        candidates = self.engine.vision.find_all_templates(
            screen, self.spot_templates,
            threshold=0.78,
            region=self.search_region,
            max_results=6
        )
        spot = candidates[0] if candidates else None

        if spot is None:
            # Fallback: color detection for swirling water
            color_regions = self.engine.color.find_color_region(
                screen, "water_blue",
                search_region=self.search_region, min_area=40
            )
            if not color_regions:
                self._failed_finds += 1
                if self._failed_finds > 8:
                    self.log("No fishing spots found. Rotating camera.")
                    self.engine.camera.random_adjustment()
                    time.sleep(random.uniform(2.0, 5.0))
                    self._failed_finds = 0
                else:
                    time.sleep(random.uniform(0.8, 1.5))
                return True

            rx, ry, rw, rh = color_regions[0]
            spot = TemplateMatch(rx, ry, rw, rh, confidence=0.7,
                                 name=self.spot_templates[0])

        self._failed_finds = 0
        cx = spot.center_x + random.randint(-10, 10)
        cy = spot.center_y + random.randint(-8, 8)

        self.engine.input.click(cx, cy)
        self._last_click_time = time.time()
        self._current_spot = (spot.x, spot.y, spot.width, spot.height)
        self._state = FishingState.FISHING

        self.engine.overlay.draw_rect("fishing_spot", spot.x, spot.y, spot.width, spot.height,
                                       color="#0088FF", ttl=12.0)
        time.sleep(self.engine.antiban.reaction_delay())
        return True

    def _wait_for_fish(self, screen: np.ndarray) -> bool:
        """Wait while actively fishing, detect spot movement/depletion."""
        self.engine.inventory.scan(screen)
        if self.engine.inventory.is_full():
            self.log("Inventory full.")
            self._fish_caught += self.engine.inventory.count_filled()
            self.stats.items_gained = self._fish_caught
            self._state = FishingState.FULL_INVENTORY
            return True

        self.engine.player.update(screen)

        # Spots move occasionally — if player idles, spot has moved
        if self.engine.player.is_idle() and self.engine.player.time_idle() > 3.5:
            self.log("Fishing spot moved. Finding new spot.")
            self._state = FishingState.FIND_SPOT
            return True

        # Timeout
        if (time.time() - self._last_click_time) > 25.0:
            self._state = FishingState.FIND_SPOT
            return True

        # Anti-ban while waiting
        self.engine.antiban.sleep_action()

        # Occasional camera adjustment to look natural
        if self.engine.antiban.should_move_camera():
            self.engine.camera.random_adjustment()

        return True

    def _drop_fish(self):
        screen = self.engine.screenshot()
        self.engine.inventory.scan(screen)
        filled = self.engine.inventory.get_filled_slots()
        for slot in filled:
            self.engine.inventory.drop_item(slot.index)
            time.sleep(random.uniform(0.08, 0.2))
        time.sleep(random.uniform(0.3, 0.6))

    def _walk_to_bank(self) -> bool:
        if not self.bank_location:
            self.power_fish = True
            self._state = FishingState.DROPPING
            return True
        self.engine.pathfinder.walk_to_named(self.bank_location, timeout=60.0)
        self._state = FishingState.BANKING
        return True

    def _do_banking(self) -> bool:
        if not self.engine.bank.wait_for_open(timeout=5.0):
            screen = self.engine.screenshot()
            booth = self.engine.vision.find_template(screen, "objects/bank_booth.png", threshold=0.80)
            if booth:
                self.engine.input.right_click(booth.center_x, booth.center_y)
                time.sleep(random.uniform(0.4, 0.7))
                self.engine.interfaces.click_menu_option("Bank")
                self.engine.bank.wait_for_open(5.0)
        if self.engine.bank.is_open():
            self.engine.bank.deposit_inventory()
            time.sleep(random.uniform(0.4, 0.8))
            self.engine.bank.close()
            self._state = FishingState.WALKING_TO_SPOTS
        return True

    def _walk_to_spots(self) -> bool:
        if self.spots_location:
            self.engine.pathfinder.walk_to_named(self.spots_location, timeout=60.0)
        self._state = FishingState.FIND_SPOT
        return True
