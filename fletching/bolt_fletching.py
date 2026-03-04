"""Bolt fletching — attaches bolt tips to unfinished bolts."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class BoltState(Enum): BANK=auto(); FLETCH=auto(); WAITING=auto()

BOLT_INFO = {
    "bronze_bolts":  {"tips":"inventory/bronze_bolt_tips.png", "xp":0.5},
    "blurite_bolts": {"tips":"inventory/blurite_bolt_tips.png","xp":1.4},
    "iron_bolts":    {"tips":"inventory/iron_bolt_tips.png",   "xp":1.5},
    "steel_bolts":   {"tips":"inventory/steel_bolt_tips.png",  "xp":3.5},
    "mithril_bolts": {"tips":"inventory/mithril_bolt_tips.png","xp":5.0},
    "adamant_bolts": {"tips":"inventory/adamant_bolt_tips.png","xp":7.0},
    "runite_bolts":  {"tips":"inventory/runite_bolt_tips.png", "xp":10},
    "dragon_bolts":  {"tips":"inventory/dragon_bolt_tips.png", "xp":12},
}

class BoltFletchingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.item          = c.get("item","adamant_bolts")
        self.bank_location = c.get("bank_location","grand_exchange_bank")
        info               = BOLT_INFO.get(self.item, BOLT_INFO["adamant_bolts"])
        self.tips_template = info["tips"]
        self.bolt_template = f"inventory/{self.item}_unf.png"
        self.xp_each       = info["xp"]
        self._state        = BoltState.BANK
        self._made         = 0

    def setup(self):
        self.log(f"Bolt fletching: {self.item}")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == BoltState.BANK:
            if not e.bank.wait_for_open(5):
                e.pathfinder.walk_to_named(self.bank_location, timeout=60)
                e.bank.wait_for_open(8)
            if e.bank.is_open():
                e.bank.deposit_inventory()
                time.sleep(random.uniform(0.3,0.5))
                e.bank.withdraw_item(self.tips_template,"all")
                time.sleep(random.uniform(0.2,0.4))
                e.bank.withdraw_item(self.bolt_template,"all")
                time.sleep(random.uniform(0.3,0.5))
                e.bank.close()
                self._state = BoltState.FLETCH

        elif self._state == BoltState.FLETCH:
            screen = e.screenshot()
            tips = e.inventory.find_item(self.tips_template, screen)
            bolt = e.inventory.find_item(self.bolt_template, screen)
            if not tips or not bolt:
                self._state = BoltState.BANK; return True
            e.inventory.use_item_on_item(tips.index, bolt.index)
            for _ in range(20):
                screen = e.screenshot()
                if e.interfaces.is_make_interface_open(screen):
                    e.interfaces.click_make_all()
                    self._state = BoltState.WAITING
                    self._start = time.time()
                    break
                time.sleep(0.3)

        elif self._state == BoltState.WAITING:
            screen = e.screenshot()
            e.player.update(screen)
            if e.player.is_idle() and e.player.time_idle() > 2:
                self._made += 1
                self.stats.items_gained = self._made
                self.stats.add_xp("fletching", int(10 * self.xp_each))
                self._state = BoltState.BANK
            elif (time.time()-self._start) > 60:
                self._state = BoltState.BANK
            else:
                e.antiban.sleep_action()
        return True

    def get_paint_data(self):
        return {"Script":f"Bolt Fletch ({self.item})","Sets":self._made,"Runtime":self._format_elapsed()}
