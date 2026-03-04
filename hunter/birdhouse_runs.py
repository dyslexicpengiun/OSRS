"""Birdhouse runs — build birdhouses on Fossil Island, collect every ~50 min."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

LOCATIONS = ["mudskipper_point","verdant_valley","mushroom_forest","the_stranglewood"]
BIRDHOUSE_INFO = {
    "regular":   {"tmpl":"objects/birdhouse_regular.png",  "xp":280},
    "oak":       {"tmpl":"objects/birdhouse_oak.png",      "xp":420},
    "willow":    {"tmpl":"objects/birdhouse_willow.png",   "xp":560},
    "teak":      {"tmpl":"objects/birdhouse_teak.png",     "xp":700},
    "maple":     {"tmpl":"objects/birdhouse_maple.png",    "xp":820},
    "mahogany":  {"tmpl":"objects/birdhouse_mahogany.png", "xp":960},
    "yew":       {"tmpl":"objects/birdhouse_yew.png",      "xp":1020},
    "magic":     {"tmpl":"objects/birdhouse_magic.png",    "xp":1140},
    "redwood":   {"tmpl":"objects/birdhouse_redwood.png",  "xp":1200},
}

class BirdhouseScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.bh_type    = c.get("birdhouse_type","maple")
        info            = BIRDHOUSE_INFO.get(self.bh_type, BIRDHOUSE_INFO["maple"])
        self.bh_tmpl    = info["tmpl"]
        self.xp_each    = info["xp"]
        self.bh_template= f"inventory/{self.bh_type}_birdhouse.png"
        self.seed_tmpl  = "inventory/hop_seeds.png"
        self._runs      = 0
        self._wait_start= 0.0
        self._waiting   = False
        self._RUN_WAIT  = 50 * 60  # 50 minutes

    def setup(self):
        self.log(f"Birdhouse runs: {self.bh_type}")
        return True

    def loop(self):
        e = self.engine
        if self._waiting:
            elapsed = time.time() - self._wait_start
            remaining = self._RUN_WAIT - elapsed
            if remaining > 0:
                self.log(f"Waiting {remaining/60:.1f} min for birdhouses to fill...")
                time.sleep(min(60, remaining))
                return True
            else:
                self._waiting = False

        # Do a run: visit each location, collect + rebuild
        for loc in LOCATIONS:
            e.pathfinder.walk_to_named(loc, timeout=120)
            screen = e.screenshot()
            bh = e.vision.find_template(screen, self.bh_tmpl, 0.78)
            if bh:
                e.input.click(bh.center_x+random.randint(-6,6),
                               bh.center_y+random.randint(-6,6))
                time.sleep(random.uniform(1.0,2.0))
                self._runs += 1
                self.stats.items_gained = self._runs
                self.stats.add_xp("hunter", self.xp_each)
                # Re-place birdhouse
                bh_inv = e.inventory.find_item(self.bh_template, e.screenshot())
                if bh_inv:
                    e.inventory.click_slot(bh_inv.index)
                    time.sleep(random.uniform(0.3,0.6))
                    e.input.click(bh.center_x+random.randint(-6,6),
                                   bh.center_y+random.randint(-6,6))
                    time.sleep(random.uniform(1.5,3.0))
                    # Add seeds
                    seed = e.inventory.find_item(self.seed_tmpl, e.screenshot())
                    if seed:
                        e.inventory.use_item_on_item(seed.index, bh_inv.index)
                        time.sleep(random.uniform(0.5,1.0))
            time.sleep(random.uniform(0.5,1.5))

        self._waiting = True
        self._wait_start = time.time()
        return True

    def get_paint_data(self):
        return {"Script":f"Birdhouses ({self.bh_type})","Runs":self._runs,
                "Runtime":self._format_elapsed()}
