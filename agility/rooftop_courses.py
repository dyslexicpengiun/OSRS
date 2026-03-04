"""
Rooftop Course Data & Manager
Defines obstacle sequences for every OSRS rooftop agility course.
Each obstacle has a template path and optional screen search region.
"""
from typing import Optional, Dict, List


class RooftopCourse:
    """Iterates through a course's obstacle list."""
    def __init__(self, data: dict):
        self.data = data
        self._index = 0

    def reset(self):
        self._index = 0

    def current_obstacle(self) -> Optional[dict]:
        obs = self.data.get("obstacles", [])
        if self._index < len(obs):
            return obs[self._index]
        return None  # lap complete

    def advance(self):
        self._index += 1


# Screen regions are approximate for 1920x1080 resizable modern
# Adjust if using a different layout/resolution.
COURSES: Dict[str, dict] = {
    "gnome_stronghold": {
        "xp_per_lap": 86,
        "start_tile": (2474, 3436),
        "obstacles": [
            {"name": "Log balance",     "template": "objects/agility/gnome_log.png",      "region": (800,400,400,200)},
            {"name": "Obstacle net 1",  "template": "objects/agility/gnome_net.png",       "region": (800,350,400,200)},
            {"name": "Tree branch 1",   "template": "objects/agility/gnome_branch.png",    "region": (750,300,400,250)},
            {"name": "Balancing rope",  "template": "objects/agility/gnome_rope.png",      "region": (800,350,400,200)},
            {"name": "Tree branch 2",   "template": "objects/agility/gnome_branch2.png",   "region": (750,300,400,250)},
            {"name": "Obstacle net 2",  "template": "objects/agility/gnome_net2.png",      "region": (800,380,400,200)},
            {"name": "Obstacle pipe",   "template": "objects/agility/gnome_pipe.png",      "region": (800,400,400,200)},
        ],
    },
    "draynor": {
        "xp_per_lap": 120,
        "start_tile": (3103, 3279),
        "obstacles": [
            {"name": "Rough wall",      "template": "objects/agility/draynor_wall.png",    "region": (800,400,400,250)},
            {"name": "Tightrope 1",     "template": "objects/agility/draynor_rope1.png",   "region": (800,350,400,200)},
            {"name": "Tightrope 2",     "template": "objects/agility/draynor_rope2.png",   "region": (800,350,400,200)},
            {"name": "Narrow wall",     "template": "objects/agility/draynor_narrow.png",  "region": (800,380,400,200)},
            {"name": "Wall",            "template": "objects/agility/draynor_wall2.png",   "region": (800,400,400,200)},
            {"name": "Gap",             "template": "objects/agility/draynor_gap.png",     "region": (800,350,400,200)},
        ],
    },
    "al_kharid": {
        "xp_per_lap": 180,
        "start_tile": (3273, 3195),
        "obstacles": [
            {"name": "Rough wall",      "template": "objects/agility/alkharid_wall.png",   "region": (800,400,400,250)},
            {"name": "Tightrope 1",     "template": "objects/agility/alkharid_rope1.png",  "region": (800,350,400,200)},
            {"name": "Cable",           "template": "objects/agility/alkharid_cable.png",  "region": (800,350,400,200)},
            {"name": "Zip line",        "template": "objects/agility/alkharid_zip.png",    "region": (800,380,400,200)},
            {"name": "Tightrope 2",     "template": "objects/agility/alkharid_rope2.png",  "region": (800,350,400,200)},
            {"name": "Jumping pad",     "template": "objects/agility/alkharid_pad.png",    "region": (800,400,400,200)},
        ],
    },
    "varrock": {
        "xp_per_lap": 238,
        "start_tile": (3221, 3414),
        "obstacles": [
            {"name": "Rough wall",      "template": "objects/agility/varrock_wall.png",    "region": (800,400,400,250)},
            {"name": "Clothes line",    "template": "objects/agility/varrock_clothes.png", "region": (800,350,400,200)},
            {"name": "Gap 1",           "template": "objects/agility/varrock_gap1.png",    "region": (800,380,400,200)},
            {"name": "Wall",            "template": "objects/agility/varrock_wall2.png",   "region": (800,400,400,200)},
            {"name": "Gap 2",           "template": "objects/agility/varrock_gap2.png",    "region": (800,350,400,200)},
            {"name": "Gap 3",           "template": "objects/agility/varrock_gap3.png",    "region": (800,380,400,200)},
            {"name": "Ledge",           "template": "objects/agility/varrock_ledge.png",   "region": (800,400,400,200)},
            {"name": "Edge",            "template": "objects/agility/varrock_edge.png",    "region": (800,350,400,200)},
        ],
    },
    "canifis": {
        "xp_per_lap": 240,
        "start_tile": (3508, 3492),
        "obstacles": [
            {"name": "Tall tree",       "template": "objects/agility/canifis_tree.png",    "region": (800,350,400,300)},
            {"name": "Gap 1",           "template": "objects/agility/canifis_gap1.png",    "region": (800,350,400,200)},
            {"name": "Gap 2",           "template": "objects/agility/canifis_gap2.png",    "region": (800,350,400,200)},
            {"name": "Gap 3",           "template": "objects/agility/canifis_gap3.png",    "region": (800,350,400,200)},
            {"name": "Gap 4",           "template": "objects/agility/canifis_gap4.png",    "region": (800,350,400,200)},
            {"name": "Pole vault",      "template": "objects/agility/canifis_pole.png",    "region": (800,400,400,200)},
            {"name": "Gap 5",           "template": "objects/agility/canifis_gap5.png",    "region": (800,350,400,200)},
        ],
    },
    "falador": {
        "xp_per_lap": 335,
        "start_tile": (3036, 3341),
        "obstacles": [
            {"name": "Rough wall",      "template": "objects/agility/falador_wall.png",    "region": (800,400,400,250)},
            {"name": "Tightrope 1",     "template": "objects/agility/falador_rope1.png",   "region": (800,350,400,200)},
            {"name": "Tightrope 2",     "template": "objects/agility/falador_rope2.png",   "region": (800,350,400,200)},
            {"name": "Tightrope 3",     "template": "objects/agility/falador_rope3.png",   "region": (800,350,400,200)},
            {"name": "Gap",             "template": "objects/agility/falador_gap.png",     "region": (800,380,400,200)},
            {"name": "Ledge 1",         "template": "objects/agility/falador_ledge1.png",  "region": (800,400,400,200)},
            {"name": "Ledge 2",         "template": "objects/agility/falador_ledge2.png",  "region": (800,400,400,200)},
            {"name": "Ledge 3",         "template": "objects/agility/falador_ledge3.png",  "region": (800,400,400,200)},
            {"name": "Ledge 4",         "template": "objects/agility/falador_ledge4.png",  "region": (800,400,400,200)},
        ],
    },
    "seers": {
        "xp_per_lap": 570,
        "start_tile": (2729, 3489),
        "obstacles": [
            {"name": "Wall",            "template": "objects/agility/seers_wall.png",      "region": (800,400,400,250)},
            {"name": "Gap 1",           "template": "objects/agility/seers_gap1.png",      "region": (800,350,400,200)},
            {"name": "Tightrope",       "template": "objects/agility/seers_rope.png",      "region": (800,350,400,200)},
            {"name": "Gap 2",           "template": "objects/agility/seers_gap2.png",      "region": (800,350,400,200)},
            {"name": "Gap 3",           "template": "objects/agility/seers_gap3.png",      "region": (800,380,400,200)},
            {"name": "Edge",            "template": "objects/agility/seers_edge.png",      "region": (800,400,400,200)},
        ],
    },
    "pollnivneach": {
        "xp_per_lap": 890,
        "start_tile": (3351, 2961),
        "obstacles": [
            {"name": "Basket",          "template": "objects/agility/poll_basket.png",     "region": (800,400,400,250)},
            {"name": "Market stall",    "template": "objects/agility/poll_stall.png",      "region": (800,380,400,200)},
            {"name": "Banner",          "template": "objects/agility/poll_banner.png",     "region": (800,350,400,200)},
            {"name": "Gap",             "template": "objects/agility/poll_gap.png",        "region": (800,350,400,200)},
            {"name": "Tree",            "template": "objects/agility/poll_tree.png",       "region": (800,350,400,300)},
            {"name": "Rough wall",      "template": "objects/agility/poll_wall.png",       "region": (800,400,400,200)},
            {"name": "Monkeybars",      "template": "objects/agility/poll_monkeybars.png", "region": (800,380,400,200)},
            {"name": "Tree 2",          "template": "objects/agility/poll_tree2.png",      "region": (800,350,400,300)},
            {"name": "Drying line",     "template": "objects/agility/poll_drying.png",     "region": (800,380,400,200)},
        ],
    },
    "rellekka": {
        "xp_per_lap": 780,
        "start_tile": (2625, 3676),
        "obstacles": [
            {"name": "Rough wall",      "template": "objects/agility/rell_wall.png",       "region": (800,400,400,250)},
            {"name": "Gap 1",           "template": "objects/agility/rell_gap1.png",       "region": (800,350,400,200)},
            {"name": "Tightrope 1",     "template": "objects/agility/rell_rope1.png",      "region": (800,350,400,200)},
            {"name": "Gap 2",           "template": "objects/agility/rell_gap2.png",       "region": (800,380,400,200)},
            {"name": "Tightrope 2",     "template": "objects/agility/rell_rope2.png",      "region": (800,350,400,200)},
            {"name": "Gap 3",           "template": "objects/agility/rell_gap3.png",       "region": (800,380,400,200)},
        ],
    },
    "ardougne": {
        "xp_per_lap": 793,
        "start_tile": (2673, 3298),
        "obstacles": [
            {"name": "Wooden beam",     "template": "objects/agility/ardy_beam.png",       "region": (800,380,400,250)},
            {"name": "Gap 1",           "template": "objects/agility/ardy_gap1.png",       "region": (800,350,400,200)},
            {"name": "Gap 2",           "template": "objects/agility/ardy_gap2.png",       "region": (800,350,400,200)},
            {"name": "Gap 3",           "template": "objects/agility/ardy_gap3.png",       "region": (800,380,400,200)},
            {"name": "Gap 4",           "template": "objects/agility/ardy_gap4.png",       "region": (800,380,400,200)},
            {"name": "Steep roof",      "template": "objects/agility/ardy_roof.png",       "region": (800,400,400,200)},
            {"name": "Gap 5",           "template": "objects/agility/ardy_gap5.png",       "region": (800,350,400,200)},
        ],
    },
}
