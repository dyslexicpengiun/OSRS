"""
Firemaking Script
Burns logs by using tinderbox on a log in inventory.
Walks in a line, relighting after each log burns.
"""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript

logger = logging.getLogger(__name__)

class FMState(Enum):
    BANK=auto(); WITHDRAW=auto(); LIGHT=auto(); WAITING=auto()

LOG_XP = {
    "normal":40,"oak":60,"willow":90,"teak":105,"maple":135,
    "mahogany":157.5,"yew":202.5,"magic":303.8,"redwood":350,
}

class FiremakingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.log_type        = c.get("log_type", "oak")
        self.log_template    = c.get("log_template", f"inventory/{self.log_type}_log.png")
        self.tinderbox_tmpl  = c.get("tinderbox_template", "inventory/tinderbox.png")
        self.bank_location   = c.get("bank_location", "grand_exchange_bank")
        self._state = FMState.BANK
        self._fires_lit = 0

    def setup(self) -> bool:
        self.log(f"Firemaking: {self.log_type} logs")
        return True

    def loop(self) -> bool:
        e = self.engine
        screen = e.screenshot()

        if self._state == FMState.BANK:
            e.pathfinder.walk_to_named(self.bank_location, timeout=60)
            if not e.bank.wait_for_open(8):
                b = e.vision.find_template(screen, "objects/bank_booth.png", 0.80)
                if b:
                    e.input.right_click(b.center_x, b.center_y)
                    time.sleep(random.uniform(0.3, 0.6))
                    e.interfaces.click_menu_option("Bank")
                    e.bank.wait_for_open(6)
            if e.bank.is_open():
                e.bank.deposit_inventory()
                time.sleep(random.uniform(0.3, 0.5))
                e.bank.withdraw_item(self.tinderbox_tmpl, "1")
                time.sleep(random.uniform(0.2, 0.4))
                e.bank.withdraw_item(self.log_template, "27")
                time.sleep(random.uniform(0.3, 0.5))
                e.bank.close()
                self._state = FMState.LIGHT

        elif self._state == FMState.LIGHT:
            screen = e.screenshot()
            e.inventory.scan(screen)
            tinder = e.inventory.find_item(self.tinderbox_tmpl, screen)
            log    = e.inventory.find_item(self.log_template, screen)
            if not tinder or not log:
                self.log("Missing tinderbox or logs — banking")
                self._state = FMState.BANK
                return True
            # Use tinderbox on log
            e.inventory.click_slot(tinder.index)
            time.sleep(random.uniform(0.1, 0.2))
            e.inventory.click_slot(log.index)
            time.sleep(e.antiban.reaction_delay())
            self._state = FMState.WAITING
            self._light_time = time.time()

        elif self._state == FMState.WAITING:
            screen = e.screenshot()
            e.player.update(screen)
            if e.player.is_idle() and e.player.time_idle() > 1.5:
                e.inventory.scan(screen)
                if e.inventory.count_empty() > 26:
                    # All logs burned
                    logs_burned = 27
                    self._fires_lit += logs_burned
                    self.stats.items_gained = self._fires_lit
                    self.stats.add_xp("firemaking", int(logs_burned * LOG_XP.get(self.log_type, 60)))
                    self._state = FMState.BANK
                else:
                    self._state = FMState.LIGHT
            elif (time.time() - self._light_time) > 8:
                self._state = FMState.LIGHT
            else:
                e.antiban.sleep_action()

        return True

    def get_paint_data(self):
        return {"Script": f"Firemaking ({self.log_type})", "State": self._state.name,
                "Fires Lit": self._fires_lit, "Runtime": self._format_elapsed()}
