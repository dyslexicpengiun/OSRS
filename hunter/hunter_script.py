"""Hunter Script dispatcher."""
import logging
from scripts.base_script import BaseScript
from scripts.hunter.chinchompas import ChinchompaScript
from scripts.hunter.birdhouse_runs import BirdhouseScript
logger = logging.getLogger(__name__)

class HunterScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        mode = self.script_config.get("mode","chinchompa")
        self._delegate = ChinchompaScript(engine, script_config) \
            if mode == "chinchompa" else BirdhouseScript(engine, script_config)
    def setup(self):  return self._delegate.setup()
    def loop(self):   return self._delegate.loop()
    def teardown(self): self._delegate.teardown()
    def get_paint_data(self): return self._delegate.get_paint_data()
