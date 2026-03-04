"""
OSRS Template Capture Tool
==========================
A guided GUI tool for capturing all required template images from the OSRS client.

Features:
  - Monitor picker in the header — choose any display, not just the primary
  - Full manifest-driven capture queue with progress tracking
  - Live region preview (updates every 500ms from the selected monitor)
  - Drag-to-select capture region positioned on the correct monitor
  - On-capture validation using OpenCV template matching
  - Instant feedback — pass/fail confidence score shown after each save
  - Manifest auto-updated (captured: true) on successful save
  - Skip / re-capture / jump-to-any workflow

Requirements (all in suite requirements.txt):
  pip install mss opencv-python Pillow customtkinter numpy

Usage:
  python template_capture.py
  python template_capture.py --assets path/to/assets   (default: ./assets)
  python template_capture.py --threshold 0.75          (match threshold, default 0.80)
"""

import os
import re
import sys
import json
import time
import argparse
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import numpy as np

try:
    import cv2
except ImportError:
    sys.exit("ERROR: opencv-python not installed. Run: pip install opencv-python")

try:
    from PIL import Image, ImageTk
except ImportError:
    sys.exit("ERROR: Pillow not installed. Run: pip install Pillow")

try:
    import mss
    import mss.tools
except ImportError:
    sys.exit("ERROR: mss not installed. Run: pip install mss")

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    USE_CTK = True
except ImportError:
    USE_CTK = False

# Colour palette
BG       = "#0f1117"
BG2      = "#1a1d2e"
BG3      = "#242840"
ACCENT   = "#5865f2"
ACCENT2  = "#7289da"
SUCCESS  = "#3ba55c"
WARNING  = "#faa61a"
TEXT     = "#dcddde"
TEXT_DIM = "#72767d"
BORDER   = "#2f3349"
GOLD     = "#c8aa5e"


# ── Monitor enumeration ───────────────────────────────────────────────────────
def get_monitors() -> List[Dict]:
    """Return list of mss monitor dicts, 0-indexed (excludes the virtual combined desktop)."""
    with mss.mss() as sct:
        return list(sct.monitors[1:])   # monitors[0] is the combined bounding box


def monitor_label(idx_1based: int, mon: Dict) -> str:
    return f"Display {idx_1based}  ({mon['width']}x{mon['height']}  @ {mon['left']},{mon['top']})"


# ── Manifest helpers ──────────────────────────────────────────────────────────
def load_manifest(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

def save_manifest(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def flatten_manifest(manifest: dict) -> List[Dict]:
    entries = []
    def _walk(obj):
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict) and "file" in item:
                    entries.append(item)
                else:
                    _walk(item)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if not k.startswith("_"):
                    _walk(v)
    _walk(manifest)
    return entries

def mark_captured(manifest: dict, file_path: str) -> dict:
    def _walk(obj):
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict) and item.get("file") == file_path:
                    item["captured"] = True
                elif isinstance(item, dict):
                    _walk(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
    _walk(manifest)
    return manifest



def variant_base(file_path: str) -> str:
    """
    Return the base name of a numbered variant, or the path itself if not a variant.
    e.g. "objects/trees/tree_oak_2.png" -> "objects/trees/tree_oak"
         "inventory/lobster.png"        -> "inventory/lobster.png"
    """
    stem = file_path.rsplit(".", 1)[0]   # strip extension
    m = re.match(r"^(.*?)_([0-9]+)$", stem)
    return m.group(1) if m else stem

# ── Screen capture ────────────────────────────────────────────────────────────
def grab_region(x: int, y: int, w: int, h: int) -> np.ndarray:
    """Grab an arbitrary screen region using absolute coordinates."""
    with mss.mss() as sct:
        img = sct.grab({"top": y, "left": x, "width": w, "height": h})
        return cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)

def grab_monitor(monitor_1based_idx: int) -> np.ndarray:
    """Grab a full monitor by its 1-based mss index."""
    with mss.mss() as sct:
        idx = max(1, min(monitor_1based_idx, len(sct.monitors) - 1))
        img = sct.grab(sct.monitors[idx])
        return cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)

def validate_template(template: np.ndarray, screen: np.ndarray,
                      threshold: float) -> Tuple[bool, float]:
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val >= threshold, float(max_val)


# ── Region selector overlay ───────────────────────────────────────────────────
class RegionSelector:
    """
    Transparent overlay placed exactly on the chosen monitor.
    Returns (x, y, w, h) in absolute screen coords, or None if cancelled.
    """
    def __init__(self, monitor: Dict):
        self.monitor = monitor
        self.result: Optional[Tuple[int, int, int, int]] = None

    def select(self) -> Optional[Tuple[int, int, int, int]]:
        mon = self.monitor
        root = tk.Toplevel()

        # Place the window exactly on the target monitor
        root.geometry(f"{mon['width']}x{mon['height']}+{mon['left']}+{mon['top']}")
        root.overrideredirect(True)
        root.attributes("-alpha", 0.30)
        root.attributes("-topmost", True)
        root.configure(bg="black")

        canvas = tk.Canvas(root, cursor="crosshair", bg="black", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        sw, sh = mon['width'], mon['height']
        canvas.create_rectangle(0, 0, sw, sh, fill="black", stipple="gray50", outline="")
        canvas.create_text(sw // 2, 40,
                           text="Drag to select region  |  ESC to cancel",
                           fill="white", font=("Consolas", 18, "bold"))

        start_x = start_y = 0
        rect_id = [None]

        def on_press(event):
            nonlocal start_x, start_y
            start_x, start_y = event.x_root, event.y_root
            if rect_id[0]:
                canvas.delete(rect_id[0])

        def on_drag(event):
            canvas.delete("size_label")
            if rect_id[0]:
                canvas.delete(rect_id[0])
            # x_root/y_root are absolute; convert to canvas-local coords
            cx0 = min(start_x, event.x_root) - mon['left']
            cy0 = min(start_y, event.y_root) - mon['top']
            cx1 = max(start_x, event.x_root) - mon['left']
            cy1 = max(start_y, event.y_root) - mon['top']
            rect_id[0] = canvas.create_rectangle(
                cx0, cy0, cx1, cy1,
                outline="#5865f2", width=2, fill="#5865f2", stipple="gray25"
            )
            canvas.create_text(
                (cx0 + cx1) / 2, (cy0 + cy1) / 2,
                text=f"{cx1 - cx0} x {cy1 - cy0}",
                fill="white", font=("Consolas", 13, "bold"),
                tags="size_label"
            )

        def on_release(event):
            x0 = min(start_x, event.x_root)
            y0 = min(start_y, event.y_root)
            x1 = max(start_x, event.x_root)
            y1 = max(start_y, event.y_root)
            if (x1 - x0) > 4 and (y1 - y0) > 4:
                self.result = (x0, y0, x1 - x0, y1 - y0)
            root.destroy()

        def on_escape(event):
            self.result = None
            root.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        root.bind("<Escape>", on_escape)
        root.focus_force()
        root.wait_window()
        return self.result


# ── Main application ──────────────────────────────────────────────────────────
class TemplateCaptureApp:

    PREVIEW_W = 320
    PREVIEW_H = 240
    LIVE_INTERVAL_MS = 500

    def __init__(self, assets_path: str, threshold: float):
        self.assets_path     = Path(assets_path)
        self.templates_path  = self.assets_path / "templates"
        self.manifest_path   = self.assets_path / "templates" / "TEMPLATE_MANIFEST.json"
        self.threshold       = threshold

        # Monitor state
        self.monitors: List[Dict] = get_monitors()
        if not self.monitors:
            sys.exit("ERROR: No monitors detected by mss.")
        self._sel_mon_idx: int = 0   # 0-based index into self.monitors

        # Capture state
        self.manifest: dict = {}
        self.entries:  List[Dict] = []
        self.current_idx: int = 0
        self.region:   Optional[Tuple[int, int, int, int]] = None
        self._live_running = False

        self._load_manifest()
        self._build_ui()
        self._refresh_queue()
        self._start_live_preview()

    @property
    def _active_monitor(self) -> Dict:
        return self.monitors[self._sel_mon_idx]

    @property
    def _active_mss_idx(self) -> int:
        return self._sel_mon_idx + 1   # mss is 1-based (0 = virtual desktop)

    # ── Manifest ──────────────────────────────────────────────────────────────
    def _load_manifest(self):
        if not self.manifest_path.exists():
            messagebox.showerror("Error", f"Manifest not found:\n{self.manifest_path}")
            sys.exit(1)
        self.manifest = load_manifest(str(self.manifest_path))
        self.entries  = flatten_manifest(self.manifest)

    def _save_manifest(self):
        save_manifest(str(self.manifest_path), self.manifest)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("OSRS Template Capture Tool")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(940, 660)

        self._font_title = ("Consolas", 15, "bold")
        self._font_body  = ("Consolas", 11)
        self._font_small = ("Consolas", 9)

        self._build_header()
        self._build_main()
        self._build_status_bar()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.update_idletasks()
        W, H = 980, 710
        self.root.geometry(
            f"{W}x{H}+"
            f"{(self.root.winfo_screenwidth()  - W) // 2}+"
            f"{(self.root.winfo_screenheight() - H) // 2}"
        )

    def _build_header(self):
        header = tk.Frame(self.root, bg=BG2, height=62)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="OSRS Template Capture Tool",
                 bg=BG2, fg=GOLD, font=("Consolas", 16, "bold")
                 ).pack(side=tk.LEFT, padx=18, pady=10)

        # ── Monitor picker (the key new widget) ───────────────────────────
        mon_frame = tk.Frame(header, bg=BG2)
        mon_frame.pack(side=tk.LEFT, padx=(16, 0), pady=8)

        tk.Label(mon_frame, text="CAPTURE FROM",
                 bg=BG2, fg=TEXT_DIM, font=self._font_small).pack(anchor="w")

        labels = [monitor_label(i + 1, m) for i, m in enumerate(self.monitors)]
        self._monitor_var = tk.StringVar(value=labels[0] if labels else "No displays")

        opt = tk.OptionMenu(mon_frame, self._monitor_var, *labels,
                            command=self._on_monitor_change)
        opt.config(bg=BG3, fg=TEXT, activebackground=ACCENT, activeforeground="white",
                   highlightthickness=0, relief=tk.FLAT,
                   font=self._font_small, width=42, anchor="w")
        opt["menu"].config(bg=BG3, fg=TEXT, activebackground=ACCENT,
                           activeforeground="white", font=self._font_small)
        opt.pack(anchor="w")
        self._monitor_menu = opt

        # Progress counter (far right)
        self._progress_var = tk.StringVar(value="0 / 0 captured")
        tk.Label(header, textvariable=self._progress_var,
                 bg=BG2, fg=TEXT_DIM, font=self._font_body
                 ).pack(side=tk.RIGHT, padx=18)

    def _on_monitor_change(self, selection: str):
        for i, m in enumerate(self.monitors):
            if monitor_label(i + 1, m) == selection:
                self._sel_mon_idx = i
                # Invalidate region — it was on a different display
                self.region = None
                self._btn_capture.config(state=tk.DISABLED)
                self._region_var.set(
                    f"Display changed to Display {i + 1} — re-select your region"
                )
                self._set_status(
                    f"Switched to Display {i + 1}  "
                    f"({m['width']}x{m['height']} at {m['left']},{m['top']})  "
                    "— click 'Select Region' on that monitor"
                )
                break

    def _build_main(self):
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill=tk.BOTH, expand=True)

        # ── LEFT: queue ────────────────────────────────────────────────────
        left = tk.Frame(main, bg=BG2, width=260)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        tk.Label(left, text="CAPTURE QUEUE", bg=BG2, fg=TEXT_DIM,
                 font=self._font_small).pack(anchor="w", padx=10, pady=(10, 4))

        filt_frame = tk.Frame(left, bg=BG2)
        filt_frame.pack(fill=tk.X, padx=8, pady=(0, 6))
        self._filter_var = tk.StringVar(value="all")
        for lbl, val in [("All", "all"), ("Pending", "pending"), ("Done", "done")]:
            tk.Radiobutton(
                filt_frame, text=lbl, variable=self._filter_var, value=val,
                command=self._refresh_queue,
                bg=BG2, fg=TEXT, selectcolor=BG3,
                activebackground=BG2, activeforeground=ACCENT,
                font=self._font_small, indicatoron=False,
                relief=tk.FLAT, padx=8, pady=3, cursor="hand2"
            ).pack(side=tk.LEFT, padx=2)

        lf = tk.Frame(left, bg=BG2)
        lf.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        sb = tk.Scrollbar(lf, bg=BG3, troughcolor=BG2, activebackground=ACCENT)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox = tk.Listbox(lf, bg=BG3, fg=TEXT,
                                    selectbackground=ACCENT, selectforeground="white",
                                    font=self._font_small, borderwidth=0,
                                    highlightthickness=0, activestyle="none",
                                    yscrollcommand=sb.set)
        self._listbox.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self._listbox.yview)
        self._listbox.bind("<<ListboxSelect>>", self._on_list_select)

        # ── RIGHT: capture panel ───────────────────────────────────────────
        right = tk.Frame(main, bg=BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Target info bar
        inf = tk.Frame(right, bg=BG2, padx=14, pady=12)
        inf.pack(fill=tk.X, pady=(0, 10))
        tk.Label(inf, text="CURRENT TARGET", bg=BG2, fg=TEXT_DIM,
                 font=self._font_small).grid(row=0, column=0, sticky="w")
        self._target_var = tk.StringVar(value="—")
        tk.Label(inf, textvariable=self._target_var,
                 bg=BG2, fg=GOLD, font=self._font_title).grid(row=1, column=0, sticky="w")
        self._note_var = tk.StringVar(value="")
        tk.Label(inf, textvariable=self._note_var,
                 bg=BG2, fg=TEXT_DIM, font=self._font_small).grid(row=2, column=0, sticky="w")
        self._status_badge_var = tk.StringVar(value="PENDING")
        self._status_badge = tk.Label(inf, textvariable=self._status_badge_var,
                                       bg=WARNING, fg="black",
                                       font=("Consolas", 9, "bold"), padx=8, pady=2)
        self._status_badge.grid(row=0, column=1, padx=(20, 0), sticky="e")
        inf.columnconfigure(1, weight=1)

        # Preview row
        prev_row = tk.Frame(right, bg=BG)
        prev_row.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        live_pnl = tk.Frame(prev_row, bg=BG2, padx=8, pady=8)
        live_pnl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        tk.Label(live_pnl, text="LIVE SCREEN  (selected region)",
                 bg=BG2, fg=TEXT_DIM, font=self._font_small).pack(anchor="w")
        self._live_canvas = tk.Canvas(live_pnl, width=self.PREVIEW_W, height=self.PREVIEW_H,
                                       bg="#080a10", highlightthickness=1,
                                       highlightbackground=BORDER)
        self._live_canvas.pack(pady=(4, 0))
        self._region_var = tk.StringVar(
            value="No region — pick a display above, then 'Select Region'"
        )
        tk.Label(live_pnl, textvariable=self._region_var,
                 bg=BG2, fg=TEXT_DIM, font=self._font_small).pack(anchor="w", pady=(4, 0))

        cap_pnl = tk.Frame(prev_row, bg=BG2, padx=8, pady=8, width=200)
        cap_pnl.pack(side=tk.LEFT, fill=tk.Y)
        cap_pnl.pack_propagate(False)
        tk.Label(cap_pnl, text="LAST CAPTURED",
                 bg=BG2, fg=TEXT_DIM, font=self._font_small).pack(anchor="w")
        self._cap_canvas = tk.Canvas(cap_pnl, width=180, height=160,
                                      bg="#080a10", highlightthickness=1,
                                      highlightbackground=BORDER)
        self._cap_canvas.pack(pady=(4, 6))
        self._match_var = tk.StringVar(value="—")
        self._match_label = tk.Label(cap_pnl, textvariable=self._match_var,
                                      bg=BG2, fg=TEXT_DIM, font=self._font_small)
        self._match_label.pack(anchor="w")
        self._conf_var = tk.StringVar(value="")
        self._conf_label = tk.Label(cap_pnl, textvariable=self._conf_var,
                                     bg=BG2, fg=TEXT_DIM, font=self._font_small)
        self._conf_label.pack(anchor="w")

        # Buttons
        btn_row = tk.Frame(right, bg=BG)
        btn_row.pack(fill=tk.X)
        BC = dict(font=("Consolas", 11, "bold"), padx=14, pady=8,
                  relief=tk.FLAT, cursor="hand2", borderwidth=0)
        tk.Button(btn_row, text="Select Region",
                  bg=BG3, fg=TEXT, activebackground=ACCENT, activeforeground="white",
                  command=self._select_region, **BC).pack(side=tk.LEFT, padx=(0, 6))
        self._btn_capture = tk.Button(btn_row, text="Capture & Save",
                                       bg=ACCENT, fg="white",
                                       activebackground=ACCENT2, activeforeground="white",
                                       command=self._capture_and_save,
                                       state=tk.DISABLED, **BC)
        self._btn_capture.pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_row, text="Skip",
                  bg=BG3, fg=TEXT_DIM, activebackground=BG3, activeforeground=TEXT,
                  command=self._skip, **BC).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_row, text="◀",
                  bg=BG3, fg=TEXT_DIM, activebackground=BG3, activeforeground=TEXT,
                  command=self._prev, **BC).pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(btn_row, text="▶",
                  bg=BG3, fg=TEXT_DIM, activebackground=BG3, activeforeground=TEXT,
                  command=self._next, **BC).pack(side=tk.LEFT, padx=(0, 6))

        # Guide
        gf = tk.Frame(right, bg=BG2, padx=12, pady=10)
        gf.pack(fill=tk.X, pady=(12, 0))
        tk.Label(gf, text="HOW TO USE", bg=BG2, fg=TEXT_DIM,
                 font=self._font_small).pack(anchor="w")
        tk.Label(
            gf,
            text=(
                "1. Pick your monitor from 'CAPTURE FROM' in the header  "
                "2. Open OSRS at 1920x1080 Resizable-Modern on that display  "
                "3. Click 'Select Region' and drag a tight box around the target  "
                "4. Verify the live preview matches what you expect  "
                "5. Click 'Capture & Save' — confidence score shown instantly  "
                "6. Score under 80%? Try a tighter crop and recapture  "
                "7. Skip anything you don't currently have access to"
            ),
            bg=BG2, fg=TEXT_DIM, font=self._font_small,
            justify=tk.LEFT, wraplength=640
        ).pack(anchor="w", pady=(4, 0))

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=BG3, height=28)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        self._status_var = tk.StringVar(
            value="Ready — pick your display in the header, then select a target"
        )
        tk.Label(bar, textvariable=self._status_var,
                 bg=BG3, fg=TEXT_DIM, font=self._font_small,
                 anchor="w").pack(side=tk.LEFT, padx=12, pady=4)
        tk.Label(bar, text="LIVE", bg=BG3, fg=SUCCESS,
                 font=self._font_small).pack(side=tk.RIGHT, padx=12)

    # ── Queue ─────────────────────────────────────────────────────────────────
    def _refresh_queue(self):
        filt = getattr(self, "_filter_var", None)
        filt = filt.get() if filt else "all"
        self._listbox.delete(0, tk.END)
        self._filtered_indices = []
        captured = sum(1 for e in self.entries if e.get("captured"))
        self._progress_var.set(f"{captured} / {len(self.entries)} captured")
        for i, entry in enumerate(self.entries):
            done = entry.get("captured", False)
            if filt == "pending" and done:  continue
            if filt == "done"    and not done: continue
            self._listbox.insert(tk.END, ("v " if done else "o ") + entry["file"])
            self._listbox.itemconfig(tk.END, fg=SUCCESS if done else TEXT)
            self._filtered_indices.append(i)
        self._sync_list_selection()

    def _sync_list_selection(self):
        for li, ri in enumerate(self._filtered_indices):
            if ri == self.current_idx:
                self._listbox.selection_clear(0, tk.END)
                self._listbox.selection_set(li)
                self._listbox.see(li)
                break

    def _on_list_select(self, event=None):
        sel = self._listbox.curselection()
        if sel and sel[0] < len(self._filtered_indices):
            self.current_idx = self._filtered_indices[sel[0]]
            self._update_target_info()

    def _update_target_info(self):
        if self.current_idx >= len(self.entries):
            return
        e = self.entries[self.current_idx]
        self._target_var.set(e["file"])
        self._note_var.set(e.get("note", ""))
        done = e.get("captured", False)
        self._status_badge_var.set("CAPTURED" if done else "PENDING")
        self._status_badge.config(bg=SUCCESS if done else WARNING,
                                   fg="white" if done else "black")
        self._set_status(f"Target: {e['file']}  — select region then capture")
        if done:
            p = self.templates_path / e["file"]
            if p.exists():
                img = cv2.imread(str(p))
                if img is not None:
                    self._show_in_canvas(img, self._cap_canvas, 180, 160)
                    self._match_var.set("Previously captured")
                    self._match_label.config(fg=SUCCESS)

    # ── Live preview ──────────────────────────────────────────────────────────
    def _start_live_preview(self):
        self._live_running = True
        self._schedule_live()

    def _schedule_live(self):
        if self._live_running:
            self.root.after(self.LIVE_INTERVAL_MS, self._update_live)

    def _update_live(self):
        if not self._live_running:
            return
        try:
            if self.region:
                x, y, w, h = self.region
                frame = grab_region(x, y, w, h)
            else:
                frame = grab_monitor(self._active_mss_idx)
                frame = cv2.resize(frame, (self.PREVIEW_W, self.PREVIEW_H),
                                   interpolation=cv2.INTER_AREA)
            self._show_in_canvas(frame, self._live_canvas, self.PREVIEW_W, self.PREVIEW_H)
        except Exception:
            pass
        finally:
            self._schedule_live()

    def _show_in_canvas(self, bgr: np.ndarray, canvas: tk.Canvas, mw: int, mh: int):
        h, w = bgr.shape[:2]
        scale = min(mw / w, mh / h, 1.0)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        rgb = cv2.cvtColor(cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA),
                           cv2.COLOR_BGR2RGB)
        photo = ImageTk.PhotoImage(Image.fromarray(rgb))
        canvas.config(width=mw, height=mh)
        canvas.delete("all")
        canvas.create_image(mw // 2, mh // 2, image=photo, anchor=tk.CENTER)
        canvas._photo = photo

    # ── Region selection ──────────────────────────────────────────────────────
    def _select_region(self):
        disp = self._sel_mon_idx + 1
        self._set_status(f"Overlay on Display {disp} — drag to select, ESC to cancel...")
        self.root.withdraw()
        self.root.update()
        time.sleep(0.25)

        result = RegionSelector(monitor=self._active_monitor).select()

        self.root.deiconify()
        self.root.lift()

        if result:
            self.region = result
            x, y, w, h = result
            self._region_var.set(
                f"Display {disp}  |  x={x}  y={y}  w={w}  h={h}  ({w}x{h} px)"
            )
            self._btn_capture.config(state=tk.NORMAL)
            self._set_status(
                f"Region {w}x{h}px at ({x},{y}) on Display {disp} — "
                "check preview, then Capture & Save"
            )
        else:
            self._set_status("Region selection cancelled")

    # ── Capture & save ────────────────────────────────────────────────────────
    def _capture_and_save(self):
        if not self.region:
            messagebox.showwarning("No Region", "Select a screen region first.")
            return
        e = self.entries[self.current_idx]
        out = self.templates_path / e["file"]
        out.parent.mkdir(parents=True, exist_ok=True)

        x, y, w, h = self.region
        frame = grab_region(x, y, w, h)
        self._show_in_canvas(frame, self._cap_canvas, 180, 160)

        try:
            screen = grab_monitor(self._active_mss_idx)
            passed, conf = validate_template(frame, screen, self.threshold)
        except Exception as ex:
            passed, conf = False, 0.0
            print(f"[WARN] Validation error: {ex}")

        cv2.imwrite(str(out), frame)
        self.manifest = mark_captured(self.manifest, e["file"])
        e["captured"] = True
        self._save_manifest()

        pct = f"{conf * 100:.1f}%"
        if passed:
            self._match_var.set(f"Match confirmed  ({pct})")
            self._match_label.config(fg=SUCCESS)
            self._conf_var.set(f"Saved: {e['file']}")
            self._conf_label.config(fg=TEXT_DIM)
            self._set_status(f"Saved! Confidence {pct} — moving to next target")
        else:
            self._match_var.set(f"Low confidence  ({pct})")
            self._match_label.config(fg=WARNING)
            self._conf_var.set(f"Saved (low score): {e['file']}")
            self._conf_label.config(fg=WARNING)
            self._set_status(f"Saved with low score ({pct}) — consider tighter crop")

        self._refresh_queue()
        self._update_target_info()
        if passed:
            self.root.after(800, self._advance_to_next_pending)

    def _advance_to_next_pending(self):
        """
        Move to the next uncaptured entry.

        Variant-clone behaviour: if the next pending entry shares the same
        base name as the one just captured (e.g. tree_oak_1 -> tree_oak_2),
        the current region is kept and a notice is shown so the user can
        capture the next angle without re-drawing the selection box.
        """
        just_captured = self.entries[self.current_idx]["file"] if self.current_idx < len(self.entries) else ""
        just_base = variant_base(just_captured)

        for i in list(range(self.current_idx + 1, len(self.entries))) + \
                 list(range(0, self.current_idx)):
            if not self.entries[i].get("captured"):
                self.current_idx = i
                self._update_target_info()
                self._sync_list_selection()

                next_file = self.entries[i]["file"]
                next_base = variant_base(next_file)

                if next_base == just_base and self.region is not None:
                    # Same object, different model — keep region, just notify
                    variant_num = next_file.rsplit("_", 1)[-1].split(".")[0]
                    self._set_status(
                        f"Same object, variant {variant_num} — "
                        "region kept. Adjust if needed, then Capture & Save."
                    )
                    # Flash the region label so the user notices it's pre-filled
                    x, y, w, h = self.region
                    disp = self._sel_mon_idx + 1
                    self._region_var.set(
                        f"[Variant carry-over]  Display {disp}  |  "
                        f"x={x}  y={y}  w={w}  h={h}  ({w}x{h} px)"
                    )
                else:
                    # Different object — clear region so user must re-select
                    if next_base != just_base:
                        self.region = None
                        self._btn_capture.config(state=tk.DISABLED)
                        self._region_var.set(
                            "New object — click \'Select Region\' to draw a fresh selection"
                        )
                        self._set_status(
                            f"Next target: {next_file} — select a new region"
                        )
                return
        self._set_status("All templates captured!")

    def _skip(self): self._next()
    def _prev(self):
        self.current_idx = max(0, self.current_idx - 1)
        self._update_target_info(); self._sync_list_selection()
    def _next(self):
        self.current_idx = min(len(self.entries) - 1, self.current_idx + 1)
        self._update_target_info(); self._sync_list_selection()
    def _set_status(self, msg):
        self._status_var.set(msg)
    def _on_close(self):
        self._live_running = False
        self._save_manifest()
        self.root.destroy()
    def run(self):
        self._update_target_info()
        self._refresh_queue()
        self.root.mainloop()


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="OSRS Template Capture Tool")
    parser.add_argument("--assets",    default="assets")
    parser.add_argument("--threshold", type=float, default=0.80)
    args = parser.parse_args()
    if not os.path.isdir(args.assets):
        sys.exit(f"ERROR: Assets directory not found: {args.assets}")
    TemplateCaptureApp(assets_path=args.assets, threshold=args.threshold).run()

if __name__ == "__main__":
    main()
