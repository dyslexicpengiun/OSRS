"""Power Mining variant — thin wrapper over MiningScript with preset config."""
from scripts.mining.mining_script import MiningScript

class PowerMiningScript(MiningScript):
    def __init__(self, engine, script_config=None):
        cfg = script_config or {}
        cfg.update({"power_mine":True})
        super().__init__(engine, cfg)
