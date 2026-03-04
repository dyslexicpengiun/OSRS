"""Tree run — check/chop/replant tree patches across Gielinor."""
import time, random, logging
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

TREE_PATCHES = [
    {"name":"Lumbridge",    "location":"lumbridge_farm",    "template":"objects/farming/tree_patch.png"},
    {"name":"Varrock",      "location":"varrock_palace",    "template":"objects/farming/tree_patch.png"},
    {"name":"Falador",      "location":"falador_farm",      "template":"objects/farming/tree_patch.png"},
    {"name":"Taverley",     "location":"taverley_farm",     "template":"objects/farming/tree_patch.png"},
    {"name":"Gnome Stronghold","location":"gnome_stronghold","template":"objects/farming/tree_patch.png"},
]

TREE_XP = {
    "oak_sapling":467.5,"willow_sapling":1456.3,"maple_sapling":3448.4,
    "yew_sapling":7150,"magic_sapling":13768.3,"redwood_sapling":22450,
}

class TreeRunScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.seed       = c.get("seed","yew_sapling")
        self.seed_tmpl  = f"inventory/{self.seed}.png"
        self.xp_plant   = TREE_XP.get(self.seed, 7150)
        self._runs      = 0
        self._WAIT      = 7 * 3600  # trees ~7 hours
        self._wait_start= 0.0
        self._waiting   = False

    def setup(self):
        self.log(f"Tree runs: {self.seed}")
        return True

    def loop(self):
        e = self.engine
        if self._waiting:
            elapsed = time.time() - self._wait_start
            if elapsed < self._WAIT:
                time.sleep(min(300, self._WAIT - elapsed)); return True
            self._waiting = False

        for patch in TREE_PATCHES:
            e.pathfinder.walk_to_named(patch["location"], timeout=120)
            screen = e.screenshot()
            obj = e.vision.find_template(screen, patch["template"], 0.78)
            if not obj: continue

            # Check tree (right-click)
            e.input.right_click(obj.center_x, obj.center_y)
            time.sleep(random.uniform(0.3,0.55))
            # Chop if grown, or pay farmer to chop
            if not e.interfaces.click_menu_option("Chop down"):
                e.interfaces.click_menu_option("Pay farmer")
            e.player.wait_until_idle(timeout=20)

            # Replant
            screen = e.screenshot()
            seed = e.inventory.find_item(self.seed_tmpl, screen)
            if seed:
                e.input.right_click(obj.center_x, obj.center_y)
                time.sleep(random.uniform(0.3,0.55))
                e.interfaces.click_menu_option("Plant")
                e.player.wait_until_idle(timeout=10)
                self.stats.add_xp("farming", self.xp_plant)
            time.sleep(random.uniform(0.5,1.5))

        self._runs += 1
        self.stats.items_gained = self._runs
        self._waiting = True
        self._wait_start = time.time()
        return True

    def get_paint_data(self):
        return {"Script":f"Tree Runs ({self.seed.replace('_sapling','')})","Runs":self._runs,
                "Runtime":self._format_elapsed()}
