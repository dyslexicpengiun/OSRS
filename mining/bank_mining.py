"""Bank Mining variant — thin wrapper over MiningScript with preset config."""
from scripts.mining.mining_script import MiningScript

class BankMiningScript(MiningScript):
    def __init__(self, engine, script_config=None):
        cfg = script_config or {}
        cfg.update({"power_mine":False})
        super().__init__(engine, cfg)
