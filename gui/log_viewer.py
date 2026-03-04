"""
Log Viewer Widget
Real-time, color-coded, filterable log display.
Thread-safe: logging handlers push via queue, UI polls.
"""

import logging
import queue
import time
from typing import Optional

try:
    import customtkinter as ctk
    CTK = True
except ImportError:
    import tkinter as ctk
    import tkinter.font as tkfont
    CTK = False


# Color tags for log levels
LEVEL_COLORS = {
    "DEBUG":    "#888888",
    "INFO":     "#CCCCCC",
    "WARNING":  "#FFD700",
    "ERROR":    "#FF6060",
    "CRITICAL": "#FF0000",
}


class LogViewer:
    """
    Scrollable, color-coded log viewer.
    Can be embedded in any parent frame.
    Attach via LogViewer.make_handler() to get a logging.Handler.
    """

    MAX_LINES = 2000

    def __init__(self, parent, height: int = 300, font_size: int = 10):
        self.parent = parent
        self._queue: queue.Queue = queue.Queue()
        self._line_count = 0
        self._filter_level = logging.DEBUG
        self._paused = False

        self.frame = ctk.CTkFrame(parent) if CTK else ctk.Frame(parent)

        # Toolbar
        toolbar = ctk.CTkFrame(self.frame) if CTK else ctk.Frame(self.frame)
        toolbar.pack(fill="x", padx=4, pady=(4, 0))

        # Level filter
        self._level_var = ctk.StringVar(value="INFO")
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if CTK:
            level_combo = ctk.CTkComboBox(toolbar, values=levels,
                                           variable=self._level_var, width=100,
                                           command=self._on_level_change)
        else:
            import tkinter.ttk as ttk
            level_combo = ttk.Combobox(toolbar, values=levels,
                                        textvariable=self._level_var, width=10)
            self._level_var.trace_add("write", lambda *_: self._on_level_change())
        level_combo.pack(side="left", padx=4)

        # Pause/resume
        self._pause_var = ctk.StringVar(value="⏸ Pause")
        pause_btn = ctk.CTkButton(toolbar, textvariable=self._pause_var,
                                   command=self._toggle_pause, width=80) if CTK \
            else ctk.Button(toolbar, textvariable=self._pause_var,
                            command=self._toggle_pause)
        pause_btn.pack(side="left", padx=4)

        # Clear
        clear_btn = ctk.CTkButton(toolbar, text="🗑 Clear",
                                   command=self._clear, width=70) if CTK \
            else ctk.Button(toolbar, text="Clear", command=self._clear)
        clear_btn.pack(side="left", padx=4)

        # Line count label
        self._count_var = ctk.StringVar(value="0 lines")
        ctk.CTkLabel(toolbar, textvariable=self._count_var).pack(side="right", padx=4) if CTK \
            else ctk.Label(toolbar, textvariable=self._count_var).pack(side="right", padx=4)

        # Text area
        if CTK:
            self._text = ctk.CTkTextbox(self.frame, height=height,
                                         font=("Consolas", font_size),
                                         state="disabled")
        else:
            self._text = ctk.Text(self.frame, height=height // 16,
                                   font=("Consolas", font_size),
                                   bg="#1e1e1e", fg="#cccccc",
                                   state="disabled")
            # Configure color tags
            for level, color in LEVEL_COLORS.items():
                self._text.tag_configure(level, foreground=color)

        self._text.pack(fill="both", expand=True, padx=4, pady=4)

        # Start polling
        self._poll()

    def _poll(self):
        """Drain the queue and update the text widget."""
        if not self._paused:
            try:
                while True:
                    record = self._queue.get_nowait()
                    self._append_record(record)
            except queue.Empty:
                pass
        self.frame.after(150, self._poll)

    def _append_record(self, record: logging.LogRecord):
        """Add a log record to the text widget."""
        level_name = record.levelname
        if record.levelno < self._filter_level:
            return

        ts = time.strftime("%H:%M:%S", time.localtime(record.created))
        line = f"[{ts}] [{level_name:<8}] {record.name}: {record.getMessage()}\n"
        color = LEVEL_COLORS.get(level_name, "#CCCCCC")

        try:
            if CTK:
                self._text.configure(state="normal")
                self._text.insert("end", line)
                self._text.configure(state="disabled")
                self._text.see("end")
            else:
                self._text.configure(state="normal")
                self._text.insert("end", line, level_name)
                self._text.configure(state="disabled")
                self._text.see("end")
        except Exception:
            pass

        self._line_count += 1
        self._count_var.set(f"{self._line_count} lines")

        # Trim oldest lines
        if self._line_count > self.MAX_LINES:
            try:
                if CTK:
                    self._text.configure(state="normal")
                    self._text.delete("1.0", "100.0")
                    self._text.configure(state="disabled")
                else:
                    self._text.configure(state="normal")
                    self._text.delete("1.0", "101.0")
                    self._text.configure(state="disabled")
                self._line_count -= 100
            except Exception:
                pass

    def _on_level_change(self, *_):
        level_name = self._level_var.get()
        self._filter_level = getattr(logging, level_name, logging.INFO)

    def _toggle_pause(self):
        self._paused = not self._paused
        self._pause_var.set("▶ Resume" if self._paused else "⏸ Pause")

    def _clear(self):
        try:
            if CTK:
                self._text.configure(state="normal")
                self._text.delete("0.0", "end")
                self._text.configure(state="disabled")
            else:
                self._text.configure(state="normal")
                self._text.delete("1.0", "end")
                self._text.configure(state="disabled")
            self._line_count = 0
            self._count_var.set("0 lines")
        except Exception:
            pass

    def make_handler(self) -> logging.Handler:
        """Return a logging.Handler that feeds into this viewer."""
        return _QueueHandler(self._queue)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)


class _QueueHandler(logging.Handler):
    """Logging handler that puts records into a queue for the UI to consume."""
    def __init__(self, q: queue.Queue):
        super().__init__()
        self._queue = q

    def emit(self, record: logging.LogRecord):
        try:
            self._queue.put_nowait(record)
        except Exception:
            pass
