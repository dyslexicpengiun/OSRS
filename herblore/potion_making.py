"""Potion making — combine herb + secondary ingredient."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class PotState(Enum): BANK=auto(); MIX=auto(); WAITING=auto()

POTIONS = {
    "attack_potion":     {"herb":"inventory/guam_leaf.png",       "secondary":"inventory/eye_of_newt.png",    "xp":25},
    "strength_potion":   {"herb":"inventory/tarromin.png",        "secondary":"inventory/limpwurt_root.png",  "xp":50},
    "defence_potion":    {"herb":"inventory/ranarr_weed.png",     "secondary":"inventory/white_berries.png",  "xp":75},
    "prayer_potion":     {"herb":"inventory/ranarr_weed.png",     "secondary":"inventory/snape_grass.png",    "xp":87.5},
    "super_attack":      {"herb":"inventory/irit_leaf.png",       "secondary":"inventory/eye_of_newt.png",    "xp":100},
    "super_strength":    {"herb":"inventory/kwuarm.png",          "secondary":"inventory/limpwurt_root.png",  "xp":125},
    "super_defence":     {"herb":"inventory/cadantine.png",       "secondary":"inventory/white_berries.png",  "xp":150},
    "ranging_potion":    {"herb":"inventory/dwarf_weed.png",      "secondary":"inventory/wine_of_zamorak.png","xp":162.5},
    "magic_potion":      {"herb":"inventory/lantadyme.png",       "secondary":"inventory/potato_cactus.png",  "xp":172.5},
    "saradomin_brew":    {"herb":"inventory/toadflax.png",        "secondary":"inventory/crushed_nest.png",   "xp":180},
    "super_restore":     {"herb":"inventory/snapdragon.png",      "secondary":"inventory/red_spiders_eggs.png","xp":142.5},
    "zamorak_brew":      {"herb":"inventory/torstol.png",         "secondary":"inventory/jangerberries.png",  "xp":175},
}

class PotionMakingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.potion        = c.get("herb","prayer_potion")
        self.bank_location = c.get("bank_location","grand_exchange_bank")
        info               = POTIONS.get(self.potion, POTIONS["prayer_potion"])
        self.herb_t        = info["herb"]
        self.secondary_t   = info["secondary"]
        self.xp_each       = info["xp"]
        self._vial_t       = "inventory/vial_of_water.png"
        self._state        = PotState.BANK
        self._made         = 0

    def setup(self):
        self.log(f"Making potions: {self.potion}")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == PotState.BANK:
            if not e.bank.wait_for_open(5):
                e.pathfinder.walk_to_named(self.bank_location, timeout=60)
                e.bank.wait_for_open(8)
            if e.bank.is_open():
                e.bank.deposit_inventory()
                time.sleep(random.uniform(0.3,0.5))
                e.bank.withdraw_item(self.herb_t,"14")
                time.sleep(random.uniform(0.2,0.4))
                e.bank.withdraw_item(self.secondary_t,"14")
                time.sleep(random.uniform(0.3,0.5))
                e.bank.close()
                self._state = PotState.MIX

        elif self._state == PotState.MIX:
            screen = e.screenshot()
            herb = e.inventory.find_item(self.herb_t, screen)
            sec  = e.inventory.find_item(self.secondary_t, screen)
            if not herb or not sec:
                self._state = PotState.BANK; return True
            e.inventory.use_item_on_item(herb.index, sec.index)
            for _ in range(25):
                screen = e.screenshot()
                if e.interfaces.is_make_interface_open(screen):
                    e.interfaces.click_make_all()
                    self._state = PotState.WAITING
                    self._start = time.time()
                    break
                time.sleep(0.3)

        elif self._state == PotState.WAITING:
            screen = e.screenshot()
            e.player.update(screen)
            if e.player.is_idle() and e.player.time_idle() > 2:
                self._made += 14
                self.stats.items_gained = self._made
                self.stats.add_xp("herblore", int(14 * self.xp_each))
                self._state = PotState.BANK
            elif (time.time()-self._start) > 60:
                self._state = PotState.BANK
            else:
                e.antiban.sleep_action()
        return True

    def get_paint_data(self):
        return {"Script":f"Potions ({self.potion})","Made":self._made,
                "XP/hr":f"{self.stats.xp_per_hour('herblore'):,.0f}","Runtime":self._format_elapsed()}
