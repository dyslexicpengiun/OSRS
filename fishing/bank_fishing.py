"""Bank Fishing variant — thin wrapper over FishingScript with preset config."""
from scripts.fishing.fishing_script import FishingScript

class BankFishingScript(FishingScript):
    def __init__(self, engine, script_config=None):
        cfg = script_config or {}
        cfg.update({"power_fish":False})
        super().__init__(engine, cfg)
