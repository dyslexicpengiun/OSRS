# Known Issues, Bugs, and Limitations

## Fixed in This Version

| Bug | Fix Applied |
|-----|------------|
| `input_handler.drag()` crashed on `button="middle"` | Added middle mouse support (MOUSEEVENTF_MIDDLEDOWN/UP) |
| `player_state.py` used undefined `cv2_inrange()` helper | Replaced with inline `import cv2` + direct `cv2.inRange()` call |
| `config.py` files used JSON `true`/`false` (invalid Python) | Replaced with Python `True`/`False` |
| `main.py` missing 13 scripts from headless registry | All 16 scripts now in `SCRIPT_MAP` |
| Malformed directory `{mining,woodcutting,...}` in scripts/ | Removed (was shell glob unexpanded) |
| Malformed directory `{templates` in assets/ | Removed |
| `scripts/base/` empty directory | Removed |
| `assets/templates/` subdirectories missing | Created full directory tree |

---

## Known Limitations (by design)

### Template-based vision requires screenshots
Every `e.vision.find_template()` call needs a PNG file in `assets/templates/`.
None are included in the repo — you must take them yourself from your own game client.
**Priority order for taking templates:** see `TESTING_GUIDE.md → Phase 5`.

### Coordinate system is resolution-dependent
All region configs in `config.json` assume **1920×1080 Resizable–Modern**.
If you run at a different resolution, you must recapture all templates AND
update all regions in `config.json`.

### Navigation is minimap-click only
`pathfinder.walk_to_named()` uses minimap tile clicks — it cannot navigate through
doors, obstacles, or across loading zones automatically.
You must position your character near the working area before starting a script.

### No login handling
The engine does not detect or recover from logout. If you get logged out
mid-session, the script will keep trying to find game objects and eventually
error out. Add a login detector as a future improvement.

### `easyocr` first-run download
First time you `import core.ocr`, EasyOCR downloads ~500MB of models.
This only happens once but requires internet. Use `--fast` in diagnose.py to skip.

---

## Pending Improvements

- [ ] Login screen detection and auto-login
- [ ] Multi-account support (multiple windows)
- [ ] Grand Exchange price integration via API
- [ ] Death detection + safe spot logic
- [ ] Training area detection (crowded/empty rock check)
- [ ] Save/restore script state across sessions
- [ ] Anti-detection: NLP-varied right-click menu reading
- [ ] Pixel-perfect inventory diff (detect item changes without template matching)
- [ ] Resizable client coordinate auto-calibration

---

## Debugging Checklist

If a script is not working:

1. Run `python diagnose.py` — fix all FAIL items first
2. Confirm templates exist: `python diagnose.py --section assets`
3. Confirm game window found: `python diagnose.py --section window`  
4. Use `python quick_test.py` to test individual functions interactively
5. Check `logs/session.log` for detailed error traces
6. Check per-script state machine in console output — is it cycling through states?
7. Lower template threshold: change `"detection_threshold": 0.78` → `0.68`
8. Increase OCR confidence: some menu text needs brighter game brightness

---

## Contribution Notes

When adding a new script:
1. Create `scripts/newskill/__init__.py` and `scripts/newskill/newskill_script.py`
2. Inherit from `BaseScript`, implement `setup()`, `loop()`, `teardown()`, `get_paint_data()`  
3. Add to `gui/hub.py → SCRIPT_REGISTRY`
4. Add to `main.py → SCRIPT_MAP`
5. Add to `gui/script_panel.py → SCRIPT_SCHEMAS`
6. Add required templates to `assets/templates/TEMPLATE_MANIFEST.json`
7. Add required locations to `data/locations.json`
