"""Herb cleaning — spam-click grimy herbs in inventory."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class CleanState(Enum): BANK=auto(); CLEAN=auto()

HERB_XP = {
    "guam":2.5,"marrentill":3.8,"tarromin":5,"harralander":6.3,"ranarr":7.5,
    "toadflax":8,"irit":8.8,"avantoe":10,"kwuarm":11.3,"snapdragon":11.8,
    "cadantine":12.5,"lantadyme":13.1,"dwarf_weed":13.8,"torstol":15,
}

class CleaningScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.herb          = c.get("herb","grimy_ranarr")
        self.bank_location = c.get("bank_location","grand_exchange_bank")
        base_name          = self.herb.replace("grimy_","")
        self.xp_each       = HERB_XP.get(base_name, 7.5)
        self.herb_template = f"inventory/{self.herb}.png"
        self._state        = CleanState.BANK
        self._cleaned      = 0

    def setup(self):
        self.log(f"Cleaning: {self.herb}")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == CleanState.BANK:
            if not e.bank.wait_for_open(5):
                e.pathfinder.walk_to_named(self.bank_location, timeout=60)
                e.bank.wait_for_open(8)
            if e.bank.is_open():
                e.bank.deposit_inventory()
                time.sleep(random.uniform(0.3,0.5))
                e.bank.withdraw_item(self.herb_template,"28")
                time.sleep(random.uniform(0.3,0.5))
                e.bank.close()
                self._state = CleanState.CLEAN

        elif self._state == CleanState.CLEAN:
            screen = e.screenshot()
            e.inventory.scan(screen)
            herbs = e.inventory.find_all_items(self.herb_template, screen)
            if not herbs:
                self._state = CleanState.BANK; return True
            # Click every herb rapidly
            for slot in herbs:
                e.inventory.click_slot(slot.index, variance=3)
                time.sleep(random.uniform(0.04, 0.09))
                self._cleaned += 1
                self.stats.items_gained = self._cleaned
                self.stats.add_xp("herblore", self.xp_each)
            time.sleep(random.uniform(0.1, 0.2))
            self._state = CleanState.BANK
        return True

    def get_paint_data(self):
        return {"Script":f"Cleaning ({self.herb})","Cleaned":self._cleaned,
                "XP/hr":f"{self.stats.xp_per_hour('herblore'):,.0f}","Runtime":self._format_elapsed()}
