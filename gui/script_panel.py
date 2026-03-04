"""
Script Panel
Per-script configuration UI panel.
Renders dynamic form fields based on each script's config schema.
Embedded inside the hub GUI.
"""

import json
from typing import Dict, Any, Callable, Optional

try:
    import customtkinter as ctk
    CTK = True
except ImportError:
    import tkinter as ctk
    CTK = False


# Schema definitions for each script type
# Each entry: field_name -> (label, widget_type, default, options_if_dropdown)
SCRIPT_SCHEMAS: Dict[str, Dict[str, tuple]] = {
    "Mining": {
        "ore_type":           ("Ore Type",        "dropdown", "iron",
                               ["tin","copper","iron","coal","mithril","adamant","rune"]),
        "power_mine":         ("Power Mine",       "checkbox", True,   None),
        "bank_location":      ("Bank Location",    "entry",    "",     None),
        "rocks_location":     ("Rocks Location",   "entry",    "",     None),
        "detection_threshold":("Detect Threshold", "slider",   0.78,   (0.5, 1.0)),
    },
    "Woodcutting": {
        "tree_type":          ("Tree Type",        "dropdown", "oak",
                               ["normal","oak","willow","maple","yew","magic","teak","mahogany"]),
        "power_chop":         ("Power Chop",       "checkbox", True,   None),
        "bank_location":      ("Bank Location",    "entry",    "",     None),
        "trees_location":     ("Trees Location",   "entry",    "",     None),
        "detection_threshold":("Detect Threshold", "slider",   0.78,   (0.5, 1.0)),
    },
    "Fishing": {
        "fish_type":          ("Fish Type",        "dropdown", "lobster",
                               ["shrimp","sardine","herring","trout","salmon",
                                "lobster","swordfish","tuna","shark","monkfish","barbarian"]),
        "power_fish":         ("Power Fish",       "checkbox", True,   None),
        "bank_location":      ("Bank Location",    "entry",    "",     None),
        "spots_location":     ("Spots Location",   "entry",    "",     None),
    },
    "Cooking": {
        "food_item":          ("Food Item",        "entry",    "lobster", None),
        "cooking_method":     ("Method",           "dropdown", "range",
                               ["range","fire","bonfire"]),
        "bank_location":      ("Bank Location",    "entry",    "al_kharid_bank", None),
        "cook_location":      ("Cook Location",    "entry",    "al_kharid_range", None),
    },
    "Firemaking": {
        "log_type":           ("Log Type",         "dropdown", "oak",
                               ["normal","oak","willow","maple","yew","magic","redwood"]),
        "use_tinderbox":      ("Use Tinderbox",    "checkbox", True,   None),
    },
    "Smithing": {
        "mode":               ("Mode",             "dropdown", "smelting",
                               ["smelting","anvil"]),
        "item":               ("Item",             "entry",    "iron_bar", None),
        "bank_location":      ("Bank Location",    "entry",    "varrock_west_bank", None),
    },
    "Agility": {
        "course":             ("Course",           "dropdown", "gnome_stronghold",
                               ["gnome_stronghold","draynor","al_kharid","varrock",
                                "canifis","falador","seers","pollnivneach","rellekka",
                                "ardougne"]),
        "eat_food":           ("Eat Food",         "checkbox", True,   None),
        "food_template":      ("Food Template",    "entry",    "inventory/salmon.png", None),
    },
    "Thieving": {
        "mode":               ("Mode",             "dropdown", "pickpocket",
                               ["pickpocket","stall"]),
        "target":             ("Target",           "entry",    "man",  None),
        "eat_food":           ("Eat Food",         "checkbox", True,   None),
    },
    "Fletching": {
        "mode":               ("Mode",             "dropdown", "bow",
                               ["bow","arrow","bolt"]),
        "item":               ("Item",             "entry",    "oak_longbow", None),
    },
    "Herblore": {
        "mode":               ("Mode",             "dropdown", "clean",
                               ["clean","potion"]),
        "herb":               ("Herb",             "entry",    "grimy_ranarr", None),
    },
    "Runecrafting": {
        "altar":              ("Altar",            "dropdown", "air",
                               ["air","mind","water","earth","fire","body",
                                "cosmic","chaos","nature","law","death","blood"]),
        "use_pouches":        ("Use Pouches",      "checkbox", True,   None),
    },
    "Hunter": {
        "mode":               ("Mode",             "dropdown", "chinchompa",
                               ["chinchompa","birdhouse"]),
        "location":           ("Location",         "entry",    "",     None),
    },
    "Farming": {
        "mode":               ("Mode",             "dropdown", "herb_run",
                               ["herb_run","tree_run","allotment"]),
        "seed":               ("Seed",             "entry",    "ranarr_seed", None),
    },
    "Construction": {
        "item":               ("Item to Build",    "entry",    "oak_larder", None),
        "butler":             ("Use Butler",       "checkbox", False,  None),
    },
    "Prayer": {
        "bone_type":          ("Bone Type",        "dropdown", "dragon_bones",
                               ["bones","big_bones","baby_dragon_bones",
                                "dragon_bones","superior_dragon_bones"]),
        "method":             ("Method",           "dropdown", "altar",
                               ["altar","ectofuntus"]),
    },
    "Crafting": {
        "mode":               ("Mode",             "dropdown", "gem_cutting",
                               ["gem_cutting","leather","pottery","glass_blowing","jewelry"]),
        "item":               ("Item",             "entry",    "sapphire", None),
    },
}


class ScriptPanel:
    """
    Dynamic configuration panel for a specific script type.
    Call get_config() to retrieve the current field values as a dict.
    """

    def __init__(self, parent, script_name: str, on_change: Optional[Callable] = None):
        self.parent = parent
        self.script_name = script_name
        self.on_change = on_change
        self._widgets: Dict[str, Any] = {}
        self._vars: Dict[str, Any] = {}

        self.frame = ctk.CTkFrame(parent) if CTK else ctk.Frame(parent)
        self._build(script_name)

    def _build(self, script_name: str):
        """Construct form fields for the given script."""
        # Clear existing
        for widget in self.frame.winfo_children():
            widget.destroy()
        self._widgets.clear()
        self._vars.clear()

        schema = SCRIPT_SCHEMAS.get(script_name, {})
        for field_key, (label_text, widget_type, default, options) in schema.items():
            row = ctk.CTkFrame(self.frame) if CTK else ctk.Frame(self.frame)
            row.pack(fill="x", pady=2, padx=4)

            lbl = ctk.CTkLabel(row, text=label_text, width=140, anchor="w") if CTK \
                else ctk.Label(row, text=label_text, width=18, anchor="w")
            lbl.pack(side="left")

            if widget_type == "entry":
                var = ctk.StringVar(value=str(default))
                w = ctk.CTkEntry(row, textvariable=var, width=140) if CTK \
                    else ctk.Entry(row, textvariable=var, width=18)
                w.pack(side="left")

            elif widget_type == "dropdown":
                var = ctk.StringVar(value=str(default))
                if CTK:
                    w = ctk.CTkComboBox(row, values=options, variable=var, width=140)
                else:
                    import tkinter.ttk as ttk
                    w = ttk.Combobox(row, values=options, textvariable=var, width=16)
                w.pack(side="left")

            elif widget_type == "checkbox":
                var = ctk.BooleanVar(value=bool(default))
                w = ctk.CTkCheckBox(row, text="", variable=var) if CTK \
                    else ctk.Checkbutton(row, variable=var)
                w.pack(side="left")

            elif widget_type == "slider":
                lo, hi = options if options else (0.0, 1.0)
                var = ctk.DoubleVar(value=float(default))
                w = ctk.CTkSlider(row, from_=lo, to=hi, variable=var, width=120) if CTK \
                    else ctk.Scale(row, from_=lo, to=hi, variable=var,
                                   orient="horizontal", length=120, resolution=0.01)
                w.pack(side="left")
                val_lbl = ctk.CTkLabel(row, textvariable=var, width=40) if CTK \
                    else ctk.Label(row, textvariable=var, width=5)
                val_lbl.pack(side="left")

            else:
                var = ctk.StringVar(value=str(default))
                w = ctk.CTkEntry(row, textvariable=var) if CTK \
                    else ctk.Entry(row, textvariable=var)
                w.pack(side="left")

            if self.on_change:
                var.trace_add("write", lambda *_: self.on_change())

            self._vars[field_key] = var
            self._widgets[field_key] = w

    def switch_script(self, script_name: str):
        """Rebuild the panel for a different script type."""
        self.script_name = script_name
        self._build(script_name)

    def get_config(self) -> Dict[str, Any]:
        """Return current field values as a config dict."""
        result = {}
        schema = SCRIPT_SCHEMAS.get(self.script_name, {})
        for field_key, (_, widget_type, default, _opts) in schema.items():
            var = self._vars.get(field_key)
            if var is None:
                result[field_key] = default
                continue
            try:
                if widget_type == "checkbox":
                    result[field_key] = bool(var.get())
                elif widget_type == "slider":
                    result[field_key] = float(var.get())
                elif widget_type == "entry":
                    val = str(var.get()).strip()
                    result[field_key] = val if val else default
                else:
                    result[field_key] = str(var.get())
            except Exception:
                result[field_key] = default
        return result

    def set_config(self, config: Dict[str, Any]):
        """Populate fields from an existing config dict."""
        for field_key, value in config.items():
            var = self._vars.get(field_key)
            if var:
                try:
                    var.set(value)
                except Exception:
                    pass

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)
