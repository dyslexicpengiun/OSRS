"""
Crafting Script
Supports: gem cutting, leather crafting, pottery, glass blowing, jewelry.
All modes use the bank→craft cycle.
"""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
logger = logging.getLogger(__name__)

class CraftState(Enum): BANK=auto(); CRAFT=auto(); WAITING=auto()

GEM_INFO = {
    "opal":      {"xp":15,   "tmpl":"inventory/uncut_opal.png"},
    "jade":      {"xp":20,   "tmpl":"inventory/uncut_jade.png"},
    "red_topaz": {"xp":25,   "tmpl":"inventory/uncut_red_topaz.png"},
    "sapphire":  {"xp":50,   "tmpl":"inventory/uncut_sapphire.png"},
    "emerald":   {"xp":67.5, "tmpl":"inventory/uncut_emerald.png"},
    "ruby":      {"xp":85,   "tmpl":"inventory/uncut_ruby.png"},
    "diamond":   {"xp":107.5,"tmpl":"inventory/uncut_diamond.png"},
    "dragonstone":{"xp":137.5,"tmpl":"inventory/uncut_dragonstone.png"},
    "onyx":      {"xp":167.5,"tmpl":"inventory/uncut_onyx.png"},
    "zenyte":    {"xp":200,  "tmpl":"inventory/uncut_zenyte.png"},
}
LEATHER_INFO = {
    "leather_gloves":{"xp":13.8,"mat":"inventory/leather.png",     "chisel":False},
    "hard_leather_body":{"xp":35,"mat":"inventory/hard_leather.png","chisel":False},
    "dragon_hide_body":{"xp":186,"mat":"inventory/black_d_hide.png","chisel":False},
}
GLASS_INFO = {
    "glass_orb":   {"xp":52.5,"tmpl":"inventory/molten_glass.png"},
    "glass_vial":  {"xp":35,  "tmpl":"inventory/molten_glass.png"},
    "glass_bowl":  {"xp":42.5,"tmpl":"inventory/molten_glass.png"},
    "glass_candle":{"xp":87.5,"tmpl":"inventory/molten_glass.png"},
}
JEWELRY_INFO = {
    "gold_ring":    {"xp":15,  "bar":"inventory/gold_bar.png","mould":"inventory/ring_mould.png"},
    "sapphire_ring":{"xp":40,  "bar":"inventory/gold_bar.png","mould":"inventory/ring_mould.png"},
    "gold_necklace":{"xp":20,  "bar":"inventory/gold_bar.png","mould":"inventory/necklace_mould.png"},
    "amulet_of_power":{"xp":70,"bar":"inventory/gold_bar.png","mould":"inventory/amulet_mould.png"},
}

class CraftingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.mode          = c.get("mode","gem_cutting")
        self.item          = c.get("item","sapphire")
        self.bank_location = c.get("bank_location","grand_exchange_bank")
        self._state        = CraftState.BANK
        self._made         = 0
        self._craft_start  = 0.0
        self._setup_mode()

    def _setup_mode(self):
        m, i = self.mode, self.item
        if m == "gem_cutting":
            info = GEM_INFO.get(i, GEM_INFO["sapphire"])
            self.xp_each    = info["xp"]
            self.mat_tmpl   = info["tmpl"]
            self.tool_tmpl  = "inventory/chisel.png"
            self.tool_slot  = True
        elif m == "leather":
            info = LEATHER_INFO.get(i, LEATHER_INFO["leather_gloves"])
            self.xp_each    = info["xp"]
            self.mat_tmpl   = info["mat"]
            self.tool_tmpl  = "inventory/needle.png"
            self.tool_slot  = True
        elif m == "glass_blowing":
            info = GLASS_INFO.get(i, GLASS_INFO["glass_orb"])
            self.xp_each    = info["xp"]
            self.mat_tmpl   = info["tmpl"]
            self.tool_tmpl  = "inventory/glassblowing_pipe.png"
            self.tool_slot  = True
        elif m == "jewelry":
            info = JEWELRY_INFO.get(i, JEWELRY_INFO["sapphire_ring"])
            self.xp_each    = info["xp"]
            self.mat_tmpl   = info["bar"]
            self.tool_tmpl  = info["mould"]
            self.tool_slot  = True
        else:
            # pottery — clay + water
            self.xp_each    = 6.3
            self.mat_tmpl   = "inventory/soft_clay.png"
            self.tool_tmpl  = None
            self.tool_slot  = False

    def setup(self):
        self.log(f"Crafting: {self.mode} — {self.item}")
        return True

    def loop(self):
        e = self.engine
        screen = e.screenshot()

        if self._state == CraftState.BANK:
            if not e.bank.wait_for_open(5):
                e.pathfinder.walk_to_named(self.bank_location, timeout=60)
                e.bank.wait_for_open(8)
            if e.bank.is_open():
                e.bank.deposit_inventory()
                time.sleep(random.uniform(0.3,0.5))
                if self.tool_tmpl:
                    e.bank.withdraw_item(self.tool_tmpl,"1")
                    time.sleep(random.uniform(0.2,0.35))
                e.bank.withdraw_item(self.mat_tmpl,"27")
                time.sleep(random.uniform(0.3,0.5))
                e.bank.close()
                self._state = CraftState.CRAFT

        elif self._state == CraftState.CRAFT:
            screen = e.screenshot()
            mat  = e.inventory.find_item(self.mat_tmpl, screen)
            if not mat:
                self._state = CraftState.BANK; return True
            if self.tool_tmpl:
                tool = e.inventory.find_item(self.tool_tmpl, screen)
                if tool:
                    e.inventory.use_item_on_item(tool.index, mat.index)
                else:
                    e.inventory.click_slot(mat.index)
            else:
                e.inventory.click_slot(mat.index)
            for _ in range(20):
                screen = e.screenshot()
                if e.interfaces.is_make_interface_open(screen):
                    e.interfaces.click_make_all()
                    self._state = CraftState.WAITING
                    self._craft_start = time.time()
                    break
                time.sleep(0.3)

        elif self._state == CraftState.WAITING:
            screen = e.screenshot()
            e.player.update(screen)
            e.inventory.scan(screen)
            if e.player.is_idle() and e.player.time_idle() > 2:
                n = e.inventory.count_empty()
                self._made += n
                self.stats.items_gained = self._made
                self.stats.add_xp("crafting", int(n * self.xp_each))
                self._state = CraftState.BANK
            elif (time.time()-self._craft_start) > 90:
                self._state = CraftState.BANK
            else:
                e.antiban.sleep_action()
        return True

    def get_paint_data(self):
        return {"Script":f"Crafting ({self.mode}/{self.item})","Made":self._made,
                "XP/hr":f"{self.stats.xp_per_hour('crafting'):,.0f}","Runtime":self._format_elapsed()}
