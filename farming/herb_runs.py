"""Herb run — harvest herbs, compost, replant across all herb patches."""
import time, random, logging
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

HERB_PATCHES = [
    {"name":"Falador",        "location":"falador_farm",    "patch_template":"objects/farming/herb_patch.png"},
    {"name":"Ardougne",       "location":"ardougne_farm",   "patch_template":"objects/farming/herb_patch.png"},
    {"name":"Catherby",       "location":"catherby_farm",   "patch_template":"objects/farming/herb_patch.png"},
    {"name":"Canifis",        "location":"canifis_farm",    "patch_template":"objects/farming/herb_patch.png"},
    {"name":"Hosidius",       "location":"hosidius_farm",   "patch_template":"objects/farming/herb_patch_h.png"},
    {"name":"Farming Guild",  "location":"farming_guild",   "patch_template":"objects/farming/herb_patch.png"},
    {"name":"Harmony Island", "location":"harmony_island",  "patch_template":"objects/farming/herb_patch.png"},
    {"name":"Weiss",          "location":"weiss_farm",      "patch_template":"objects/farming/herb_patch.png"},
    {"name":"Troll Stronghold","location":"troll_stronghold","patch_template":"objects/farming/herb_patch.png"},
]

HERB_SEEDS = {
    "guam":6.5,"marrentill":8.5,"tarromin":10.5,"harralander":12.5,
    "ranarr":27,"toadflax":34,"irit":43,"avantoe":54.5,"kwuarm":69,
    "snapdragon":98.5,"cadantine":106.5,"lantadyme":134.5,"dwarf_weed":170.5,"torstol":199.5,
}

class HerbRunScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.seed         = c.get("seed","ranarr_seed")
        self.use_compost  = c.get("use_compost",True)
        self.compost_type = c.get("compost","ultracompost")
        herb_name         = self.seed.replace("_seed","")
        self.seed_tmpl    = f"inventory/{self.seed}.png"
        self.xp_plant     = HERB_SEEDS.get(herb_name, 27)
        self._runs        = 0
        self._WAIT        = 80 * 60  # herbs take ~80 min
        self._wait_start  = 0.0
        self._waiting     = False

    def setup(self):
        self.log(f"Herb runs: {self.seed}")
        return True

    def loop(self):
        e = self.engine
        if self._waiting:
            elapsed = time.time() - self._wait_start
            remaining = self._WAIT - elapsed
            if remaining > 0:
                time.sleep(min(60, remaining)); return True
            self._waiting = False

        for patch in HERB_PATCHES:
            e.pathfinder.walk_to_named(patch["location"], timeout=120)
            screen = e.screenshot()
            obj = e.vision.find_template(screen, patch["patch_template"], 0.78)
            if not obj:
                self.log(f"Patch not found at {patch['name']}")
                continue

            # Harvest
            e.input.right_click(obj.center_x+random.randint(-8,8),
                                  obj.center_y+random.randint(-8,8))
            time.sleep(random.uniform(0.3,0.55))
            e.interfaces.click_menu_option("Harvest")
            e.player.wait_until_idle(timeout=15)
            time.sleep(random.uniform(0.5,1.0))

            # Compost
            if self.use_compost:
                screen = e.screenshot()
                comp = e.inventory.find_item(f"inventory/{self.compost_type}.png", screen)
                if comp:
                    e.inventory.use_item_on_item(comp.index, 0)  # use on patch

            # Plant
            screen = e.screenshot()
            seed = e.inventory.find_item(self.seed_tmpl, screen)
            if seed:
                e.input.right_click(obj.center_x+random.randint(-5,5),
                                     obj.center_y+random.randint(-5,5))
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
        return {"Script":f"Herb Runs ({self.seed.replace('_seed','')})","Runs":self._runs,
                "XP/hr":f"{self.stats.xp_per_hour('farming'):,.0f}","Runtime":self._format_elapsed()}
