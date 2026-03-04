# Assets Directory

## Structure

```
assets/
├── templates/              # OpenCV template images (PNG, cropped from game screenshots)
│   ├── inventory/          # Inventory item images (28x28 to 35x35 px, transparent bg ok)
│   │   ├── iron_ore.png
│   │   ├── coal_ore.png
│   │   ├── lobster.png
│   │   ├── bones.png
│   │   └── ... (one per item used by any script)
│   ├── objects/            # In-world objects
│   │   ├── agility/        # Agility course obstacles
│   │   ├── altars/         # RC altar entrances and interiors
│   │   ├── farming/        # Farming patches
│   │   └── construction/   # Hotspot and furniture templates
│   ├── interfaces/         # UI elements (make-x, bank, login etc.)
│   ├── npcs/               # NPC portrait/overhead templates
│   ├── random_events/      # Random event NPC and dialog templates
│   └── minimap/            # Minimap dot colors (unused, color-detected instead)
├── models/                 # Optional: ONNX/TFLite models for object detection
├── fonts/                  # OCR font references (optional)
└── color_profiles/         # JSON color range overrides per skill area
```

## How to Capture Templates

1. Set OSRS to **Resizable - Modern** layout at **1920x1080**
2. Use the built-in screenshot or any snipping tool
3. Crop tightly around the object — leave 1–2 px border
4. Save as PNG (lossless)
5. Name consistently: `{category}/{object_name}.png`

## Template Naming Conventions

| Prefix          | Meaning                        |
|----------------|-------------------------------|
| `inventory/`   | Inventory item slot icon       |
| `objects/`     | Clickable game world object    |
| `interfaces/`  | Game interface element         |
| `npcs/`        | NPC overhead / portrait        |

## Resolution Notes

- Templates are matched against the **full 1920×1080** game view
- If you run a different resolution, retake all templates at that resolution
- Region hints in script configs (e.g. `"region": [x, y, w, h]`) speed up matching

## Color-Based Detection (no templates needed)

The following are detected by color profile rather than template:
- Health orb (red/green bar)
- Prayer orb (blue/white bar)
- Rock depletion (grey desaturated rock)
- Fishing spot movement (blue water color)
- Inventory empty slots (dark grey background)
- Minimap player dot (white)
- Minimap NPC dots (yellow)
- Minimap item dots (cyan)
