"""
Cooking Script
Cooks food on a range/fire. Bank → cook cycle.
Detects the Make-All interface and waits for cooking to finish.
"""
import time, random, logging
from enum import Enum, auto
from typing import Optional
from scripts.base_script import BaseScript

logger = logging.getLogger(__name__)

class CookState(Enum):
    WALK_TO_BANK=auto(); BANK=auto(); WALK_TO_RANGE=auto()
    CLICK_RANGE=auto(); COOK=auto(); WAITING=auto()

FOOD_XP = {
    "shrimp":8,"sardine":40,"herring":50,"mackerel":60,"trout":70,
    "cod":75,"pike":80,"salmon":90,"tuna":100,"lobster":120,
    "bass":130,"swordfish":140,"monkfish":150,"shark":210,
    "anglerfish":230,"dark_crab":215,
}

class CookingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.food_item      = c.get("food_item", "lobster")
        self.food_template  = c.get("food_template", f"inventory/{self.food_item}.png")
        self.range_template = c.get("range_template", "objects/range.png")
        self.cooking_method = c.get("cooking_method", "range")
        self.bank_location  = c.get("bank_location", "al_kharid_bank")
        self.cook_location  = c.get("cook_location", "al_kharid_range")
        self._state = CookState.WALK_TO_BANK
        self._cooked = 0
        self._cook_start = 0.0

    def setup(self) -> bool:
        self.log(f"Cooking: {self.food_item} on {self.cooking_method}")
        self.engine.camera.set_max_pitch()
        return True

    def loop(self) -> bool:
        screen = self.engine.screenshot()
        e = self.engine

        if self._state == CookState.WALK_TO_BANK:
            e.pathfinder.walk_to_named(self.bank_location, timeout=60)
            self._state = CookState.BANK

        elif self._state == CookState.BANK:
            if not e.bank.wait_for_open(8):
                screen = e.screenshot()
                booth = e.vision.find_template(screen, "objects/bank_booth.png", 0.80)
                if booth:
                    e.input.right_click(booth.center_x, booth.center_y)
                    time.sleep(random.uniform(0.35, 0.6))
                    e.interfaces.click_menu_option("Bank")
                    e.bank.wait_for_open(6)
            if e.bank.is_open():
                e.bank.deposit_inventory()
                time.sleep(random.uniform(0.4, 0.7))
                e.bank.withdraw_item(self.food_template, "28")
                time.sleep(random.uniform(0.4, 0.7))
                e.bank.close()
                self._state = CookState.WALK_TO_RANGE
            else:
                time.sleep(2)

        elif self._state == CookState.WALK_TO_RANGE:
            e.pathfinder.walk_to_named(self.cook_location, timeout=60)
            self._state = CookState.CLICK_RANGE

        elif self._state == CookState.CLICK_RANGE:
            screen = e.screenshot()
            obj = e.vision.find_template(screen, self.range_template, 0.78)
            if obj:
                e.input.click(obj.center_x + random.randint(-5,5),
                               obj.center_y + random.randint(-5,5))
                time.sleep(e.antiban.reaction_delay())
                # Wait for Make-All interface
                for _ in range(20):
                    screen = e.screenshot()
                    if e.interfaces.is_make_interface_open(screen):
                        e.interfaces.click_make_all()
                        self._state = CookState.WAITING
                        self._cook_start = time.time()
                        break
                    time.sleep(0.3)
                else:
                    self.log("Make interface not found, retrying")
            else:
                self.log("Range not found")
                time.sleep(1.5)

        elif self._state == CookState.WAITING:
            e.player.update(screen)
            e.inventory.scan(screen)
            if e.inventory.is_empty():
                self._cooked += 28
                self.stats.items_gained = self._cooked
                xp_each = FOOD_XP.get(self.food_item, 100)
                self.stats.add_xp("cooking", 28 * xp_each)
                self._state = CookState.WALK_TO_BANK
            elif (time.time() - self._cook_start) > 120:
                self.log("Cooking timeout")
                self._state = CookState.WALK_TO_BANK
            else:
                e.antiban.sleep_action()

        return True

    def get_paint_data(self):
        return {"Script": f"Cooking ({self.food_item})", "State": self._state.name,
                "Cooked": self._cooked, "Cooked/hr": f"{self.stats.items_per_hour():.0f}",
                "Runtime": self._format_elapsed()}
