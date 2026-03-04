"""Farming Script dispatcher."""
import logging
from scripts.base_script import BaseScript
from scripts.farming.herb_runs import HerbRunScript
from scripts.farming.tree_runs import TreeRunScript
logger = logging.getLogger(__name__)

class FarmingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        mode = self.script_config.get("mode","herb_run")
        self._delegate = HerbRunScript(engine, script_config) \
            if mode == "herb_run" else TreeRunScript(engine, script_config)
    def setup(self):  return self._delegate.setup()
    def loop(self):   return self._delegate.loop()
    def teardown(self): self._delegate.teardown()
    def get_paint_data(self): return self._delegate.get_paint_data()
