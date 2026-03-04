"""
quick_test.py - Interactive testing utility
Run: python quick_test.py
Provides a REPL-like environment with engine pre-initialized.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time, json, logging
logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")

print("Loading engine...")
from core.engine import Engine
e = Engine('config.json')
e.start()
print(f"Engine ready. Type 'e.' and tab to explore.\n")

# Convenience aliases
def screenshot():
    return e.screenshot()

def find(template, threshold=0.78):
    """Find a template on screen."""
    frame = e.screenshot()
    match = e.vision.find_template(frame, template, threshold)
    if match:
        print(f"Found at ({match.center_x}, {match.center_y}) conf={match.confidence:.3f}")
    else:
        print(f"Not found (threshold={threshold})")
    return match

def click(x, y):
    """Click at (x, y)."""
    e.input.click(x, y)
    print(f"Clicked ({x}, {y})")

def move(x, y):
    """Move mouse to (x, y)."""
    e.input.move_to(x, y)

def inv():
    """Print inventory state."""
    frame = e.screenshot()
    e.inventory.scan(frame)
    filled = e.inventory.count_filled()
    print(f"Inventory: {filled}/28 filled")

def hp():
    """Show health and prayer."""
    frame = e.screenshot()
    h = e.color.get_health_percent(frame)
    p = e.color.get_prayer_percent(frame)
    print(f"HP: {h:.0%}  Prayer: {p:.0%}")

def state():
    """Show player state."""
    frame = e.screenshot()
    e.player.update(frame)
    print(f"Player state: {e.player.state.name}  idle_time: {e.player.time_idle():.1f}s")

def bank_open():
    """Check if bank is open."""
    frame = e.screenshot()
    result = e.bank.is_open()
    print(f"Bank open: {result}")
    return result

def test_capture_fps(n=30):
    """Benchmark capture speed."""
    t0 = time.time()
    for _ in range(n):
        f = e.screenshot()
    dt = time.time() - t0
    print(f"{n} frames in {dt:.2f}s = {n/dt:.1f} FPS ({1000*dt/n:.1f}ms/frame)")

print("Utilities: screenshot(), find(tmpl), click(x,y), move(x,y), inv(), hp(), state(), bank_open(), test_capture_fps()")
print("Engine: e.vision, e.input, e.inventory, e.bank, e.minimap, e.camera, e.player, e.antiban\n")

# Drop into interactive shell
import code
code.interact(local=locals(), banner="")

e.stop()
