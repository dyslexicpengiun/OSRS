"""Construction Script — builds and removes furniture using butler for plank supply."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class ConState(Enum): GET_PLANKS=auto(); BUILD=auto(); WAITING=auto()

ITEMS = {
    "oak_larder":       {"planks":"oak_plank",    "planks_per":8, "xp":480, "room":"kitchen"},
    "mahogany_table":   {"planks":"mahogany_plank","planks_per":6,"xp":840,"room":"dining_room"},
    "teak_garden_bench":{"planks":"teak_plank",   "planks_per":6, "xp":540, "room":"garden"},
    "oak_bench":        {"planks":"oak_plank",    "planks_per":4, "xp":240, "room":"parlour"},
}

class ConstructionScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.item        = c.get("item","oak_larder")
        self.use_butler  = c.get("butler",False)
        info             = ITEMS.get(self.item, ITEMS["oak_larder"])
        self.plank_type  = info["planks"]
        self.planks_per  = info["planks_per"]
        self.xp_each     = info["xp"]
        self.room        = info["room"]
        self.plank_tmpl  = f"inventory/{self.plank_type}.png"
        self.hotspot_tmpl= f"objects/construction/{self.item}_hotspot.png"
        self.built_tmpl  = f"objects/construction/{self.item}_built.png"
        self._state      = ConState.GET_PLANKS
        self._built      = 0

    def setup(self):
        self.log(f"Construction: {self.item} (butler={self.use_butler})")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == ConState.GET_PLANKS:
            if self.use_butler:
                # Call butler with bell pull
                bell = e.vision.find_template(screen,"objects/construction/bell_pull.png",0.78)
                if bell:
                    e.input.click(bell.center_x, bell.center_y)
                    time.sleep(random.uniform(1.5,3.0))
                    e.interfaces.click_menu_option("Fetch")
                    time.sleep(random.uniform(2.0,4.0))
            else:
                # Bank to get planks
                if not e.bank.wait_for_open(5):
                    b = e.vision.find_template(screen,"objects/bank_booth.png",0.80)
                    if b:
                        e.input.right_click(b.center_x, b.center_y)
                        time.sleep(random.uniform(0.3,0.6))
                        e.interfaces.click_menu_option("Bank")
                        e.bank.wait_for_open(6)
                if e.bank.is_open():
                    e.bank.deposit_inventory()
                    time.sleep(random.uniform(0.3,0.5))
                    e.bank.withdraw_item(self.plank_tmpl,"28")
                    time.sleep(random.uniform(0.3,0.5))
                    e.bank.close()
            self._state = ConState.BUILD

        elif self._state == ConState.BUILD:
            screen = e.screenshot()
            # Click hotspot or built item to build/remove
            hotspot = e.vision.find_template(screen, self.hotspot_tmpl, 0.78)
            built   = e.vision.find_template(screen, self.built_tmpl, 0.78)
            if hotspot:
                e.input.click(hotspot.center_x+random.randint(-8,8),
                               hotspot.center_y+random.randint(-8,8))
                for _ in range(20):
                    screen = e.screenshot()
                    if e.interfaces.is_make_interface_open(screen):
                        e.interfaces.click_make_all()
                        self._state = ConState.WAITING
                        self._build_start = time.time()
                        break
                    time.sleep(0.25)
            elif built:
                # Remove it
                e.input.right_click(built.center_x, built.center_y)
                time.sleep(random.uniform(0.3,0.55))
                e.interfaces.click_menu_option("Remove")
                e.player.wait_until_idle(timeout=8)
            else:
                time.sleep(1)

        elif self._state == ConState.WAITING:
            screen = e.screenshot()
            e.player.update(screen)
            if e.player.is_idle() and e.player.time_idle() > 1.5:
                self._built += 1
                self.stats.items_gained = self._built
                self.stats.add_xp("construction", self.xp_each)
                e.inventory.scan(screen)
                if e.inventory.is_empty():
                    self._state = ConState.GET_PLANKS
                else:
                    self._state = ConState.BUILD
            elif (time.time()-self._build_start) > 15:
                self._state = ConState.BUILD
            else:
                e.antiban.sleep_action()
        return True

    def get_paint_data(self):
        return {"Script":f"Construction ({self.item})","Built":self._built,
                "XP/hr":f"{self.stats.xp_per_hour('construction'):,.0f}","Runtime":self._format_elapsed()}
