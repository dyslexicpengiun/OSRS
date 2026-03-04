"""
Central Hub GUI
Main control panel — integrates ScriptPanel, LogViewer, StatsTracker.
Run via: python main.py
"""

import time
import threading
import logging
import json
import importlib
from typing import Optional, Dict

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    CTK = True
except ImportError:
    import tkinter as ctk
    CTK = False

from gui.script_panel import ScriptPanel, SCRIPT_SCHEMAS
from gui.log_viewer import LogViewer
from gui.stats_tracker import StatsTracker

logger = logging.getLogger(__name__)

SCRIPT_REGISTRY: Dict[str, tuple] = {
    "Mining":        ("scripts.mining.mining_script",           "MiningScript"),
    "Woodcutting":   ("scripts.woodcutting.woodcutting_script", "WoodcuttingScript"),
    "Fishing":       ("scripts.fishing.fishing_script",         "FishingScript"),
    "Cooking":       ("scripts.cooking.cooking_script",         "CookingScript"),
    "Firemaking":    ("scripts.firemaking.firemaking_script",   "FiremakingScript"),
    "Smithing":      ("scripts.smithing.smithing_script",       "SmithingScript"),
    "Agility":       ("scripts.agility.agility_script",         "AgilityScript"),
    "Thieving":      ("scripts.thieving.thieving_script",       "ThievingScript"),
    "Fletching":     ("scripts.fletching.fletching_script",     "FletchingScript"),
    "Herblore":      ("scripts.herblore.herblore_script",       "HerbloreScript"),
    "Runecrafting":  ("scripts.runecrafting.runecrafting_script","RunecraftingScript"),
    "Hunter":        ("scripts.hunter.hunter_script",           "HunterScript"),
    "Farming":       ("scripts.farming.farming_script",         "FarmingScript"),
    "Construction":  ("scripts.construction.construction_script","ConstructionScript"),
    "Prayer":        ("scripts.prayer.prayer_script",           "PrayerScript"),
    "Crafting":      ("scripts.crafting.crafting_script",       "CraftingScript"),
}


class HubGUI:
    WIN_W, WIN_H = 1100, 700

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self._engine = None
        self._active_script = None
        self._engine_lock = threading.Lock()

        self.root = ctk.CTk() if CTK else ctk.Tk()
        self.root.title("OSRS Automation Suite v1.0")
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}")
        self.root.resizable(True, True)

        self._build_ui()
        self._wire_logging()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        header = self._frame(self.root, fill="x", padx=10, pady=(8, 0))
        self._label(header, "OSRS Automation Suite", size=18, bold=True, side="left")
        self._button(header, "Config", self._open_global_config, width=80, side="right")
        self._button(header, "About",  self._show_about,         width=70, side="right")

        body = self._frame(self.root, fill="both", expand=True, padx=10, pady=4)

        left = ctk.CTkFrame(body, width=270) if CTK else ctk.Frame(body, width=270)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)
        self._build_left(left)

        right = self._frame(body, side="right", fill="both", expand=True)
        self._build_right(right)

        self._status_var = ctk.StringVar(value="Status: Idle")
        self._eng_var    = ctk.StringVar(value="Engine: Offline")
        sbar = self._frame(self.root, fill="x", padx=10, pady=(2, 6))
        self._label(sbar, "", textvariable=self._status_var, side="left")
        self._label(sbar, "", textvariable=self._eng_var,    side="right")

    def _build_left(self, p):
        self._label(p, "Script", bold=True, padx=8, pady=(8, 2))
        self._script_var = ctk.StringVar(value="Mining")
        scripts = sorted(SCRIPT_REGISTRY.keys())
        if CTK:
            ctk.CTkComboBox(p, values=scripts, variable=self._script_var,
                             width=250, command=self._on_script_change).pack(padx=8, pady=4)
        else:
            import tkinter.ttk as ttk
            cb = ttk.Combobox(p, values=scripts, textvariable=self._script_var, width=32)
            cb.pack(padx=8, pady=4)
            self._script_var.trace_add("write", lambda *_: self._on_script_change())

        self._label(p, "Config", bold=True, padx=8, pady=(6, 2))
        self._script_panel = ScriptPanel(p, self._script_var.get())
        self._script_panel.pack(fill="x", padx=4, pady=2)

        r1 = self._frame(p, padx=8, pady=6)
        self._start_btn = self._button(r1, "Start", self._start_script,
                                        color="green", width=115, side="left")
        self._stop_btn  = self._button(r1, "Stop",  self._stop_script,
                                        color="red",   width=115, side="left",
                                        state="disabled")
        r2 = self._frame(p, padx=8, pady=0)
        self._pause_btn = self._button(r2, "Pause", self._pause_resume,
                                        width=115, side="left", state="disabled")
        self._button(r2, "Reset Engine", self._restart_engine,
                     width=125, side="left")

        self._label(p, "Quick Stats", bold=True, padx=8, pady=(10, 2))
        self._qs_var = ctk.StringVar(value="—")
        lbl = ctk.CTkLabel(p, textvariable=self._qs_var,
                            font=("Consolas", 10), justify="left", anchor="nw") if CTK \
            else ctk.Label(p, textvariable=self._qs_var,
                            font=("Consolas", 10), justify="left", anchor="nw")
        lbl.pack(padx=12, pady=2, fill="x")

    def _build_right(self, p):
        if CTK:
            tabs = ctk.CTkTabview(p)
            tabs.pack(fill="both", expand=True)
            tabs.add("Log")
            tabs.add("Stats")
            log_p   = tabs.tab("Log")
            stats_p = tabs.tab("Stats")
        else:
            import tkinter.ttk as ttk
            nb = ttk.Notebook(p)
            nb.pack(fill="both", expand=True)
            log_p   = ctk.Frame(nb)
            stats_p = ctk.Frame(nb)
            nb.add(log_p,   text="Log")
            nb.add(stats_p, text="Stats")

        self._log_viewer    = LogViewer(log_p, height=560)
        self._log_viewer.pack(fill="both", expand=True)
        self._stats_tracker = StatsTracker(stats_p,
                                            stats_provider=self._get_stats)
        self._stats_tracker.pack(fill="both", expand=True, padx=8, pady=8)

    # ------------------------------------------------------------------
    def _on_script_change(self, *_):
        self._script_panel.switch_script(self._script_var.get())

    def _start_script(self):
        if self._active_script and self._active_script.is_running:
            return
        name = self._script_var.get()
        if name not in SCRIPT_REGISTRY:
            return
        cfg = self._script_panel.get_config()
        if not self._ensure_engine():
            return
        mod_path, cls_name = SCRIPT_REGISTRY[name]
        try:
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, cls_name)
            self._active_script = cls(self._engine, cfg)
            self._active_script.start()
            self._status_var.set(f"Status: Running — {name}")
            self._eng_var.set("Engine: Running")
            self._set_btns(True)
            logger.info(f"[Hub] Started: {name}")
        except Exception as e:
            logger.exception(f"[Hub] Start failed: {e}")

    def _stop_script(self):
        if self._active_script:
            self._active_script.stop()
        self._status_var.set("Status: Idle")
        self._set_btns(False)

    def _pause_resume(self):
        if not self._engine: return
        if self._engine.is_paused:
            self._engine.resume()
            txt = "Pause"
        else:
            self._engine.pause()
            txt = "Resume"
        try:
            self._pause_btn.configure(text=txt)
        except Exception:
            pass

    def _restart_engine(self):
        with self._engine_lock:
            if self._active_script:
                try: self._active_script.stop()
                except Exception: pass
                self._active_script = None
            if self._engine:
                try: self._engine.stop()
                except Exception: pass
                self._engine = None
        self._eng_var.set("Engine: Offline")
        self._set_btns(False)

    def _ensure_engine(self) -> bool:
        with self._engine_lock:
            if self._engine and self._engine.is_running:
                return True
            try:
                from core.engine import Engine
                self._engine = Engine(self.config_path)
                self._engine.start()
                self._eng_var.set("Engine: Online")
                return True
            except Exception as e:
                logger.exception(f"[Hub] Engine init: {e}")
                self._eng_var.set("Engine: ERROR")
                return False

    def _get_stats(self):
        return self._active_script.stats if self._active_script else None

    def _update_quick_stats(self):
        if self._active_script and self._active_script.is_running:
            s = self._active_script.stats
            el = time.time() - s.start_time
            eh = el / 3600 or 1e-6
            h, m, sec = int(el//3600), int((el%3600)//60), int(el%60)
            self._qs_var.set(
                f"Runtime:  {h}:{m:02d}:{sec:02d}\n"
                f"Items:    {s.items_gained:,} ({s.items_gained/eh:.0f}/hr)\n"
                f"Actions:  {s.actions_performed:,}\n"
                f"Errors:   {s.errors}"
            )
        else:
            self._qs_var.set("No script running")
        self.root.after(1000, self._update_quick_stats)

    def _open_global_config(self):
        w = ctk.CTkToplevel(self.root) if CTK else ctk.Toplevel(self.root)
        w.title("Global Config")
        w.geometry("520x420")
        try:
            with open(self.config_path) as f: content = f.read()
        except Exception: content = "{}"
        txt = ctk.CTkTextbox(w, font=("Consolas", 11)) if CTK \
            else ctk.Text(w, font=("Consolas", 11))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        (txt.insert("0.0", content) if CTK else txt.insert("1.0", content))
        def save():
            raw = txt.get("0.0","end") if CTK else txt.get("1.0","end")
            try:
                parsed = json.loads(raw)
                with open(self.config_path,"w") as f: json.dump(parsed, f, indent=4)
                logger.info("[Hub] Config saved.")
                w.destroy()
            except json.JSONDecodeError as e:
                logger.error(f"[Hub] Bad JSON: {e}")
        self._button(w, "Save", save, color="green").pack(pady=4)

    def _show_about(self):
        w = ctk.CTkToplevel(self.root) if CTK else ctk.Toplevel(self.root)
        w.title("About"); w.geometry("360x180")
        lbl = ctk.CTkLabel(w,
            text="OSRS Automation Suite v1.0\n\nEducational reverse-engineering project.\n"
                 "Demonstrates CV, input simulation, state machines.\n\nNot affiliated with Jagex Ltd.",
            justify="center") if CTK else ctk.Label(w,
            text="OSRS Automation Suite v1.0\n\nEducational project. Not affiliated with Jagex.",
            justify="center")
        lbl.pack(expand=True)

    def _wire_logging(self):
        h = self._log_viewer.make_handler()
        h.setLevel(logging.DEBUG)
        h.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        logging.getLogger().addHandler(h)
        logging.getLogger().setLevel(logging.DEBUG)

    def _set_btns(self, running: bool):
        for btn, st in [(self._start_btn, "disabled" if running else "normal"),
                         (self._stop_btn,  "normal"   if running else "disabled"),
                         (self._pause_btn, "normal"   if running else "disabled")]:
            try: btn.configure(state=st)
            except Exception: pass

    def _frame(self, p, side=None, fill=None, expand=False, padx=0, pady=0):
        f = ctk.CTkFrame(p) if CTK else ctk.Frame(p)
        kw = {}
        if side:   kw["side"]   = side
        if fill:   kw["fill"]   = fill
        if expand: kw["expand"] = expand
        if padx:   kw["padx"]   = padx
        if pady:   kw["pady"]   = pady
        f.pack(**kw)
        return f

    def _label(self, p, text="", size=12, bold=False, side=None,
               textvariable=None, padx=0, pady=0):
        w = "bold" if bold else "normal"
        kw_p = {}
        if side: kw_p["side"] = side
        if padx: kw_p["padx"] = padx
        if pady: kw_p["pady"] = pady
        if CTK:
            kw = {"font": ("Segoe UI", size, w)}
            if textvariable: kw["textvariable"] = textvariable
            else:            kw["text"] = text
            lbl = ctk.CTkLabel(p, **kw)
        else:
            kw = {"font": ("Segoe UI", size)}
            if textvariable: kw["textvariable"] = textvariable
            else:            kw["text"] = text
            lbl = ctk.Label(p, **kw)
        lbl.pack(**kw_p)
        return lbl

    def _button(self, p, text, cmd, color=None, width=None, side=None, state="normal"):
        kw_p = {"padx": 3, "pady": 3}
        if side: kw_p["side"] = side
        if CTK:
            kw = {"command": cmd, "state": state}
            if width: kw["width"] = width
            if color == "green": kw["fg_color"] = "#1a5c1a"
            elif color == "red": kw["fg_color"] = "#5c1a1a"
            btn = ctk.CTkButton(p, text=text, **kw)
        else:
            btn = ctk.Button(p, text=text, command=cmd, state=state)
        btn.pack(**kw_p)
        return btn

    def run(self):
        self.root.after(1000, self._update_quick_stats)
        self.root.mainloop()

    def _on_close(self):
        try:
            if self._active_script: self._active_script.stop()
            if self._engine:        self._engine.stop()
        except Exception: pass
        self.root.destroy()
