"""
Smelting Sub-Script
Smelt ores into bars at a furnace using Make-All.
"""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript

logger = logging.getLogger(__name__)

class SmeltState(Enum):
    BANK=auto(); WALK_FURNACE=auto(); CLICK_FURNACE=auto(); SMELTING=auto()

BAR_INFO = {
    "bronze_bar": {"ores": ["copper_ore","tin_ore"],  "xp": 6.25},
    "iron_bar":   {"ores": ["iron_ore"],              "xp": 12.5},
    "steel_bar":  {"ores": ["iron_ore","coal"],       "xp": 17.5},
    "gold_bar":   {"ores": ["gold_ore"],              "xp": 22.5},
    "mithril_bar":{"ores": ["mithril_ore","coal"],    "xp": 30.0},
    "adamant_bar":{"ores": ["adamantite_ore","coal"], "xp": 37.5},
    "rune_bar":   {"ores": ["runite_ore","coal"],     "xp": 50.0},
}

class SmeltingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.item          = c.get("item", "iron_bar")
        self.bank_location = c.get("bank_location", "edgeville_bank")
        self.furnace_loc   = c.get("furnace_location", "edgeville_furnace")
        self._state = SmeltState.BANK
        self._bars = 0

    def setup(self) -> bool:
        self.log(f"Smelting: {self.item}")
        return True

    def loop(self) -> bool:
        e = self.engine
        screen = e.screenshot()

        if self._state == SmeltState.BANK:
            e.pathfinder.walk_to_named(self.bank_location, timeout=60)
            if not e.bank.wait_for_open(8):
                b = e.vision.find_template(screen,"objects/bank_booth.png",0.80)
                if b:
                    e.input.right_click(b.center_x, b.center_y)
                    time.sleep(random.uniform(0.3,0.6))
                    e.interfaces.click_menu_option("Bank")
                    e.bank.wait_for_open(6)
            if e.bank.is_open():
                e.bank.deposit_inventory()
                time.sleep(random.uniform(0.3,0.5))
                info = BAR_INFO.get(self.item, {})
                for ore in info.get("ores", []):
                    e.bank.withdraw_item(f"inventory/{ore}.png", "all")
                    time.sleep(random.uniform(0.2,0.4))
                e.bank.close()
                self._state = SmeltState.WALK_FURNACE

        elif self._state == SmeltState.WALK_FURNACE:
            e.pathfinder.walk_to_named(self.furnace_loc, timeout=60)
            self._state = SmeltState.CLICK_FURNACE

        elif self._state == SmeltState.CLICK_FURNACE:
            screen = e.screenshot()
            furnace = e.vision.find_template(screen,"objects/furnace.png",0.78)
            if furnace:
                e.input.click(furnace.center_x + random.randint(-6,6),
                               furnace.center_y + random.randint(-6,6))
                for _ in range(25):
                    screen = e.screenshot()
                    if e.interfaces.is_make_interface_open(screen):
                        e.interfaces.click_make_all()
                        self._state = SmeltState.SMELTING
                        self._smelt_start = time.time()
                        break
                    time.sleep(0.3)
                else:
                    time.sleep(1)
            else:
                self.log("Furnace not found")
                time.sleep(1.5)

        elif self._state == SmeltState.SMELTING:
            screen = e.screenshot()
            e.player.update(screen)
            e.inventory.scan(screen)
            if e.inventory.is_empty() or (e.player.is_idle() and e.player.time_idle()>3):
                bars = e.inventory.count_empty()
                self._bars += bars
                self.stats.items_gained = self._bars
                xp_each = BAR_INFO.get(self.item,{}).get("xp",12.5)
                self.stats.add_xp("smithing", int(bars * xp_each))
                self._state = SmeltState.BANK
            elif (time.time()-self._smelt_start)>120:
                self._state = SmeltState.BANK
            else:
                e.antiban.sleep_action()
        return True

    def get_paint_data(self):
        return {"Script":f"Smelting ({self.item})","State":self._state.name,
                "Bars":self._bars,"Bars/hr":f"{self.stats.items_per_hour():.0f}",
                "Runtime":self._format_elapsed()}
