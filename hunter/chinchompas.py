"""Box trap hunter — places traps, collects catches, resets fallen traps."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class TrapState(Enum): PLACE_TRAPS=auto(); WATCH=auto(); COLLECT=auto()

CHINCHOMPA_INFO = {
    "grey":   {"location":"piscatoris","xp":198.4,"trap_template":"objects/box_trap_set.png"},
    "red":    {"location":"feldip_hills","xp":265,"trap_template":"objects/box_trap_set.png"},
    "black":  {"location":"elf_land","xp":315,"trap_template":"objects/box_trap_set.png"},
}

class ChinchompaScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.chin_type   = c.get("chin_type","grey")
        info             = CHINCHOMPA_INFO.get(self.chin_type, CHINCHOMPA_INFO["grey"])
        self.location    = c.get("location", info["location"])
        self.xp_catch    = info["xp"]
        self.trap_tmpl   = info["trap_template"]
        self.trap_tmpl_caught = "objects/box_trap_caught.png"
        self.trap_tmpl_failed = "objects/box_trap_failed.png"
        self.box_template= "inventory/box_trap.png"
        self.max_traps   = c.get("max_traps", 4)
        self._state      = TrapState.PLACE_TRAPS
        self._caught     = 0

    def setup(self):
        self.log(f"Chin trapping: {self.chin_type}")
        e = self.engine
        e.pathfinder.walk_to_named(self.location, timeout=120)
        e.camera.set_max_pitch()
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == TrapState.PLACE_TRAPS:
            traps_placed = len(e.vision.find_all_templates(screen, self.trap_tmpl, 0.75))
            if traps_placed >= self.max_traps:
                self._state = TrapState.WATCH
                return True
            # Place a box trap at cursor position
            box = e.inventory.find_item(self.box_template, screen)
            if box:
                e.inventory.click_slot(box.index)
                time.sleep(random.uniform(0.3,0.6))
                # Click a ground position near player
                cx = 960 + random.randint(-80,80)
                cy = 540 + random.randint(-50,50)
                e.input.click(cx, cy)
                time.sleep(random.uniform(0.8,1.5))
            else:
                self.log("No box traps in inventory")
                return False

        elif self._state == TrapState.WATCH:
            # Check for caught or failed traps
            caught = e.vision.find_all_templates(screen, self.trap_tmpl_caught, 0.75)
            failed = e.vision.find_all_templates(screen, self.trap_tmpl_failed, 0.75)
            if caught or failed:
                self._state = TrapState.COLLECT
            else:
                e.antiban.sleep_action()
                if e.antiban.should_move_camera():
                    e.camera.random_adjustment()

        elif self._state == TrapState.COLLECT:
            screen = e.screenshot()
            for match in e.vision.find_all_templates(screen, self.trap_tmpl_caught, 0.75):
                e.input.click(match.center_x+random.randint(-5,5),
                               match.center_y+random.randint(-5,5))
                time.sleep(random.uniform(0.6,1.0))
                self._caught += 1
                self.stats.items_gained = self._caught
                self.stats.add_xp("hunter", self.xp_catch)
            # Reset failed
            for match in e.vision.find_all_templates(screen, self.trap_tmpl_failed, 0.75):
                e.input.click(match.center_x+random.randint(-5,5),
                               match.center_y+random.randint(-5,5))
                time.sleep(random.uniform(0.6,1.0))
            self._state = TrapState.PLACE_TRAPS
        return True

    def get_paint_data(self):
        return {"Script":f"Chinchompas ({self.chin_type})","Caught":self._caught,
                "XP/hr":f"{self.stats.xp_per_hour('hunter'):,.0f}","Runtime":self._format_elapsed()}
