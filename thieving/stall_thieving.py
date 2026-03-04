"""Stall thieving sub-script."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class StallState(Enum): FIND_STALL=auto(); STEAL=auto(); DROP=auto()

STALL_INFO = {
    "bakers_stall":   {"template":"objects/stalls/baker_stall.png",   "xp":16},
    "tea_stall":      {"template":"objects/stalls/tea_stall.png",      "xp":16},
    "silk_stall":     {"template":"objects/stalls/silk_stall.png",     "xp":24},
    "wine_stall":     {"template":"objects/stalls/wine_stall.png",     "xp":27},
    "fruit_stall":    {"template":"objects/stalls/fruit_stall.png",    "xp":36},
    "gem_stall":      {"template":"objects/stalls/gem_stall.png",      "xp":160},
    "fur_stall":      {"template":"objects/stalls/fur_stall.png",      "xp":36},
    "magic_stall":    {"template":"objects/stalls/magic_stall.png",    "xp":100},
    "spice_stall":    {"template":"objects/stalls/spice_stall.png",    "xp":81},
    "scimitar_stall": {"template":"objects/stalls/scimitar_stall.png", "xp":160},
}

class StallThievingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.target   = c.get("target","fruit_stall")
        self.info     = STALL_INFO.get(self.target, STALL_INFO["fruit_stall"])
        self._state   = StallState.FIND_STALL
        self._stolen  = 0

    def setup(self):
        self.log(f"Stall thieving: {self.target}")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == StallState.FIND_STALL:
            match = e.vision.find_template(screen, self.info["template"], 0.78)
            if match:
                e.input.click(match.center_x+random.randint(-8,8),
                               match.center_y+random.randint(-8,8))
                time.sleep(e.antiban.reaction_delay())
                self._state = StallState.STEAL
                self._steal_time = time.time()
            else:
                time.sleep(0.8)

        elif self._state == StallState.STEAL:
            e.player.update(screen)
            if e.player.is_idle() and e.player.time_idle() > 0.5:
                self._stolen += 1
                self.stats.items_gained = self._stolen
                self.stats.add_xp("thieving", self.info["xp"])
                e.inventory.scan(screen)
                if e.inventory.is_full():
                    self._state = StallState.DROP
                else:
                    self._state = StallState.FIND_STALL
                    time.sleep(random.uniform(0.5, 1.2))  # stall cooldown
            elif (time.time()-self._steal_time) > 5:
                self._state = StallState.FIND_STALL
            else:
                e.antiban.sleep_action()

        elif self._state == StallState.DROP:
            e.inventory.drop_all_items()
            self._state = StallState.FIND_STALL
        return True

    def get_paint_data(self):
        return {"Script":f"Stall ({self.target})","Stolen":self._stolen,
                "XP/hr":f"{self.stats.xp_per_hour('thieving'):,.0f}","Runtime":self._format_elapsed()}
