"""Pickpocketing sub-script."""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class PPState(Enum): FIND_NPC=auto(); PICKPOCKET=auto(); EAT=auto(); DROP_JUNK=auto()

NPC_INFO = {
    "man":           {"template":"npcs/man.png",        "xp":8,  "hp_risk":True},
    "woman":         {"template":"npcs/woman.png",      "xp":8,  "hp_risk":True},
    "farmer":        {"template":"npcs/farmer.png",     "xp":14, "hp_risk":True},
    "warrior_woman": {"template":"npcs/warrior_woman.png","xp":26,"hp_risk":True},
    "rogue":         {"template":"npcs/rogue.png",      "xp":36, "hp_risk":True},
    "master_farmer": {"template":"npcs/master_farmer.png","xp":43,"hp_risk":True},
    "guard":         {"template":"npcs/guard.png",      "xp":46, "hp_risk":True},
    "knight":        {"template":"npcs/knight.png",     "xp":84, "hp_risk":True},
    "paladin":       {"template":"npcs/paladin.png",    "xp":152,"hp_risk":True},
    "gnome":         {"template":"npcs/gnome.png",      "xp":198,"hp_risk":True},
    "hero":          {"template":"npcs/hero.png",       "xp":275,"hp_risk":True},
    "elf":           {"template":"npcs/elf.png",        "xp":353,"hp_risk":True},
}

class PickpocketScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.target        = c.get("target","man")
        self.eat_food      = c.get("eat_food",True)
        self.food_template = c.get("food_template","inventory/monkfish.png")
        self.hp_threshold  = c.get("hp_threshold",0.40)
        self.npc_info      = NPC_INFO.get(self.target, NPC_INFO["man"])
        self._state        = PPState.FIND_NPC
        self._pickpockets  = 0
        self._last_pp_time = 0.0

    def setup(self):
        self.log(f"Pickpocketing: {self.target}")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self.eat_food and e.game_state.health < self.hp_threshold:
            self._state = PPState.EAT

        if self._state == PPState.EAT:
            slot = e.inventory.find_item(self.food_template, screen)
            if slot:
                e.inventory.click_slot(slot.index)
                time.sleep(random.uniform(0.4,0.8))
            else:
                self.log("Out of food")
            self._state = PPState.FIND_NPC

        elif self._state == PPState.FIND_NPC:
            match = e.vision.find_template(screen, self.npc_info["template"], 0.78)
            if match:
                e.input.right_click(match.center_x+random.randint(-6,6),
                                     match.center_y+random.randint(-6,6))
                time.sleep(random.uniform(0.3,0.55))
                if e.interfaces.click_menu_option("Pickpocket"):
                    self._state = PPState.PICKPOCKET
                    self._last_pp_time = time.time()
                else:
                    time.sleep(0.5)
            else:
                time.sleep(random.uniform(0.4,1.0))

        elif self._state == PPState.PICKPOCKET:
            e.player.update(screen)
            if e.player.is_idle() and e.player.time_idle() > 0.8:
                self._pickpockets += 1
                self.stats.items_gained = self._pickpockets
                self.stats.add_xp("thieving", self.npc_info["xp"])
                e.inventory.scan(screen)
                if e.inventory.is_full():
                    self._state = PPState.DROP_JUNK
                else:
                    self._state = PPState.FIND_NPC
            elif (time.time()-self._last_pp_time) > 6:
                self._state = PPState.FIND_NPC
            else:
                e.antiban.sleep_action()

        elif self._state == PPState.DROP_JUNK:
            screen = e.screenshot()
            e.inventory.scan(screen)
            keep_templates = [self.food_template]
            for slot in e.inventory.get_filled_slots():
                keep = any(e.inventory.find_item(t,screen) and
                           e.inventory.find_item(t,screen).index == slot.index
                           for t in keep_templates)
                if not keep:
                    e.inventory.drop_item(slot.index)
                    time.sleep(random.uniform(0.06,0.14))
            self._state = PPState.FIND_NPC
        return True

    def get_paint_data(self):
        return {"Script":f"Pickpocket ({self.target})","Stolen":self._pickpockets,
                "XP/hr":f"{self.stats.xp_per_hour('thieving'):,.0f}","Runtime":self._format_elapsed()}
