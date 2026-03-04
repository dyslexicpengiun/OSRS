"""Anvil Smithing Sub-Script — Smith bars into items at an anvil."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class AnvilState(Enum):
    BANK=auto(); WALK_ANVIL=auto(); SMITH=auto(); WAITING=auto()

ANVIL_ITEMS = {
    "iron_dagger":     {"bar":"iron_bar",    "bars_per":1, "xp":25},
    "iron_sword":      {"bar":"iron_bar",    "bars_per":2, "xp":50},
    "steel_platebody": {"bar":"steel_bar",   "bars_per":5, "xp":187.5},
    "mithril_platebody":{"bar":"mithril_bar","bars_per":5,"xp":250},
    "rune_2h_sword":   {"bar":"rune_bar",    "bars_per":3, "xp":150},
}

class AnvilSmithingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.item          = c.get("item","iron_dagger")
        self.bank_location = c.get("bank_location","varrock_west_bank")
        self.anvil_loc     = c.get("anvil_location","varrock_anvil")
        self._state = AnvilState.BANK
        self._items_made = 0

    def setup(self) -> bool:
        self.log(f"Anvil smithing: {self.item}")
        return True

    def loop(self) -> bool:
        e = self.engine
        screen = e.screenshot()
        info = ANVIL_ITEMS.get(self.item, {"bar":"iron_bar","bars_per":1,"xp":25})

        if self._state == AnvilState.BANK:
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
                e.bank.withdraw_item(f"inventory/{info['bar']}.png","27")
                time.sleep(random.uniform(0.3,0.5))
                e.bank.close()
                self._state = AnvilState.WALK_ANVIL

        elif self._state == AnvilState.WALK_ANVIL:
            e.pathfinder.walk_to_named(self.anvil_loc, timeout=60)
            self._state = AnvilState.SMITH

        elif self._state == AnvilState.SMITH:
            screen = e.screenshot()
            anvil = e.vision.find_template(screen,"objects/anvil.png",0.78)
            if anvil:
                e.input.click(anvil.center_x+random.randint(-5,5),
                               anvil.center_y+random.randint(-5,5))
                for _ in range(25):
                    screen = e.screenshot()
                    if e.interfaces.is_make_interface_open(screen):
                        e.interfaces.click_make_all()
                        self._state = AnvilState.WAITING
                        self._smith_start = time.time()
                        break
                    time.sleep(0.3)
                else:
                    time.sleep(1.5)
            else:
                self.log("Anvil not visible")
                time.sleep(1.5)

        elif self._state == AnvilState.WAITING:
            screen = e.screenshot()
            e.player.update(screen)
            if e.player.is_idle() and e.player.time_idle() > 3:
                e.inventory.scan(screen)
                n = e.inventory.count_empty()
                self._items_made += n
                self.stats.items_gained = self._items_made
                self.stats.add_xp("smithing", int(n * info["xp"]))
                self._state = AnvilState.BANK
            elif (time.time()-self._smith_start)>120:
                self._state = AnvilState.BANK
            else:
                e.antiban.sleep_action()
        return True

    def get_paint_data(self):
        return {"Script":f"Anvil Smith ({self.item})","Items":self._items_made,
                "Runtime":self._format_elapsed()}
