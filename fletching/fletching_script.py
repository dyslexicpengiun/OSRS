"""Fletching Script dispatcher."""
import logging
from scripts.base_script import BaseScript
from scripts.fletching.bow_fletching import BowFletchingScript
from scripts.fletching.arrow_fletching import ArrowFletchingScript
from scripts.fletching.bolt_fletching import BoltFletchingScript
logger = logging.getLogger(__name__)

class FletchingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        mode = self.script_config.get("mode","bow")
        self._delegate = {"bow":BowFletchingScript,"arrow":ArrowFletchingScript,
                          "bolt":BoltFletchingScript}.get(mode, BowFletchingScript)(engine, script_config)
    def setup(self):  return self._delegate.setup()
    def loop(self):   return self._delegate.loop()
    def teardown(self): self._delegate.teardown()
    def get_paint_data(self): return self._delegate.get_paint_data()
