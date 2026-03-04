"""
Stats Tracker Widget
Displays live XP/hour, items/hour, session stats, and graphs.
Polls the active script's ScriptStats every second.
"""

import time
import math
from typing import Optional, List, Dict, Callable

try:
    import customtkinter as ctk
    CTK = True
except ImportError:
    import tkinter as ctk
    CTK = False


class StatsTracker:
    """
    Embeddable stats panel.
    Pass a callable `stats_provider` that returns a ScriptStats-like object.
    """

    GRAPH_WIDTH  = 280
    GRAPH_HEIGHT = 80
    HISTORY_LEN  = 120   # data points kept

    def __init__(self, parent, stats_provider: Optional[Callable] = None):
        self.parent = parent
        self.stats_provider = stats_provider  # () -> ScriptStats | None

        self._xp_history: List[float]    = []   # xp/hr samples
        self._items_history: List[float] = []
        self._time_history: List[float]  = []

        self.frame = ctk.CTkFrame(parent) if CTK else ctk.Frame(parent)
        self._build()
        self._poll()

    def _build(self):
        """Construct all stat labels and the mini-graph canvas."""
        # Title
        title = ctk.CTkLabel(self.frame, text="Session Statistics",
                              font=("Segoe UI", 13, "bold")) if CTK \
            else ctk.Label(self.frame, text="Session Statistics",
                            font=("Segoe UI", 12, "bold"))
        title.pack(anchor="w", padx=8, pady=(6, 2))

        # Stats grid
        self._labels: Dict[str, ctk.StringVar] = {}
        rows = [
            ("Runtime",    "runtime"),
            ("Actions",    "actions"),
            ("Items",      "items"),
            ("Items/hr",   "items_hr"),
            ("XP Gained",  "xp_total"),
            ("XP/hr",      "xp_hr"),
            ("Errors",     "errors"),
            ("Breaks",     "breaks"),
        ]
        grid = ctk.CTkFrame(self.frame) if CTK else ctk.Frame(self.frame)
        grid.pack(fill="x", padx=8, pady=2)

        for i, (label_text, key) in enumerate(rows):
            var = ctk.StringVar(value="—")
            self._labels[key] = var
            row_idx = i // 2
            col_base = (i % 2) * 2

            lbl = ctk.CTkLabel(grid, text=label_text + ":", anchor="e", width=70) if CTK \
                else ctk.Label(grid, text=label_text + ":", anchor="e", width=10)
            lbl.grid(row=row_idx, column=col_base, sticky="e", padx=(4, 1), pady=1)

            val = ctk.CTkLabel(grid, textvariable=var, anchor="w", width=90) if CTK \
                else ctk.Label(grid, textvariable=var, anchor="w", width=12)
            val.grid(row=row_idx, column=col_base + 1, sticky="w", padx=(1, 8), pady=1)

        # Mini graph canvas
        graph_lbl = ctk.CTkLabel(self.frame, text="XP/hr trend",
                                  font=("Segoe UI", 10)) if CTK \
            else ctk.Label(self.frame, text="XP/hr trend")
        graph_lbl.pack(anchor="w", padx=8, pady=(6, 0))

        import tkinter as tk
        self._canvas = tk.Canvas(self.frame,
                                  width=self.GRAPH_WIDTH, height=self.GRAPH_HEIGHT,
                                  bg="#1a1a2e", highlightthickness=1,
                                  highlightbackground="#444444")
        self._canvas.pack(padx=8, pady=(2, 8))

    def set_provider(self, fn: Callable):
        """Swap the stats provider (e.g. when a new script starts)."""
        self.stats_provider = fn

    def _poll(self):
        """Refresh stats every second."""
        try:
            self._refresh()
        except Exception:
            pass
        self.frame.after(1000, self._poll)

    def _refresh(self):
        """Pull fresh data from the stats provider and update widgets."""
        if self.stats_provider is None:
            return

        stats = self.stats_provider()
        if stats is None:
            return

        elapsed = time.time() - stats.start_time
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)

        elapsed_hr = elapsed / 3600 if elapsed > 0 else 0.0001
        total_xp   = sum(stats.xp_gained.values())
        xp_hr      = total_xp / elapsed_hr
        items_hr   = stats.items_gained / elapsed_hr

        self._labels["runtime"].set(f"{h}:{m:02d}:{s:02d}")
        self._labels["actions"].set(f"{stats.actions_performed:,}")
        self._labels["items"].set(f"{stats.items_gained:,}")
        self._labels["items_hr"].set(f"{items_hr:,.0f}")
        self._labels["xp_total"].set(f"{total_xp:,}")
        self._labels["xp_hr"].set(f"{xp_hr:,.0f}")
        self._labels["errors"].set(str(stats.errors))

        # breaks from antiban stats if available
        self._labels["breaks"].set("—")

        # Update graph history
        self._xp_history.append(xp_hr)
        self._time_history.append(elapsed)
        if len(self._xp_history) > self.HISTORY_LEN:
            self._xp_history  = self._xp_history[-self.HISTORY_LEN:]
            self._time_history = self._time_history[-self.HISTORY_LEN:]

        self._draw_graph()

    def _draw_graph(self):
        """Draw a simple line graph of XP/hr over time."""
        c = self._canvas
        c.delete("all")
        w, h = self.GRAPH_WIDTH, self.GRAPH_HEIGHT
        pad = 6

        data = self._xp_history
        if len(data) < 2:
            c.create_text(w // 2, h // 2, text="Collecting data...",
                          fill="#666666", font=("Consolas", 9))
            return

        max_val = max(data) or 1
        min_val = min(data)

        # Grid lines
        for i in range(4):
            y = pad + (h - 2 * pad) * i / 3
            c.create_line(pad, y, w - pad, y, fill="#333355", width=1)

        # Data line
        points = []
        n = len(data)
        for i, val in enumerate(data):
            x = pad + (w - 2 * pad) * i / (n - 1)
            y = h - pad - (h - 2 * pad) * (val - min_val) / max(max_val - min_val, 1)
            points.append((x, y))

        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            c.create_line(x1, y1, x2, y2, fill="#4488FF", width=2, smooth=True)

        # Current value label
        last = data[-1]
        c.create_text(w - pad, pad, text=f"{last:,.0f}/hr",
                      fill="#88AAFF", font=("Consolas", 8), anchor="ne")

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)
