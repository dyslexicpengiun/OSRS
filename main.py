"""
OSRS Automation Suite - Entry Point
Launches the hub GUI or runs a script directly from the command line.

Usage:
    python main.py                            # Launch hub GUI
    python main.py --script mining            # Run mining script headless
    python main.py --script mining --script-config my_iron.json
    python main.py --config myconfig.json
    python main.py --list                     # List available scripts
"""

import sys
import os
import argparse
import logging
import json

# Ensure project root is on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

os.makedirs(os.path.join(_HERE, "logs"), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(_HERE, "logs", "session.log"),
            mode='a', encoding='utf-8'
        ),
    ]
)
logger = logging.getLogger(__name__)

SCRIPT_MAP = {
    "mining":        ("scripts.mining.mining_script",            "MiningScript"),
    "woodcutting":   ("scripts.woodcutting.woodcutting_script",  "WoodcuttingScript"),
    "fishing":       ("scripts.fishing.fishing_script",          "FishingScript"),
    "cooking":       ("scripts.cooking.cooking_script",          "CookingScript"),
    "firemaking":    ("scripts.firemaking.firemaking_script",     "FiremakingScript"),
    "smithing":      ("scripts.smithing.smithing_script",        "SmithingScript"),
    "agility":       ("scripts.agility.agility_script",          "AgilityScript"),
    "thieving":      ("scripts.thieving.thieving_script",        "ThievingScript"),
    "fletching":     ("scripts.fletching.fletching_script",      "FletchingScript"),
    "herblore":      ("scripts.herblore.herblore_script",        "HerbloreScript"),
    "runecrafting":  ("scripts.runecrafting.runecrafting_script", "RunecraftingScript"),
    "hunter":        ("scripts.hunter.hunter_script",            "HunterScript"),
    "farming":       ("scripts.farming.farming_script",          "FarmingScript"),
    "construction":  ("scripts.construction.construction_script","ConstructionScript"),
    "prayer":        ("scripts.prayer.prayer_script",            "PrayerScript"),
    "crafting":      ("scripts.crafting.crafting_script",        "CraftingScript"),
}


def launch_gui(config_path: str):
    from gui.hub import HubGUI
    app = HubGUI(config_path=config_path)
    app.run()


def launch_script(script_name: str, config_path: str, script_config: dict):
    key = script_name.lower()
    if key not in SCRIPT_MAP:
        logger.error(
            f"Unknown script: '{script_name}'. "
            f"Available: {', '.join(sorted(SCRIPT_MAP.keys()))}"
        )
        sys.exit(1)

    module_path, class_name = SCRIPT_MAP[key]
    import importlib
    from core.engine import Engine

    logger.info(f"[main] Launching {class_name} headlessly")

    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
    except Exception as e:
        logger.error(f"Failed to import {module_path}.{class_name}: {e}")
        sys.exit(1)

    with Engine(config_path) as engine:
        script = cls(engine, script_config)
        try:
            script.run()
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
            script.stop()
        except Exception as e:
            logger.exception(f"Unhandled exception in script: {e}")
            script.stop()
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="OSRS Automation Suite")
    parser.add_argument("--script", type=str, default=None, metavar="NAME",
                        help="Script to run headlessly. Use --list to see options.")
    parser.add_argument("--config", type=str, default="config.json", metavar="PATH",
                        help="Path to global config JSON (default: config.json)")
    parser.add_argument("--script-config", type=str, default=None, metavar="PATH",
                        help="Path to script-specific config JSON")
    parser.add_argument("--list", action="store_true",
                        help="List all available scripts and exit")
    parser.add_argument("--debug", action="store_true",
                        help="Set log level to DEBUG")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list:
        print("Available scripts:")
        for name in sorted(SCRIPT_MAP.keys()):
            mod, cls = SCRIPT_MAP[name]
            print(f"  {name:<16}  {cls}")
        sys.exit(0)

    script_config = {}
    if args.script_config:
        try:
            with open(args.script_config) as f:
                script_config = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load script config: {e}")

    if args.script:
        launch_script(args.script, args.config, script_config)
    else:
        launch_gui(args.config)


if __name__ == "__main__":
    main()
