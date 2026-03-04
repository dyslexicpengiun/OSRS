"""Herblore Script dispatcher."""
import logging
from scripts.base_script import BaseScript
from scripts.herblore.cleaning import CleaningScript
from scripts.herblore.potion_making import PotionMakingScript
logger = logging.getLogger(__name__)

class HerbloreScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        mode = self.script_config.get("mode","clean")
        self._delegate = CleaningScript(engine, script_config) \
            if mode == "clean" else PotionMakingScript(engine, script_config)
    def setup(self):  return self._delegate.setup()
    def loop(self):   return self._delegate.loop()
    def teardown(self): self._delegate.teardown()
    def get_paint_data(self): return self._delegate.get_paint_data()
