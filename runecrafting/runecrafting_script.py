"""
Runecrafting Script
Uses essence pouch support. Runs: bank → fill pouches → use rune essence on altar → repeat.
"""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class RCState(Enum):
    BANK=auto(); WALK_ALTAR=auto(); CRAFT=auto(); WALK_BANK=auto()

ALTAR_INFO = {
    "air":    {"xp_per_ess":5,    "altar_template":"objects/altars/air_altar.png",    "ruins_template":"objects/altars/air_ruins.png"},
    "mind":   {"xp_per_ess":5.5,  "altar_template":"objects/altars/mind_altar.png",   "ruins_template":"objects/altars/mind_ruins.png"},
    "water":  {"xp_per_ess":6,    "altar_template":"objects/altars/water_altar.png",  "ruins_template":"objects/altars/water_ruins.png"},
    "earth":  {"xp_per_ess":6.5,  "altar_template":"objects/altars/earth_altar.png",  "ruins_template":"objects/altars/earth_ruins.png"},
    "fire":   {"xp_per_ess":7,    "altar_template":"objects/altars/fire_altar.png",   "ruins_template":"objects/altars/fire_ruins.png"},
    "body":   {"xp_per_ess":7.5,  "altar_template":"objects/altars/body_altar.png",   "ruins_template":"objects/altars/body_ruins.png"},
    "cosmic": {"xp_per_ess":8,    "altar_template":"objects/altars/cosmic_altar.png", "ruins_template":"objects/altars/cosmic_ruins.png"},
    "chaos":  {"xp_per_ess":8.5,  "altar_template":"objects/altars/chaos_altar.png",  "ruins_template":"objects/altars/chaos_ruins.png"},
    "nature": {"xp_per_ess":9,    "altar_template":"objects/altars/nature_altar.png", "ruins_template":"objects/altars/nature_ruins.png"},
    "law":    {"xp_per_ess":9.5,  "altar_template":"objects/altars/law_altar.png",    "ruins_template":"objects/altars/law_ruins.png"},
    "death":  {"xp_per_ess":10,   "altar_template":"objects/altars/death_altar.png",  "ruins_template":"objects/altars/death_ruins.png"},
    "blood":  {"xp_per_ess":10.5, "altar_template":"objects/altars/blood_altar.png",  "ruins_template":"objects/altars/blood_ruins.png"},
}

class RunecraftingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.altar         = c.get("altar","nature")
        self.use_pouches   = c.get("use_pouches",True)
        self.bank_location = c.get("bank_location","castle_wars_bank")
        info               = ALTAR_INFO.get(self.altar, ALTAR_INFO["nature"])
        self.xp_per_ess    = info["xp_per_ess"]
        self.altar_tmpl    = info["altar_template"]
        self.ruins_tmpl    = info["ruins_template"]
        self.ess_tmpl      = "inventory/pure_essence.png"
        self.talisman_tmpl = f"inventory/{self.altar}_talisman.png"
        self._state        = RCState.BANK
        self._runes_made   = 0

    def setup(self):
        self.log(f"Runecrafting: {self.altar} runes")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == RCState.BANK:
            if not e.bank.wait_for_open(5):
                e.pathfinder.walk_to_named(self.bank_location, timeout=60)
                e.bank.wait_for_open(8)
            if e.bank.is_open():
                e.bank.deposit_inventory()
                time.sleep(random.uniform(0.3,0.5))
                e.bank.withdraw_item(self.ess_tmpl,"all")
                if self.use_pouches:
                    for p in ["inventory/small_pouch.png","inventory/medium_pouch.png",
                               "inventory/large_pouch.png","inventory/giant_pouch.png"]:
                        e.bank.withdraw_item(p,"1")
                        time.sleep(random.uniform(0.15,0.3))
                e.bank.close()
                self._state = RCState.WALK_ALTAR

        elif self._state == RCState.WALK_ALTAR:
            e.pathfinder.walk_to_named(f"{self.altar}_altar", timeout=90)
            self._state = RCState.CRAFT

        elif self._state == RCState.CRAFT:
            screen = e.screenshot()
            # Click on altar
            altar_obj = e.vision.find_template(screen, self.altar_tmpl, 0.78)
            if not altar_obj:
                altar_obj = e.vision.find_template(screen, self.ruins_tmpl, 0.78)
            if altar_obj:
                e.input.click(altar_obj.center_x+random.randint(-8,8),
                               altar_obj.center_y+random.randint(-8,8))
                e.player.wait_until_idle(timeout=12)
                time.sleep(random.uniform(0.3,0.6))
                # Empty pouches if used
                if self.use_pouches:
                    screen = e.screenshot()
                    for p in ["inventory/small_pouch.png","inventory/medium_pouch.png",
                               "inventory/large_pouch.png","inventory/giant_pouch.png"]:
                        slot = e.inventory.find_item(p, screen)
                        if slot:
                            e.input.right_click(slot.center[0], slot.center[1])
                            time.sleep(random.uniform(0.25,0.45))
                            e.interfaces.click_menu_option("Empty")
                    # Craft again
                    altar_obj = e.vision.find_template(e.screenshot(), self.altar_tmpl, 0.78)
                    if altar_obj:
                        e.input.click(altar_obj.center_x, altar_obj.center_y)
                        e.player.wait_until_idle(timeout=8)

                e.inventory.scan(e.screenshot())
                ess_count = e.inventory.count_filled()
                self._runes_made += ess_count
                self.stats.items_gained = self._runes_made
                self.stats.add_xp("runecrafting", int(ess_count * self.xp_per_ess))
                self._state = RCState.WALK_BANK
            else:
                self.log("Altar not found")
                time.sleep(2)

        elif self._state == RCState.WALK_BANK:
            e.pathfinder.walk_to_named(self.bank_location, timeout=90)
            self._state = RCState.BANK
        return True

    def get_paint_data(self):
        return {"Script":f"Runecraft ({self.altar})","Runes":self._runes_made,
                "XP/hr":f"{self.stats.xp_per_hour('runecrafting'):,.0f}","Runtime":self._format_elapsed()}
