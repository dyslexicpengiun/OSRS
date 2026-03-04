"""
Woodcutting Script
Chops trees, handles depletion, and manages inventory.
Supports power-chopping and bank-chopping variants.
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


class WcState(Enum):
    FIND_TREE = auto()
    CHOPPING = auto()
    FULL_INVENTORY = auto()
    DROPPING = auto()
    BANKING = auto()
    WALKING_TO_BANK = auto()
    WALKING_TO_TREES = auto()


TREE_DEFINITIONS = {
    # Each entry: (  [variant_templates, ...],  color_profile  )
    # Multiple variants cover different camera angles / lighting models.
    # find_all_templates() accepts the list directly.
    "normal":   (["objects/trees/tree_normal_1.png",
                  "objects/trees/tree_normal_2.png"],           "tree_leaves"),
    "oak":      (["objects/trees/tree_oak_1.png",
                  "objects/trees/tree_oak_2.png",
                  "objects/trees/tree_oak_3.png"],              "tree_leaves"),
    "willow":   (["objects/trees/tree_willow_1.png",
                  "objects/trees/tree_willow_2.png",
                  "objects/trees/tree_willow_3.png"],           "tree_leaves"),
    "maple":    (["objects/trees/tree_maple_1.png",
                  "objects/trees/tree_maple_2.png",
                  "objects/trees/tree_maple_3.png"],            "tree_leaves"),
    "yew":      (["objects/trees/tree_yew_1.png",
                  "objects/trees/tree_yew_2.png",
                  "objects/trees/tree_yew_3.png"],              "tree_leaves"),
    "magic":    (["objects/trees/tree_magic_1.png",
                  "objects/trees/tree_magic_2.png",
                  "objects/trees/tree_magic_3.png"],            "tree_leaves"),
    "teak":     (["objects/trees/tree_teak_1.png",
                  "objects/trees/tree_teak_2.png"],             "tree_trunk"),
    "mahogany": (["objects/trees/tree_mahogany_1.png",
                  "objects/trees/tree_mahogany_2.png"],         "tree_trunk"),
}


class WoodcuttingScript(BaseScript):
    """
    Chops trees, detects stump/depletion, and handles logs.
    """

    def __init__(self, engine: Engine, script_config: dict = None):
        super().__init__(engine, script_config)
        cfg = self.script_config

        self.tree_type: str = cfg.get("tree_type", "oak")
        self.tree_template, self.tree_color = TREE_DEFINITIONS.get(
            self.tree_type, (["objects/trees/tree_oak_1.png",
                               "objects/trees/tree_oak_2.png",
                               "objects/trees/tree_oak_3.png"], "tree_leaves")
        )

        self.power_chop: bool = cfg.get("power_chop", True)
        self.bank_location: Optional[str] = cfg.get("bank_location", None)
        self.trees_location: Optional[str] = cfg.get("trees_location", None)
        self.search_region: Optional[Tuple] = cfg.get("search_region", None)
        self.detection_threshold: float = cfg.get("detection_threshold", 0.78)

        self._state = WcState.FIND_TREE
        self._trees_chopped: int = 0
        self._last_click_time: float = 0
        self._failed_finds: int = 0

    def setup(self) -> bool:
        self.log(f"Woodcutting script starting. Tree: {self.tree_type}")
        if self.tree_type not in TREE_DEFINITIONS:
            self.log(f"Unknown tree type: {self.tree_type}", "error")
            return False
        self.engine.camera.set_max_pitch()
        time.sleep(random.uniform(0.5, 1.0))
        return True

    def loop(self) -> bool:
        screen = self.engine.screenshot()
        self.log(f"loop() tick — state={self._state.name} "
                 f"screen={'None' if screen is None else f'{screen.shape[1]}x{screen.shape[0]}'}")
        if screen is None:
            time.sleep(1.0)
            return True   # keep running, wait for window

        if self._state == WcState.FIND_TREE:
            return self._find_and_click_tree(screen)
        elif self._state == WcState.CHOPPING:
            return self._wait_for_log(screen)
        elif self._state == WcState.FULL_INVENTORY:
            self._state = WcState.DROPPING if self.power_chop else WcState.WALKING_TO_BANK
        elif self._state == WcState.DROPPING:
            self._drop_logs()
            self._state = WcState.FIND_TREE
        elif self._state == WcState.WALKING_TO_BANK:
            return self._walk_to_bank()
        elif self._state == WcState.BANKING:
            return self._do_banking()
        elif self._state == WcState.WALKING_TO_TREES:
            return self._walk_to_trees()
        return True

    def teardown(self):
        self.log(f"Stopped. Trees chopped: {self._trees_chopped}")

    def get_paint_data(self):
        return {
            "Script": f"Woodcutting ({self.tree_type})",
            "State": self._state.name,
            "Trees Chopped": self._trees_chopped,
            "Logs/hr": f"{self.stats.items_per_hour():.0f}",
            "Runtime": self._format_elapsed(),
        }

    def _find_and_click_tree(self, screen: np.ndarray) -> bool:
        candidates = self.engine.vision.find_all_templates(
            screen, self.tree_template,
            threshold=self.detection_threshold,
            region=self.search_region,
            max_results=8
        )

        # Always log result so we can diagnose detection issues
        if candidates:
            self.log(f"Tree detected: {len(candidates)} candidate(s), "
                     f"best conf={candidates[0].confidence:.2f} at "
                     f"({candidates[0].center_x},{candidates[0].center_y})")
        else:
            self.log(f"No tree detected via template (screen size: "
                     f"{screen.shape[1]}x{screen.shape[0]})", "warning")

        if not candidates:
            # ── Diagnostic: log why template matching failed ──────────────
            # Check whether any template files actually exist yet
            missing = [p for p in self.tree_template
                       if not (self.engine.assets_path / p).exists()]
            if missing and self._failed_finds == 0:
                self.log(
                    f"No template files found for {self.tree_type} trees "
                    f"({len(missing)}/{len(self.tree_template)} missing). "
                    "Capture templates in the Template Capture Tool first, "
                    "or rely on color detection until then.",
                    "warning"
                )

            # ── Color fallback — two passes: configured profile then broad green ──
            color_regions = self.engine.color.find_color_region(
                screen, self.tree_color,
                search_region=self.search_region, min_area=60
            )

            # Broader second pass using a wider green range if first pass found nothing
            if not color_regions:
                color_regions = self.engine.color.find_color_region_hsv(
                    screen,
                    lower_hsv=(25, 25, 25),   # wide green / yellow-green
                    upper_hsv=(95, 255, 180),
                    search_region=self.search_region,
                    min_area=80
                )
                if color_regions and self._failed_finds == 0:
                    self.log(
                        "Using broad green color fallback for tree detection. "
                        "Capture oak templates for reliable clicking.",
                        "warning"
                    )

            if not color_regions:
                self._failed_finds += 1
                if self._failed_finds % 7 == 1:   # log every 7th miss, not just at threshold
                    self.log(
                        f"No trees detected (attempt {self._failed_finds}). "
                        f"Template files missing: {len(missing)}/{len(self.tree_template)}. "
                        "Make sure oak trees are visible on screen.",
                        "warning"
                    )
                if self._failed_finds > 6:
                    self.engine.camera.random_adjustment()
                    time.sleep(random.uniform(2.0, 4.0))
                    self._failed_finds = 0
                else:
                    time.sleep(random.uniform(0.5, 1.2))
                return True

            self._failed_finds = 0
            rx, ry, rw, rh = color_regions[0]
            tree = TemplateMatch(rx, ry, rw, rh, confidence=0.7,
                                 name=self.tree_template[0])
        else:
            tree = candidates[0]

        self._failed_finds = 0
        cx = tree.center_x + random.randint(-10, 10)
        cy = tree.center_y + random.randint(-8, 8)
        self.engine.input.click(cx, cy)
        self._last_click_time = time.time()
        self._state = WcState.CHOPPING

        self.engine.overlay.draw_rect(
            "tree", tree.x, tree.y, tree.width, tree.height,
            color="#00AA44", ttl=10.0
        )
        time.sleep(self.engine.antiban.reaction_delay())
        return True

    def _wait_for_log(self, screen: np.ndarray) -> bool:
        self.engine.inventory.scan(screen)
        if self.engine.inventory.is_full():
            self.log("Inventory full.")
            self.stats.items_gained += 1
            self._trees_chopped += 1
            self._state = WcState.FULL_INVENTORY
            return True

        elapsed = time.time() - self._last_click_time

        # Give the game up to 4s to start the chop animation before we
        # start monitoring for idle — prevents immediate false "idle" on
        # the tick right after clicking.
        if elapsed < 4.0:
            self.engine.antiban.sleep_action()
            return True

        self.engine.player.update(screen)
        if self.engine.player.is_idle():
            if self.engine.player.time_idle() > 2.0:
                self._trees_chopped += 1
                self._state = WcState.FIND_TREE
                return True

        # Hard timeout — if still chopping after 35s something went wrong
        if elapsed > 35.0:
            self.log("Chop timeout — re-finding tree.", "warning")
            self._state = WcState.FIND_TREE
            return True

        self.engine.antiban.sleep_action()
        return True

    def _drop_logs(self):
        screen = self.engine.screenshot()
        self.engine.inventory.scan(screen)
        filled = self.engine.inventory.get_filled_slots()
        for slot in filled:
            self.engine.inventory.drop_item(slot.index)
            time.sleep(random.uniform(0.08, 0.18))
        self.stats.items_gained += len(filled)
        time.sleep(random.uniform(0.3, 0.6))

    def _walk_to_bank(self) -> bool:
        if not self.bank_location:
            # No bank configured — switch to power chop so the inventory gets
            # dropped instead. User can manually bank if they prefer; the
            # script will keep running either way.
            self.log(
                "No bank_location set — switching to power chop mode. "
                "Logs will be dropped. Set bank_location in the GUI to enable banking.",
                "warning"
            )
            self.power_chop = True
            self._state = WcState.DROPPING
            return True

        success = self.engine.pathfinder.walk_to_named(self.bank_location, timeout=90.0)
        if not success:
            self.log(
                f"Could not auto-navigate to '{self.bank_location}'. "
                "Walk to the bank manually — the script will detect when it opens.",
                "warning"
            )
        self._state = WcState.BANKING
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
            self._state = WcState.WALKING_TO_TREES
        return True

    def _walk_to_trees(self) -> bool:
        if self.trees_location:
            success = self.engine.pathfinder.walk_to_named(self.trees_location, timeout=90.0)
            if not success:
                self.log(
                    f"Could not auto-navigate to '{self.trees_location}'. "
                    "Walk back to the trees manually — the script will resume when it sees them.",
                    "warning"
                )
        else:
            self.log(
                "No trees_location set — waiting for you to walk back to the trees.",
                "warning"
            )
            # Poll every 3 s until the player is idle near trees, then proceed.
            # The FIND_TREE state will handle detecting them once we get there.
            time.sleep(3.0)
        self._state = WcState.FIND_TREE
        return True
