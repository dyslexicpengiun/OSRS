"""
OSRS Automation Suite - Diagnostic Runner
==========================================
Run this BEFORE attempting to use any script.
It will tell you exactly what works, what doesn't, and why.

Usage:
    python diagnose.py              # Full diagnostic
    python diagnose.py --fast       # Skip slow tests (no screen capture)
    python diagnose.py --fix        # Auto-fix what it can
    python diagnose.py --section imports   # Only run imports section
"""

import sys
import os
import json
import time
import traceback
import argparse
from typing import List, Tuple, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── Color codes ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗{RESET} {msg}")
def info(msg):  print(f"  {CYAN}→{RESET} {msg}")
def section(title):
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}")

RESULTS = {"pass": 0, "warn": 0, "fail": 0}

def check(condition, pass_msg, fail_msg, warn_msg=None):
    if condition is True:
        ok(pass_msg); RESULTS["pass"] += 1
    elif condition == "warn":
        warn(warn_msg or pass_msg); RESULTS["warn"] += 1
    else:
        fail(fail_msg); RESULTS["fail"] += 1


# ── 1. Python environment ─────────────────────────────────────────────────────
def check_python():
    section("1. Python Environment")
    v = sys.version_info
    check(v >= (3, 9), f"Python {v.major}.{v.minor}.{v.micro} ≥ 3.9",
          f"Python {v.major}.{v.minor} is too old — need 3.9+")

    # Platform
    check(sys.platform == "win32", "Platform: Windows",
          f"Platform: {sys.platform} — Windows required for Interception/SendInput")

    # Virtual env
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    check("warn" if not in_venv else True,
          "Virtual environment active",
          "",
          "No virtual environment detected — recommended to isolate deps")


# ── 2. Required packages ──────────────────────────────────────────────────────
def check_imports():
    section("2. Package Imports")

    packages = [
        ("numpy",       "numpy",             True,  None),
        ("cv2",         "opencv-python",     True,  None),
        ("PIL",         "Pillow",            True,  None),
        ("mss",         "mss",               True,  None),
        ("scipy",       "scipy",             True,  None),
        ("easyocr",     "easyocr",           False, "OCR features unavailable without easyocr"),
        ("rapidfuzz",   "rapidfuzz",         False, "Fuzzy text match unavailable"),
        ("customtkinter","customtkinter",     False, "GUI will use plain tkinter fallback"),
        ("psutil",      "psutil",            False, "Process utilities unavailable"),
    ]

    for mod, pkg, required, warn_text in packages:
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", "?")
            ok(f"{pkg} ({ver})")
            RESULTS["pass"] += 1
        except ImportError:
            if required:
                fail(f"{pkg} — REQUIRED: pip install {pkg}")
                RESULTS["fail"] += 1
            else:
                warn(warn_text or f"{pkg} not installed (optional)")
                RESULTS["warn"] += 1

    # Windows-specific
    try:
        import ctypes
        ctypes.windll.user32.GetSystemMetrics(0)
        ok("ctypes.windll (Windows API accessible)")
        RESULTS["pass"] += 1
    except Exception as e:
        fail(f"ctypes.windll not accessible: {e}")
        RESULTS["fail"] += 1

    # Interception (optional, hardware-level)
    try:
        import interception
        ok("interception-python (hardware-level input available)")
        RESULTS["pass"] += 1
    except ImportError:
        warn("interception-python not installed — will use SendInput fallback (lower stealth)")
        RESULTS["warn"] += 1


# ── 3. Internal module imports ────────────────────────────────────────────────
def check_internal_imports():
    section("3. Internal Module Imports")

    core_modules = [
        "core.screen_capture",
        "core.vision",
        "core.color_detection",
        "core.ocr",
        "core.input_handler",
        "core.inventory",
        "core.bank",
        "core.minimap",
        "core.camera",
        "core.player_state",
        "core.game_state",
        "core.antiban",
        "core.overlay",
        "core.random_events",
        "core.interfaces",
        "core.pathfinding",
        "core.engine",
    ]

    gui_modules = [
        "gui.hub",
        "gui.log_viewer",
        "gui.stats_tracker",
        "gui.script_panel",
        "gui.overlay_widgets",
    ]

    script_modules = [
        "scripts.base_script",
        "scripts.mining.mining_script",
        "scripts.woodcutting.woodcutting_script",
        "scripts.fishing.fishing_script",
        "scripts.cooking.cooking_script",
        "scripts.firemaking.firemaking_script",
        "scripts.smithing.smithing_script",
        "scripts.smithing.smelting",
        "scripts.smithing.anvil_smithing",
        "scripts.agility.agility_script",
        "scripts.agility.rooftop_courses",
        "scripts.thieving.thieving_script",
        "scripts.thieving.pickpocketing",
        "scripts.thieving.stall_thieving",
        "scripts.fletching.fletching_script",
        "scripts.fletching.bow_fletching",
        "scripts.fletching.arrow_fletching",
        "scripts.fletching.bolt_fletching",
        "scripts.herblore.herblore_script",
        "scripts.herblore.cleaning",
        "scripts.herblore.potion_making",
        "scripts.runecrafting.runecrafting_script",
        "scripts.hunter.hunter_script",
        "scripts.hunter.chinchompas",
        "scripts.hunter.birdhouse_runs",
        "scripts.farming.farming_script",
        "scripts.farming.herb_runs",
        "scripts.farming.tree_runs",
        "scripts.construction.construction_script",
        "scripts.prayer.prayer_script",
        "scripts.crafting.crafting_script",
    ]

    all_mods = [("Core", core_modules), ("GUI", gui_modules), ("Scripts", script_modules)]

    for category, mods in all_mods:
        print(f"\n  [{category}]")
        for m in mods:
            try:
                import importlib
                importlib.import_module(m)
                ok(m)
                RESULTS["pass"] += 1
            except Exception as e:
                fail(f"{m} — {type(e).__name__}: {e}")
                RESULTS["fail"] += 1


# ── 4. Config files ───────────────────────────────────────────────────────────
def check_configs():
    section("4. Config Files")

    files = [
        ("config.json",             True),
        ("profiles/default.json",   True),
        ("profiles/aggressive.json", False),
        ("profiles/casual.json",     False),
        ("data/locations.json",     True),
        ("data/xp_tables.json",     True),
        ("data/items.json",         False),
        ("data/objects.json",       False),
    ]

    for path, required in files:
        full = os.path.join(_HERE, path)
        if not os.path.exists(full):
            if required:
                fail(f"{path} — MISSING (required)")
                RESULTS["fail"] += 1
            else:
                warn(f"{path} — missing (optional)")
                RESULTS["warn"] += 1
            continue

        try:
            with open(full) as f:
                data = json.load(f)
            ok(f"{path} ({len(str(data))} bytes parsed)")
            RESULTS["pass"] += 1
        except json.JSONDecodeError as e:
            fail(f"{path} — INVALID JSON: {e}")
            RESULTS["fail"] += 1

    # Deep check config.json fields
    cfg_path = os.path.join(_HERE, "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path) as f:
                cfg = json.load(f)
            required_keys = ["input_method", "capture_method", "regions"]
            for k in required_keys:
                if k in cfg:
                    ok(f"config.json has '{k}' = {str(cfg[k])[:60]}")
                    RESULTS["pass"] += 1
                else:
                    fail(f"config.json missing required key: '{k}'")
                    RESULTS["fail"] += 1
            # Accept either the legacy single-title key or the new list form
            if "game_window_titles" in cfg:
                titles = cfg["game_window_titles"]
                ok(f"config.json has 'game_window_titles' = {titles}")
                RESULTS["pass"] += 1
            elif "game_window_title" in cfg:
                ok(f"config.json has 'game_window_title' = {cfg['game_window_title']}")
                RESULTS["pass"] += 1
            else:
                warn("config.json has no window title key — built-in defaults will be used")
                RESULTS["warn"] += 1
        except Exception:
            pass


# ── 5. Profile validation ─────────────────────────────────────────────────────
def check_profiles():
    section("5. Anti-Ban Profiles")

    required_fields = [
        "break_enabled", "break_interval_min", "break_interval_max",
        "break_duration_min", "break_duration_max",
        "micro_break_chance", "afk_chance", "misclick_chance",
        "camera_move_chance", "fatigue_enabled", "fatigue_curve",
        "session_max_hours", "action_delay_min", "action_delay_max"
    ]

    for profile_file in ["default.json", "aggressive.json", "casual.json"]:
        path = os.path.join(_HERE, "profiles", profile_file)
        if not os.path.exists(path):
            warn(f"profiles/{profile_file} not found")
            RESULTS["warn"] += 1
            continue
        with open(path) as f:
            p = json.load(f)
        missing = [k for k in required_fields if k not in p]
        if missing:
            fail(f"profiles/{profile_file} missing: {', '.join(missing)}")
            RESULTS["fail"] += 1
        else:
            ok(f"profiles/{profile_file} — all {len(required_fields)} required fields present")
            RESULTS["pass"] += 1


# ── 6. Locations database ─────────────────────────────────────────────────────
def check_locations():
    section("6. Locations Database")
    path = os.path.join(_HERE, "data", "locations.json")
    if not os.path.exists(path):
        fail("data/locations.json not found"); RESULTS["fail"] += 1; return

    with open(path) as f:
        locs = json.load(f)

    # Check all locations referenced in scripts exist
    important_locs = [
        "grand_exchange_bank", "edgeville_bank", "falador_east_bank",
        "castle_wars_bank", "al_kharid_bank", "lumbridge_bank",
        "edgeville_furnace", "falador_furnace", "falador_anvil", "varrock_anvil",
        "al_kharid_range", "lumbridge_range",
        "air_altar", "fire_altar", "nature_altar", "law_altar",
        "gnome_stronghold", "draynor_agility", "falador_agility",
        "gilded_altar_house", "house_party_bank",
        "piscatoris", "feldip_hills",
        "falador_farm", "ardougne_farm", "catherby_farm",
        "farming_guild", "hosidius_farm",
    ]
    missing = [l for l in important_locs if l not in locs]
    if missing:
        fail(f"Missing locations: {', '.join(missing)}")
        RESULTS["fail"] += 1
    else:
        ok(f"All {len(important_locs)} key locations present ({len(locs)} total)")
        RESULTS["pass"] += 1


# ── 7. Asset templates ────────────────────────────────────────────────────────
def check_assets():
    section("7. Asset Templates (screenshots)")

    tmpl_dir = os.path.join(_HERE, "assets", "templates")
    manifest_path = os.path.join(tmpl_dir, "TEMPLATE_MANIFEST.json")

    if not os.path.exists(tmpl_dir):
        fail("assets/templates/ directory missing"); RESULTS["fail"] += 1; return

    # Count actual png files
    png_count = 0
    for root, dirs, files in os.walk(tmpl_dir):
        for f in files:
            if f.lower().endswith(".png"):
                png_count += 1

    if png_count == 0:
        warn("No template PNG files found — vision-based detection will fail at runtime")
        warn("Take screenshots per assets/README.md and assets/templates/TEMPLATE_MANIFEST.json")
        RESULTS["warn"] += 1
    else:
        ok(f"{png_count} template PNG files found")
        RESULTS["pass"] += 1

    # Check manifest
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
        total = 0; captured = 0
        for category, items in manifest.items():
            if category.startswith("_"): continue
            if isinstance(items, dict):
                for subcat, entries in items.items():
                    if isinstance(entries, list):
                        for e in entries:
                            total += 1
                            if e.get("captured"): captured += 1
            elif isinstance(items, list):
                for e in items:
                    total += 1
                    if e.get("captured"): captured += 1
        info(f"Template manifest: {captured}/{total} templates captured")
        if captured == 0:
            warn("No templates marked as captured — update TEMPLATE_MANIFEST.json as you go")
            RESULTS["warn"] += 1
        else:
            ok(f"{captured}/{total} templates ready ({100*captured//total}%)")
            RESULTS["pass"] += 1
    else:
        warn("TEMPLATE_MANIFEST.json missing — create it to track template progress")
        RESULTS["warn"] += 1


# ── 8. Screen capture test ────────────────────────────────────────────────────
def check_screen_capture(fast=False):
    section("8. Screen Capture")
    if fast:
        info("Skipped (--fast mode)"); return

    try:
        from core.screen_capture import ScreenCapture
        import json
        with open(os.path.join(_HERE, "config.json")) as f:
            cfg = json.load(f)
        cap = ScreenCapture(cfg)
        import time
        t0 = time.time()
        frame = cap.grab_full()
        dt = (time.time() - t0) * 1000
        if frame is not None:
            h, w = frame.shape[:2]
            ok(f"Screen captured: {w}×{h} in {dt:.1f}ms")
            RESULTS["pass"] += 1
        else:
            fail("grab_full() returned None")
            RESULTS["fail"] += 1
    except Exception as e:
        fail(f"Screen capture failed: {type(e).__name__}: {e}")
        info("  Is the game running? Is 'mss' installed?")
        RESULTS["fail"] += 1


# ── 9. Input handler test ─────────────────────────────────────────────────────
def check_input(fast=False):
    section("9. Input Handler")
    if fast:
        info("Skipped (--fast mode)"); return

    try:
        from core.input_handler import HumanizedInput
        import json
        with open(os.path.join(_HERE, "config.json")) as f:
            cfg = json.load(f)
        inp = HumanizedInput(cfg)
        pos = inp.get_position()
        ok(f"Mouse position readable: {pos}")
        RESULTS["pass"] += 1

        # Check drag has middle support
        import inspect
        src = inspect.getsource(inp.drag)
        if "middle" in src:
            ok("drag() supports middle mouse button")
            RESULTS["pass"] += 1
        else:
            fail("drag() missing middle mouse support (camera will crash)")
            RESULTS["fail"] += 1
    except Exception as e:
        fail(f"Input handler init failed: {type(e).__name__}: {e}")
        RESULTS["fail"] += 1


# ── 10. Engine init test ──────────────────────────────────────────────────────
def check_engine(fast=False):
    section("10. Engine Init")
    if fast:
        info("Skipped (--fast mode)"); return

    try:
        from core.engine import Engine
        e = Engine(os.path.join(_HERE, "config.json"))
        ok(f"Engine initialized: {type(e).__name__}")
        RESULTS["pass"] += 1

        # Check all subsystems are accessible
        subsystems = ["capture", "vision", "input", "color", "ocr",
                      "inventory", "bank", "minimap", "camera",
                      "player", "game_state", "antiban", "overlay",
                      "random_events", "interfaces", "pathfinder"]
        missing = [s for s in subsystems if not hasattr(e, s)]
        if missing:
            fail(f"Engine missing subsystems: {', '.join(missing)}")
            RESULTS["fail"] += 1
        else:
            ok(f"All {len(subsystems)} engine subsystems present")
            RESULTS["pass"] += 1
    except Exception as e:
        fail(f"Engine init failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        RESULTS["fail"] += 1


# ── 11. Script instantiation test ─────────────────────────────────────────────
def check_script_init():
    section("11. Script Class Instantiation (mock engine)")

    class MockPlayer:
        def update(self, *a): pass
        def is_idle(self): return True
        def time_idle(self): return 10
        def wait_until_idle(self, timeout=10): pass
        health = 1.0; prayer = 1.0

    class MockAntiban:
        def sleep_action(self): pass
        def reaction_delay(self): return 0.1
        def should_move_camera(self): return False

    class MockEngine:
        player = MockPlayer()
        antiban = MockAntiban()
        def screenshot(self): return None
        class vision:
            @staticmethod
            def find_template(*a, **kw): return None
            @staticmethod
            def find_all_templates(*a, **kw): return []
        class inventory:
            @staticmethod
            def scan(*a): pass
            @staticmethod
            def find_item(*a): return None
            @staticmethod
            def find_all_items(*a): return []
            @staticmethod
            def is_empty(): return False
            @staticmethod
            def get_filled_slots(): return []
        class bank:
            @staticmethod
            def is_open(): return False
            @staticmethod
            def wait_for_open(*a): return False
        class interfaces:
            @staticmethod
            def is_make_interface_open(*a): return False
        class pathfinder:
            @staticmethod
            def walk_to_named(*a, **kw): return True
        class camera:
            @staticmethod
            def set_max_pitch(): pass
            @staticmethod
            def random_adjustment(): pass
        class input:
            @staticmethod
            def click(*a, **kw): pass
            @staticmethod
            def right_click(*a, **kw): pass
        class game_state:
            health = 1.0; xp_gained = {}
        class color:
            pass
        class ocr:
            pass

    mock = MockEngine()

    scripts_to_test = {
        "scripts.mining.mining_script":              ("MiningScript",      {"ore_type": "iron", "power_mine": True}),
        "scripts.woodcutting.woodcutting_script":    ("WoodcuttingScript", {"tree_type": "oak", "power_chop": True}),
        "scripts.fishing.fishing_script":            ("FishingScript",     {"fish_type": "lobster"}),
        "scripts.cooking.cooking_script":            ("CookingScript",     {}),
        "scripts.firemaking.firemaking_script":      ("FiremakingScript",  {}),
        "scripts.smithing.smelting":                 ("SmeltingScript",    {}),
        "scripts.smithing.anvil_smithing":           ("AnvilSmithingScript",{}),
        "scripts.agility.agility_script":            ("AgilityScript",     {"course": "gnome_stronghold"}),
        "scripts.thieving.pickpocketing":            ("PickpocketScript",  {}),
        "scripts.thieving.stall_thieving":           ("StallThievingScript",{}),
        "scripts.fletching.bow_fletching":           ("BowFletchingScript",{}),
        "scripts.fletching.arrow_fletching":         ("ArrowFletchingScript",{}),
        "scripts.fletching.bolt_fletching":          ("BoltFletchingScript",{}),
        "scripts.herblore.cleaning":                 ("CleaningScript",    {}),
        "scripts.herblore.potion_making":            ("PotionMakingScript",{}),
        "scripts.runecrafting.runecrafting_script":  ("RunecraftingScript",{}),
        "scripts.hunter.chinchompas":                ("ChinchompaScript",  {}),
        "scripts.hunter.birdhouse_runs":             ("BirdhouseScript",   {}),
        "scripts.farming.herb_runs":                 ("HerbRunScript",     {}),
        "scripts.farming.tree_runs":                 ("TreeRunScript",     {}),
        "scripts.construction.construction_script":  ("ConstructionScript",{}),
        "scripts.prayer.prayer_script":              ("PrayerScript",      {}),
        "scripts.crafting.crafting_script":          ("CraftingScript",    {}),
    }

    import importlib
    for mod_path, (cls_name, cfg) in scripts_to_test.items():
        try:
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, cls_name)
            inst = cls(mock, cfg)
            paint = inst.get_paint_data()
            ok(f"{cls_name} init OK, paint={list(paint.keys())[:3]}")
            RESULTS["pass"] += 1
        except Exception as e:
            fail(f"{cls_name}: {type(e).__name__}: {e}")
            RESULTS["fail"] += 1


# ── 12. Game window detection ─────────────────────────────────────────────────
def check_window():
    section("12. Game Window Detection")
    try:
        import ctypes

        # Build search list from config (supports both old single-string key
        # and new game_window_titles list). Built-in defaults always present.
        cfg_titles = []
        try:
            with open(os.path.join(_HERE, "config.json")) as f:
                cfg = json.load(f)
            cfg_titles = cfg.get("game_window_titles") or []
            if not cfg_titles:
                legacy = cfg.get("game_window_title")
                if legacy:
                    cfg_titles = [legacy]
        except Exception:
            pass

        default_titles = ["RuneLite", "Old School RuneScape", "HDOS"]
        seen: set = set()
        search_titles: list = []
        for t in cfg_titles + default_titles:
            if t.lower() not in seen:
                seen.add(t.lower())
                search_titles.append(t)

        info(f"Searching for clients: {search_titles}")

        import win32gui

        # Collect all visible windows via win32gui (avoids ctypes callback quirks)
        visible = []
        def _collect(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if t:
                    visible.append((hwnd, t))
        win32gui.EnumWindows(_collect, None)

        found_hwnd    = None
        found_title   = ""
        found_client  = ""
        for ct in search_titles:
            needle = ct.lower()
            for hwnd, title in visible:
                if needle in title.lower():
                    found_hwnd   = hwnd
                    found_title  = title
                    found_client = ct
                    break
            if found_hwnd:
                break

        if found_hwnd:
            ok(f"Game window found via '{found_client}' — title: \"{found_title}\"  HWND={found_hwnd:#010x}")
            RESULTS["pass"] += 1
            rect = win32gui.GetWindowRect(found_hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            info(f"Window position: ({rect[0]},{rect[1]})  size: {w}\u00d7{h}")
            if w < 765 or h < 503:
                warn(f"Window size {w}\u00d7{h} is below minimum 765\u00d7503")
                RESULTS["warn"] += 1
        else:
            warn(f"No game client found.  Searched for: {search_titles}")
            warn("Start RuneLite or the official OSRS client, then re-run diagnose.py")
            RESULTS["warn"] += 1

    except Exception as e:
        warn(f"Window check error: {e}")
        RESULTS["warn"] += 1


# ── Summary ───────────────────────────────────────────────────────────────────
def print_summary():
    section("SUMMARY")
    total = sum(RESULTS.values())
    p, w, f = RESULTS["pass"], RESULTS["warn"], RESULTS["fail"]
    print(f"\n  {GREEN}PASS{RESET}: {p}   {YELLOW}WARN{RESET}: {w}   {RED}FAIL{RESET}: {f}   (Total: {total})")
    if f == 0 and w == 0:
        print(f"\n  {GREEN}{BOLD}All checks passed — suite is ready!{RESET}")
    elif f == 0:
        print(f"\n  {YELLOW}{BOLD}Ready with warnings — review WARN items above before running.{RESET}")
    else:
        print(f"\n  {RED}{BOLD}{f} critical issue(s) — fix FAIL items before running scripts.{RESET}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="OSRS Suite Diagnostic")
    parser.add_argument("--fast",    action="store_true", help="Skip screen/input/engine tests")
    parser.add_argument("--section", type=str, default=None,
                        help="Run only one section: imports|internal|configs|profiles|locations|assets|screen|input|engine|scripts|window")
    args = parser.parse_args()

    print(f"\n{BOLD}OSRS Automation Suite — Diagnostic{RESET}")
    print(f"Python: {sys.version}")
    print(f"CWD:    {os.getcwd()}")
    print(f"Suite:  {_HERE}")

    s = args.section

    if not s or s == "python":    check_python()
    if not s or s == "imports":   check_imports()
    if not s or s == "internal":  check_internal_imports()
    if not s or s == "configs":   check_configs()
    if not s or s == "profiles":  check_profiles()
    if not s or s == "locations": check_locations()
    if not s or s == "assets":    check_assets()
    if not s or s == "screen":    check_screen_capture(fast=args.fast)
    if not s or s == "input":     check_input(fast=args.fast)
    if not s or s == "engine":    check_engine(fast=args.fast)
    if not s or s == "scripts":   check_script_init()
    if not s or s == "window":    check_window()

    print_summary()
    sys.exit(1 if RESULTS["fail"] > 0 else 0)


if __name__ == "__main__":
    main()
