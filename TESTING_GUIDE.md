# OSRS Automation Suite — Testing & Debugging Guide

## Step-by-Step: First Run

### Phase 1: Environment (do this first, off-game)

```bash
cd path/to/osrs_suite
python diagnose.py --fast
```

**Expect failures on first run:**
- `interception-python` — optional, install if you want hardware-level input
- Template PNG files — all missing until you take screenshots
- Game window not found — normal if game isn't running

**Must be green before continuing:**
- Python ≥ 3.9 ✓
- numpy, opencv-python, Pillow, mss, scipy ✓
- All internal module imports ✓
- config.json valid ✓
- profiles/default.json valid ✓
- data/locations.json valid ✓

---

### Phase 2: Fix any import failures

If any internal module fails to import:
```bash
python diagnose.py --section internal 2>&1 | grep "✗"
```
Then run the failing module directly for the full traceback:
```bash
python -c "import scripts.mining.mining_script"
```

---

### Phase 3: Game running, no templates yet

Open OSRS in **Resizable – Modern** layout at **1920×1080**.

```bash
python diagnose.py --section window
```
Should show the HWND and window size.

```bash
python diagnose.py --section screen
```
Should show frame capture with correct dimensions.

---

### Phase 4: Test screen capture + color detection

```python
# quick_test.py - run in same directory
import sys; sys.path.insert(0, '.')
from core.engine import Engine
e = Engine('config.json')
e.start()

# Grab a frame and show basic info
frame = e.screenshot()
print(f"Frame: {frame.shape}")          # Should be (1080, 1920, 3)

# Test color detection (no templates needed)
hp = e.color.get_health_percent(frame)
prayer = e.color.get_prayer_percent(frame)
print(f"HP: {hp:.0%}  Prayer: {prayer:.0%}")

# Test player state
e.player.update(frame)
print(f"State: {e.player.state.name}")  # IDLE, ANIMATING, MOVING, etc.

e.stop()
```

**Expected issues at this stage:**
- HP/Prayer shows 0% or 1.0 — color regions may need tuning for your resolution/theme
- Player state IDLE even when moving — frame-diff needs 2+ frames

---

### Phase 5: Take first templates

Priority order (take these first — needed by most scripts):
1. `interfaces/bank_bg.png` — open the bank, screenshot background
2. `interfaces/make_all_btn.png` — open any Make-X interface
3. `inventory/iron_ore.png` — have iron ore in inventory
4. `objects/iron_rock.png` — face an iron rock in Lumbridge

```python
# Save a cropped template from a screenshot
import cv2
frame = e.screenshot()
# Identify the region (x, y, w, h) using any image viewer
x, y, w, h = 200, 400, 45, 45
crop = frame[y:y+h, x:x+w]
cv2.imwrite('assets/templates/inventory/iron_ore.png', crop)
```

---

### Phase 6: Test template matching

```python
from core.vision import Vision
v = Vision()

frame = e.screenshot()
match = v.find_template(frame, 'objects/iron_rock.png', threshold=0.78)
if match:
    print(f"Rock found at ({match.center_x}, {match.center_y}) conf={match.confidence:.2f}")
else:
    print("Not found — try lower threshold or retake template")
    # Try lower threshold:
    match = v.find_template(frame, 'objects/iron_rock.png', threshold=0.65)
```

**Tuning thresholds:**
- 0.78 — default, good balance
- 0.70 — if templates look similar but confidence too low
- 0.85 — if getting false positives (wrong object matched)

---

### Phase 7: Test a script with MockEngine

This tests script logic WITHOUT needing templates or game running:

```bash
python diagnose.py --section scripts
```

All scripts should init with the MockEngine. If any fail, the issue is in
the constructor (`__init__`) — fix it before trying to run with real engine.

---

### Phase 8: Run first real script (power mining)

```bash
# Start OSRS, log in, stand next to iron rocks
python main.py --script mining --script-config scripts/mining/config.py
```

**What to watch for:**
- `[MiningScript] FIND_ROCK` — is it finding rocks? Check console
- `[Vision] Template not found` — you need `objects/iron_rock.png`
- `[MiningScript] MINING` — clicking the rock successfully
- `[MiningScript] FULL_INVENTORY` — inventory full, starting to drop
- `[Player] State: IDLE timeout` — idle detection may need tuning

---

## Common Failure Modes & Fixes

### "Template not found" every loop
1. Take a fresh screenshot of the object
2. Confirm the region config matches where you're looking
3. Lower threshold: `"detection_threshold": 0.70`
4. Check if game zoom level has changed (zoom in/out resets template size)

### Mouse clicks wrong location
1. Verify window capture region in `config.json → regions → game_view`
2. Use `e.input.get_position()` to verify coordinate system
3. The `variance` param on `click()` adds ±N pixel jitter — reduce if overshooting

### Bank detection fails
1. Make sure `interfaces/bank_bg.png` template is taken
2. Color-based bank detection uses `BANK_BACKGROUND_COLOR` in `core/color_detection.py`
3. Adjust the BGR range if your client theme is different

### Player state stuck on ANIMATING
1. Increase `idle_timeout` in player_state config
2. The animation detector uses frame diff — ensure 30fps+ capture rate
3. Some animations (like firemaking) are continuous — use timeout-based detection

### "walk_to_named: location not found"
1. Check `data/locations.json` has the location key
2. Locations use minimap tile coordinates — must be calibrated per resolution
3. For now: manually walk character to position, then let script take over

### Antiban not triggering breaks
1. Check `profiles/default.json` has `"break_enabled": true`
2. `break_interval_min` is in seconds (default 1500 = 25 min)
3. Session time shows in overlay if `overlay.enabled: true` in config

---

## Module-by-Module Test Commands

```bash
# Screen capture
python -c "from core.screen_capture import ScreenCapture; import json; c=json.load(open('config.json')); sc=ScreenCapture(c); f=sc.grab_full(); print(f.shape)"

# Color detection  
python -c "from core.color_detection import ColorDetection; cd=ColorDetection(); print(cd.profiles.keys())"

# Vision
python -c "from core.vision import Vision; v=Vision(); print('Vision OK')"

# OCR (slow first run - downloads model)
python -c "from core.ocr import OSRSTextReader; r=OSRSTextReader({}); print('OCR OK')"

# Antiban
python -c "from core.antiban import AntiBan; import json; ab=AntiBan(json.load(open('profiles/default.json'))); print(f'Break interval: {ab.break_interval_min/60:.0f}-{ab.break_interval_max/60:.0f} min')"

# Pathfinder + locations
python -c "from core.pathfinding import PathFinder; pf=PathFinder({},{}); print(pf._locations.keys())"
```

---

## Performance Benchmarks (targets)

| Operation               | Target    | Poor        |
|------------------------|-----------|-------------|
| Screen capture (full)  | <30ms     | >80ms       |
| Template match (1 tmpl)| <15ms     | >50ms       |
| Template match (10 tm) | <100ms    | >300ms      |
| Mouse move (400px)     | 150-400ms | <50ms (too fast!) |
| Bank open detection    | <100ms    | >500ms      |
| Script loop (1 iter)   | 50-500ms  | <20ms (spinning) |

---

## Logs

- Runtime log: `logs/session.log`
- View last 50 lines: `tail -50 logs/session.log`
- Watch live: `tail -f logs/session.log`
- Clear old logs: `echo "" > logs/session.log`
