"""
Mining Script
Mines ore rocks, handles depletion detection, and manages inventory.
Supports power-mining (drop all) and bank-mining variants.
"""

import time
import random
import logging
from typing import Optional, List, Tuple, Dict
from enum import Enum, auto

import numpy as np

from scripts.base_script import BaseScript
from core.engine import Engine
from core.vision import TemplateMatch
from core.color_detection import ColorDetection

logger = logging.getLogger(__name__)


class MiningState(Enum):
    FIND_ROCK = auto()
    CLICK_ROCK = auto()
    MINING = auto()
    FULL_INVENTORY = auto()
    DROPPING = auto()
    BANKING = auto()
    WALKING_TO_BANK = auto()
    WALKING_TO_ROCKS = auto()


# Ore definitions: template path + color profile name
ORE_DEFINITIONS = {
    # Each entry: (  [variant_templates, ...],  color_profile  )
    # Rocks have 2 models — full and a slightly different angle/lighting variant.
    "tin":      (["objects/rocks/tin_rock_1.png",
                  "objects/rocks/tin_rock_2.png"],          "tin_rock"),
    "copper":   (["objects/rocks/copper_rock_1.png",
                  "objects/rocks/copper_rock_2.png"],       "copper_rock"),
    "iron":     (["objects/rocks/iron_rock_1.png",
                  "objects/rocks/iron_rock_2.png"],         "iron_rock"),
    "coal":     (["objects/rocks/coal_rock_1.png",
                  "objects/rocks/coal_rock_2.png"],         "coal_rock"),
    "mithril":  (["objects/rocks/mithril_rock_1.png",
                  "objects/rocks/mithril_rock_2.png"],      "mithril_rock"),
    "adamant":  (["objects/rocks/adamant_rock_1.png",
                  "objects/rocks/adamant_rock_2.png"],      "adamant_rock"),
    "rune":     (["objects/rocks/rune_rock_1.png",
                  "objects/rocks/rune_rock_2.png"],         "rune_rock"),
}


class MiningScript(BaseScript):
    """
    Mines rocks in a configurable area.
    Handles depletion, inventory management, and optional banking.
    """

    def __init__(self, engine: Engine, script_config: dict = None):
        super().__init__(engine, script_config)

        cfg = self.script_config

        # Ore configuration
        self.ore_type: str = cfg.get("ore_type", "iron")
        self.ore_template, self.ore_color_profile = ORE_DEFINITIONS.get(
            self.ore_type, (["objects/rocks/iron_rock_1.png",
                              "objects/rocks/iron_rock_2.png"], "iron_rock")
        )

        # Rock locations (list of (x, y, w, h) search regions for rocks)
        self.rock_regions: List[Tuple] = cfg.get("rock_regions", [])

        # Mode
        self.power_mine: bool = cfg.get("power_mine", True)
        self.bank_location: Optional[str] = cfg.get("bank_location", None)

        # Detection
        self.detection_threshold: float = cfg.get("detection_threshold", 0.78)
        self.search_region: Optional[Tuple] = cfg.get("search_region", None)

        # Drop settings (power mining)
        self.drop_ore: bool = cfg.get("drop_ore", True)
        self.keep_gems: bool = cfg.get("keep_gems", True)

        # State
        self._state = MiningState.FIND_ROCK
        self._current_rock: Optional[Tuple] = None
        self._rocks_mined: int = 0
        self._last_rock_click_time: float = 0
        self._failed_finds: int = 0

    # ------------------------------------------------------------------
    # BaseScript implementation
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        """Validate configuration and locate starting position."""
        self.log(f"Mining script starting. Ore: {self.ore_type}, Power mine: {self.power_mine}")

        if self.ore_type not in ORE_DEFINITIONS:
            self.log(f"Unknown ore type: {self.ore_type}", "error")
            return False

        # Set camera to a good angle
        self.engine.camera.set_max_pitch()
        time.sleep(random.uniform(0.5, 1.0))

        self.log("Setup complete.")
        return True

    def loop(self) -> bool:
        """One iteration of the mining loop."""
        screen = self.engine.screenshot()
        if screen is None:
            return True

        state = self._state

        if state == MiningState.FIND_ROCK:
            return self._find_and_click_rock(screen)

        elif state == MiningState.MINING:
            return self._wait_for_ore(screen)

        elif state == MiningState.FULL_INVENTORY:
            if self.power_mine:
                self._state = MiningState.DROPPING
            else:
                self._state = MiningState.WALKING_TO_BANK
            return True

        elif state == MiningState.DROPPING:
            self._drop_inventory()
            self._state = MiningState.FIND_ROCK
            return True

        elif state == MiningState.WALKING_TO_BANK:
            return self._walk_to_bank()

        elif state == MiningState.BANKING:
            return self._do_banking()

        elif state == MiningState.WALKING_TO_ROCKS:
            return self._walk_to_rocks()

        return True

    def teardown(self):
        self.log(f"Stopped. Rocks mined: {self._rocks_mined}")

    def get_paint_data(self):
        return {
            "Script": f"Mining ({self.ore_type})",
            "State": self._state.name,
            "Rocks Mined": self._rocks_mined,
            "Ore/hr": f"{self.stats.items_per_hour():.0f}",
            "Runtime": self._format_elapsed(),
        }

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    def _find_and_click_rock(self, screen: np.ndarray) -> bool:
        """Scan for an available rock and click it."""
        rock = self._detect_rock(screen)

        if rock is None:
            self._failed_finds += 1
            if self._failed_finds > 5:
                # Rocks may all be depleted; wait and try camera rotation
                self.log("No rocks found. Waiting for respawn...")
                self.engine.camera.random_adjustment()
                time.sleep(random.uniform(1.5, 3.5))
                self._failed_finds = 0
            else:
                time.sleep(random.uniform(0.5, 1.2))
            return True

        self._failed_finds = 0
        self._current_rock = (rock.x, rock.y, rock.width, rock.height)

        # Click the rock with natural variance
        cx = rock.center_x + random.randint(-8, 8)
        cy = rock.center_y + random.randint(-8, 8)
        self.engine.input.click(cx, cy)
        self._last_rock_click_time = time.time()

        # Brief reaction wait
        time.sleep(self.engine.antiban.reaction_delay())
        self._state = MiningState.MINING

        # Draw on overlay
        self.engine.overlay.draw_rect(
            "current_rock", rock.x, rock.y, rock.width, rock.height,
            color="#FF8800", ttl=10.0
        )
        return True

    def _detect_rock(self, screen: np.ndarray) -> Optional[TemplateMatch]:
        """Find the nearest available (non-depleted) ore rock."""
        candidates = self.engine.vision.find_all_templates(
            screen,
            self.ore_template,
            threshold=self.detection_threshold,
            region=self.search_region,
            max_results=10
        )

        if not candidates:
            # Fallback: color-based detection
            color_regions = self.engine.color.find_color_region(
                screen, self.ore_color_profile,
                search_region=self.search_region,
                min_area=50
            )
            if color_regions:
                rx, ry, rw, rh = color_regions[0]
                return TemplateMatch(rx, ry, rw, rh, confidence=0.7,
                                     name=self.ore_template[0])
            return None

        # Filter out depleted rocks
        valid = []
        for match in candidates:
            rx, ry, rw, rh = match.rect
            if not self.engine.color.is_rock_depleted(screen, (rx, ry, rw, rh)):
                valid.append(match)

        if not valid:
            return None

        # Return the highest-confidence match
        return max(valid, key=lambda m: m.confidence)

    def _wait_for_ore(self, screen: np.ndarray) -> bool:
        """Wait while the player is actively mining."""
        # Check for inventory full
        self.engine.inventory.scan(screen)
        if self.engine.inventory.is_full():
            self.log("Inventory full.")
            self.stats.items_gained += 1
            self._rocks_mined += 1
            self._state = MiningState.FULL_INVENTORY
            return True

        player_state = self.engine.player.update(screen)

        # If idle, rock is likely depleted or we missed the click
        if self.engine.player.is_idle():
            idle_time = self.engine.player.time_idle()
            if idle_time > 2.5:
                self.log("Player idle too long. Rock likely depleted.")
                self._rocks_mined += 1
                self._state = MiningState.FIND_ROCK
                return True

        # Timeout: re-click if we've been waiting too long with no animation
        if (time.time() - self._last_rock_click_time) > 18.0:
            self.log("Mining timeout. Re-clicking.")
            self._state = MiningState.FIND_ROCK
            return True

        # Anti-ban while waiting
        self.engine.antiban.sleep_action()
        return True

    def _drop_inventory(self):
        """Drop all ore from the inventory (power mining)."""
        screen = self.engine.screenshot()
        self.engine.inventory.scan(screen)

        filled = self.engine.inventory.get_filled_slots()
        self.log(f"Dropping {len(filled)} items.")

        for slot in filled:
            self.engine.inventory.drop_item(slot.index)
            time.sleep(random.uniform(0.08, 0.18))

        self.stats.items_gained += len(filled)
        time.sleep(random.uniform(0.3, 0.6))

    def _walk_to_bank(self) -> bool:
        """Navigate to the configured bank location."""
        if not self.bank_location:
            self.log("No bank location configured. Switching to power mine.", "warning")
            self.power_mine = True
            self._state = MiningState.DROPPING
            return True

        self.log(f"Walking to bank: {self.bank_location}")
        success = self.engine.pathfinder.walk_to_named(self.bank_location, timeout=60.0)
        if success:
            self._state = MiningState.BANKING
        else:
            self.log("Failed to reach bank.", "warning")
            time.sleep(2.0)
        return True

    def _do_banking(self) -> bool:
        """Deposit all ore at the bank."""
        if not self.engine.bank.wait_for_open(timeout=6.0):
            self.log("Bank not open. Trying to open it...")
            # Try to find and click nearby bank booth
            screen = self.engine.screenshot()
            booth = self.engine.vision.find_template(
                screen, "objects/bank_booth.png", threshold=0.80
            )
            if booth:
                self.engine.input.right_click(booth.center_x, booth.center_y)
                time.sleep(random.uniform(0.4, 0.7))
                self.engine.interfaces.click_menu_option("Bank")
                self.engine.bank.wait_for_open(timeout=5.0)

        if self.engine.bank.is_open():
            self.engine.bank.deposit_inventory()
            time.sleep(random.uniform(0.5, 1.0))
            self.engine.bank.close()
            self._state = MiningState.WALKING_TO_ROCKS
        else:
            self.log("Could not open bank.", "warning")
            time.sleep(3.0)
        return True

    def _walk_to_rocks(self) -> bool:
        """Return to the mining area after banking."""
        rocks_loc = self.script_config.get("rocks_location", "").strip()
        if rocks_loc:
            self.log(f"Walking back to rocks: {rocks_loc}")
            success = self.engine.pathfinder.walk_to_named(rocks_loc, timeout=90.0)
            if not success:
                self.log(
                    f"Could not auto-navigate to '{rocks_loc}'. "
                    "Walk back to the rocks manually — the script will resume when it sees them.",
                    "warning"
                )
        else:
            self.log(
                "No rocks_location set — waiting for you to walk back to the mining area.",
                "warning"
            )
            # Give the player time to walk back manually before scanning for rocks.
            time.sleep(3.0)

        self._state = MiningState.FIND_ROCK
        return True
