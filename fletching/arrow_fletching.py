"""Arrow fletching sub-script."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class ArrowState(Enum): BANK=auto(); FLETCH=auto(); WAITING=auto()

ARROW_INFO = {
    "bronze_arrow":  {"head":"inventory/bronze_arrowhead.png", "xp":12.5},
    "iron_arrow":    {"head":"inventory/iron_arrowhead.png",   "xp":25},
    "steel_arrow":   {"head":"inventory/steel_arrowhead.png",  "xp":37.5},
    "mithril_arrow": {"head":"inventory/mithril_arrowhead.png","xp":50},
    "adamant_arrow": {"head":"inventory/adamant_arrowhead.png","xp":62.5},
    "rune_arrow":    {"head":"inventory/rune_arrowhead.png",   "xp":75},
    "dragon_arrow":  {"head":"inventory/dragon_arrowhead.png", "xp":112.5},
}

class ArrowFletchingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.item          = c.get("item","rune_arrow")
        self.bank_location = c.get("bank_location","grand_exchange_bank")
        info               = ARROW_INFO.get(self.item, ARROW_INFO["rune_arrow"])
        self.head_template = info["head"]
        self.shaft_template= "inventory/arrow_shaft.png"
        self.feather_template="inventory/feather.png"
        self.xp_each       = info["xp"]
        self._state        = ArrowState.BANK
        self._made         = 0

    def setup(self):
        self.log(f"Arrow fletching: {self.item}")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == ArrowState.BANK:
            if not e.bank.wait_for_open(5):
                e.pathfinder.walk_to_named(self.bank_location, timeout=60)
                e.bank.wait_for_open(8)
            if e.bank.is_open():
                e.bank.deposit_inventory()
                time.sleep(random.uniform(0.3,0.5))
                e.bank.withdraw_item(self.head_template,"all")
                time.sleep(random.uniform(0.2,0.4))
                e.bank.withdraw_item(self.shaft_template,"all")
                time.sleep(random.uniform(0.3,0.5))
                e.bank.close()
                self._state = ArrowState.FLETCH

        elif self._state == ArrowState.FLETCH:
            screen = e.screenshot()
            e.inventory.scan(screen)
            head  = e.inventory.find_item(self.head_template, screen)
            shaft = e.inventory.find_item(self.shaft_template, screen)
            if not head or not shaft:
                self._state = ArrowState.BANK
                return True
            e.inventory.use_item_on_item(head.index, shaft.index)
            for _ in range(20):
                screen = e.screenshot()
                if e.interfaces.is_make_interface_open(screen):
                    e.interfaces.click_make_all()
                    self._state = ArrowState.WAITING
                    self._start = time.time()
                    break
                time.sleep(0.3)

        elif self._state == ArrowState.WAITING:
            screen = e.screenshot()
            e.player.update(screen)
            if e.player.is_idle() and e.player.time_idle() > 2:
                self._made += 1
                self.stats.items_gained = self._made
                self.stats.add_xp("fletching", int(10 * self.xp_each))
                self._state = ArrowState.BANK
            elif (time.time()-self._start) > 60:
                self._state = ArrowState.BANK
            else:
                e.antiban.sleep_action()
        return True

    def get_paint_data(self):
        return {"Script":f"Arrow Fletch ({self.item})","Sets":self._made,
                "XP/hr":f"{self.stats.xp_per_hour('fletching'):,.0f}","Runtime":self._format_elapsed()}
