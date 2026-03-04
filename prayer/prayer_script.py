"""Prayer Script — uses bones on a gilded altar or at the Ectofuntus."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class PrayerState(Enum): BANK=auto(); WALK_ALTAR=auto(); OFFER=auto(); WAITING=auto()

BONE_INFO = {
    "bones":               {"xp_altar":7.5,   "xp_ectofu":4.5,  "template":"inventory/bones.png"},
    "big_bones":           {"xp_altar":15,     "xp_ectofu":10,   "template":"inventory/big_bones.png"},
    "baby_dragon_bones":   {"xp_altar":30,     "xp_ectofu":17,   "template":"inventory/baby_dragon_bones.png"},
    "dragon_bones":        {"xp_altar":252,    "xp_ectofu":144,  "template":"inventory/dragon_bones.png"},
    "superior_dragon_bones":{"xp_altar":525,   "xp_ectofu":280,  "template":"inventory/superior_dragon_bones.png"},
    "wyvern_bones":        {"xp_altar":252,    "xp_ectofu":144,  "template":"inventory/wyvern_bones.png"},
    "lava_dragon_bones":   {"xp_altar":341.25, "xp_ectofu":195,  "template":"inventory/lava_dragon_bones.png"},
}

class PrayerScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.bone_type     = c.get("bone_type","dragon_bones")
        self.method        = c.get("method","altar")   # "altar" or "ectofuntus"
        self.altar_location= c.get("altar_location","gilded_altar_house")
        self.bank_location = c.get("bank_location","house_party_bank")
        info               = BONE_INFO.get(self.bone_type, BONE_INFO["dragon_bones"])
        self.bone_tmpl     = info["template"]
        self.xp_each       = info["xp_altar"] if self.method == "altar" else info["xp_ectofu"]
        self.altar_tmpl    = "objects/gilded_altar.png"
        self._state        = PrayerState.BANK
        self._offered      = 0

    def setup(self):
        self.log(f"Prayer: {self.bone_type} via {self.method}")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == PrayerState.BANK:
            if not e.bank.wait_for_open(5):
                e.pathfinder.walk_to_named(self.bank_location, timeout=60)
                e.bank.wait_for_open(8)
            if e.bank.is_open():
                e.bank.deposit_inventory()
                time.sleep(random.uniform(0.3,0.5))
                e.bank.withdraw_item(self.bone_tmpl,"28")
                time.sleep(random.uniform(0.3,0.5))
                e.bank.close()
                self._state = PrayerState.WALK_ALTAR

        elif self._state == PrayerState.WALK_ALTAR:
            e.pathfinder.walk_to_named(self.altar_location, timeout=60)
            self._state = PrayerState.OFFER

        elif self._state == PrayerState.OFFER:
            screen = e.screenshot()
            altar = e.vision.find_template(screen, self.altar_tmpl, 0.78)
            if altar:
                # Use first bone on altar, rest auto-follows
                e.inventory.scan(screen)
                bones = e.inventory.get_filled_slots()
                if bones:
                    e.inventory.click_slot(bones[0].index)
                    time.sleep(random.uniform(0.15,0.3))
                    e.input.click(altar.center_x+random.randint(-8,8),
                                   altar.center_y+random.randint(-8,8))
                    self._state = PrayerState.WAITING
                    self._offer_start = time.time()
            else:
                self.log("Altar not found")
                time.sleep(2)

        elif self._state == PrayerState.WAITING:
            screen = e.screenshot()
            e.player.update(screen)
            e.inventory.scan(screen)
            if e.inventory.is_empty():
                self._offered += 28
                self.stats.items_gained = self._offered
                self.stats.add_xp("prayer", int(28 * self.xp_each))
                self._state = PrayerState.BANK
            elif e.player.is_idle() and e.player.time_idle() > 2:
                # Continue using bones on altar
                bones = e.inventory.get_filled_slots()
                if bones:
                    altar = e.vision.find_template(screen, self.altar_tmpl, 0.78)
                    if altar:
                        e.inventory.click_slot(bones[0].index)
                        time.sleep(random.uniform(0.1,0.25))
                        e.input.click(altar.center_x+random.randint(-6,6),
                                       altar.center_y+random.randint(-6,6))
                        self._offer_start = time.time()
            elif (time.time()-self._offer_start) > 120:
                self._state = PrayerState.BANK
            else:
                e.antiban.sleep_action()
        return True

    def get_paint_data(self):
        return {"Script":f"Prayer ({self.bone_type})","Offered":self._offered,
                "XP/hr":f"{self.stats.xp_per_hour('prayer'):,.0f}","Runtime":self._format_elapsed()}
