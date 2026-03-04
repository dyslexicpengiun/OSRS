"""Bank Chopping variant — thin wrapper over WoodcuttingScript with preset config."""
from scripts.woodcutting.woodcutting_script import WoodcuttingScript

class BankChoppingScript(WoodcuttingScript):
    def __init__(self, engine, script_config=None):
        cfg = script_config or {}
        cfg.update({"power_chop":False})
        super().__init__(engine, cfg)
