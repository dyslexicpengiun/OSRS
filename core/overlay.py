"""
Transparent Overlay System
Renders a click-through transparent window over the game for debug visualization.
Shows detected objects, bot status, XP rates, and state information.
Uses tkinter for a lightweight always-on-top overlay.
"""

import time
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Dict, List, Tuple, Optional, Callable
import queue

try:
    import win32gui
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


class OverlayWidget:
    """A drawable element on the overlay."""
    def __init__(self, widget_id: str, widget_type: str, **kwargs):
        self.id = widget_id
        self.type = widget_type  # 'text', 'rect', 'circle', 'line'
        self.kwargs = kwargs
        self.ttl: float = kwargs.pop('ttl', 0)  # 0 = persistent
        self.created_at: float = time.time()

    @property
    def expired(self) -> bool:
        if self.ttl <= 0:
            return False
        return (time.time() - self.created_at) > self.ttl


class GameOverlay:
    """
    Transparent click-through overlay window rendered over the game.
    Runs in a separate thread to avoid blocking the bot logic.
    """

    BG_COLOR = 'black'   # Will be made transparent
    TRANSPARENT_COLOR = 'black'

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("overlay_enabled", True)

        resolution = config.get("resolution", {})
        self.width = resolution.get("width", 1920)
        self.height = resolution.get("height", 1080)

        self._widgets: Dict[str, OverlayWidget] = {}
        self._lock = threading.Lock()
        self._command_queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None

        # Status bar data
        self._status: Dict[str, str] = {
            "State": "Initializing",
            "Health": "100%",
            "Prayer": "100%",
            "XP/hr": "0",
            "Runtime": "0:00",
        }

    def start(self):
        """Start the overlay in a background thread."""
        if not self.enabled:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the overlay."""
        self._running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    def _run(self):
        """Main overlay thread function."""
        try:
            self._root = tk.Tk()
            self._setup_window()
            self._canvas = tk.Canvas(
                self._root,
                width=self.width, height=self.height,
                bg=self.BG_COLOR, highlightthickness=0
            )
            self._canvas.pack()

            # Make window transparent and click-through
            self._root.wm_attributes('-transparentcolor', self.TRANSPARENT_COLOR)
            self._root.wm_attributes('-topmost', True)
            self._root.wm_attributes('-alpha', 0.95)

            if WIN32_AVAILABLE:
                self._make_click_through()

            self._schedule_refresh()
            self._root.mainloop()
        except Exception as e:
            print(f"[Overlay] Error: {e}")

    def _setup_window(self):
        """Configure the overlay window."""
        self._root.overrideredirect(True)  # No title bar
        self._root.geometry(f"{self.width}x{self.height}+0+0")
        self._root.configure(bg=self.BG_COLOR)

    def _make_click_through(self):
        """Make window click-through using Win32 API."""
        try:
            hwnd = win32gui.FindWindow(None, self._root.title())
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd,
                win32con.GWL_EXSTYLE,
                style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
            )
        except Exception:
            pass

    def _schedule_refresh(self):
        """Schedule periodic canvas refresh."""
        if self._running:
            self._process_commands()
            self._draw_frame()
            self._root.after(100, self._schedule_refresh)  # 10 FPS

    def _process_commands(self):
        """Process queued widget updates."""
        while not self._command_queue.empty():
            try:
                cmd, args = self._command_queue.get_nowait()
                if cmd == 'set_widget':
                    widget_id, widget = args
                    with self._lock:
                        self._widgets[widget_id] = widget
                elif cmd == 'remove':
                    with self._lock:
                        self._widgets.pop(args, None)
                elif cmd == 'clear':
                    with self._lock:
                        self._widgets.clear()
                elif cmd == 'status':
                    key, value = args
                    self._status[key] = value
            except queue.Empty:
                break

    def _draw_frame(self):
        """Redraw all overlay elements."""
        if not self._canvas:
            return

        self._canvas.delete('all')

        # Remove expired widgets
        with self._lock:
            expired = [k for k, w in self._widgets.items() if w.expired]
            for k in expired:
                del self._widgets[k]
            widgets = list(self._widgets.values())

        # Draw widgets
        for widget in widgets:
            self._draw_widget(widget)

        # Draw status panel (top-right)
        self._draw_status_panel()

    def _draw_widget(self, widget: OverlayWidget):
        """Render a single overlay widget."""
        try:
            kw = widget.kwargs
            if widget.type == 'rect':
                self._canvas.create_rectangle(
                    kw['x'], kw['y'], kw['x'] + kw['w'], kw['y'] + kw['h'],
                    outline=kw.get('color', '#00FF00'),
                    width=kw.get('width', 2)
                )
            elif widget.type == 'text':
                self._canvas.create_text(
                    kw['x'], kw['y'],
                    text=kw['text'],
                    fill=kw.get('color', '#00FF00'),
                    font=('Consolas', kw.get('size', 11), 'bold'),
                    anchor=kw.get('anchor', 'nw')
                )
            elif widget.type == 'circle':
                r = kw.get('radius', 5)
                self._canvas.create_oval(
                    kw['x'] - r, kw['y'] - r,
                    kw['x'] + r, kw['y'] + r,
                    outline=kw.get('color', '#FF0000'),
                    width=2
                )
            elif widget.type == 'line':
                self._canvas.create_line(
                    kw['x1'], kw['y1'], kw['x2'], kw['y2'],
                    fill=kw.get('color', '#FFFFFF'),
                    width=kw.get('width', 1)
                )
        except Exception:
            pass

    def _draw_status_panel(self):
        """Draw the bot status panel in the top-right corner."""
        if not self._canvas:
            return

        panel_x = self.width - 220
        panel_y = 10
        line_height = 16

        # Panel background
        h = len(self._status) * line_height + 12
        self._canvas.create_rectangle(
            panel_x - 5, panel_y - 5,
            panel_x + 215, panel_y + h,
            fill='#111111', outline='#333333', width=1
        )

        for i, (key, val) in enumerate(self._status.items()):
            y = panel_y + i * line_height
            self._canvas.create_text(
                panel_x, y,
                text=f"{key}: {val}",
                fill='#AAFFAA', font=('Consolas', 9), anchor='nw'
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def draw_rect(self, widget_id: str, x: int, y: int, w: int, h: int,
                  color: str = '#00FF00', line_width: int = 2, ttl: float = 2.0):
        """Draw a bounding rectangle around a detected object."""
        widget = OverlayWidget(widget_id, 'rect', x=x, y=y, w=w, h=h,
                               color=color, width=line_width, ttl=ttl)
        self._command_queue.put(('set_widget', (widget_id, widget)))

    def draw_text(self, widget_id: str, x: int, y: int, text: str,
                  color: str = '#FFFFFF', size: int = 11, ttl: float = 3.0):
        """Draw text at a screen position."""
        widget = OverlayWidget(widget_id, 'text', x=x, y=y, text=text,
                               color=color, size=size, ttl=ttl)
        self._command_queue.put(('set_widget', (widget_id, widget)))

    def draw_circle(self, widget_id: str, x: int, y: int, radius: int = 5,
                    color: str = '#FF0000', ttl: float = 2.0):
        """Draw a circle marker at a screen position."""
        widget = OverlayWidget(widget_id, 'circle', x=x, y=y,
                               radius=radius, color=color, ttl=ttl)
        self._command_queue.put(('set_widget', (widget_id, widget)))

    def update_status(self, key: str, value: str):
        """Update a status panel entry."""
        self._command_queue.put(('status', (key, value)))

    def remove_widget(self, widget_id: str):
        self._command_queue.put(('remove', widget_id))

    def clear(self):
        self._command_queue.put(('clear', None))
