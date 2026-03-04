"""Power Chopping variant — thin wrapper over WoodcuttingScript with preset config."""
from scripts.woodcutting.woodcutting_script import WoodcuttingScript

class PowerChoppingScript(WoodcuttingScript):
    def __init__(self, engine, script_config=None):
        cfg = script_config or {}
        cfg.update({"power_chop":True})
        super().__init__(engine, cfg)
