"""Bow fletching — knife on log, Make-All."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class BowState(Enum): BANK=auto(); FLETCH=auto(); WAITING=auto()

BOW_INFO = {
    "arrow_shaft":    {"log":"normal_log",  "xp":5,   "qty_per":15},
    "shortbow_u":     {"log":"normal_log",  "xp":5,   "qty_per":1},
    "longbow_u":      {"log":"normal_log",  "xp":10,  "qty_per":1},
    "oak_shortbow_u": {"log":"oak_log",     "xp":16.5,"qty_per":1},
    "oak_longbow_u":  {"log":"oak_log",     "xp":25,  "qty_per":1},
    "willow_shortbow_u":{"log":"willow_log","xp":33.25,"qty_per":1},
    "willow_longbow_u": {"log":"willow_log","xp":41.5,"qty_per":1},
    "maple_shortbow_u": {"log":"maple_log", "xp":50,  "qty_per":1},
    "maple_longbow_u":  {"log":"maple_log", "xp":58.25,"qty_per":1},
    "yew_shortbow_u":   {"log":"yew_log",   "xp":67.5,"qty_per":1},
    "yew_longbow_u":    {"log":"yew_log",   "xp":75,  "qty_per":1},
    "magic_shortbow_u": {"log":"magic_log", "xp":83.25,"qty_per":1},
    "magic_longbow_u":  {"log":"magic_log", "xp":91.5,"qty_per":1},
}

class BowFletchingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.item          = c.get("item","maple_longbow_u")
        self.bank_location = c.get("bank_location","grand_exchange_bank")
        info               = BOW_INFO.get(self.item, BOW_INFO["maple_longbow_u"])
        self.log_template  = f"inventory/{info['log']}.png"
        self.knife_template= "inventory/knife.png"
        self.xp_each       = info["xp"]
        self._state        = BowState.BANK
        self._made         = 0

    def setup(self):
        self.log(f"Bow fletching: {self.item}")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == BowState.BANK:
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
                e.bank.withdraw_item(self.knife_template,"1")
                time.sleep(random.uniform(0.2,0.4))
                e.bank.withdraw_item(self.log_template,"27")
                time.sleep(random.uniform(0.3,0.5))
                e.bank.close()
                self._state = BowState.FLETCH

        elif self._state == BowState.FLETCH:
            screen = e.screenshot()
            e.inventory.scan(screen)
            knife = e.inventory.find_item(self.knife_template, screen)
            log   = e.inventory.find_item(self.log_template, screen)
            if not knife or not log:
                self._state = BowState.BANK
                return True
            e.inventory.use_item_on_item(knife.index, log.index)
            for _ in range(25):
                screen = e.screenshot()
                if e.interfaces.is_make_interface_open(screen):
                    e.interfaces.click_make_all()
                    self._state = BowState.WAITING
                    self._start_time = time.time()
                    break
                time.sleep(0.3)

        elif self._state == BowState.WAITING:
            screen = e.screenshot()
            e.player.update(screen)
            e.inventory.scan(screen)
            if e.player.is_idle() and e.player.time_idle() > 2:
                n = e.inventory.count_empty()
                self._made += n
                self.stats.items_gained = self._made
                self.stats.add_xp("fletching", int(n * self.xp_each))
                self._state = BowState.BANK
            elif (time.time()-self._start_time) > 90:
                self._state = BowState.BANK
            else:
                e.antiban.sleep_action()
        return True

    def get_paint_data(self):
        return {"Script":f"Bow Fletch ({self.item})","Made":self._made,
                "XP/hr":f"{self.stats.xp_per_hour('fletching'):,.0f}","Runtime":self._format_elapsed()}
