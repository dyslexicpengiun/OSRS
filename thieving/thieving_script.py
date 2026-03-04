"""Thieving Script — dispatches to pickpocket or stall sub-scripts."""
import logging
from scripts.base_script import BaseScript
from scripts.thieving.pickpocketing import PickpocketScript
from scripts.thieving.stall_thieving import StallThievingScript
logger = logging.getLogger(__name__)

class ThievingScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        mode = self.script_config.get("mode","pickpocket")
        self._delegate = PickpocketScript(engine, script_config) \
            if mode == "pickpocket" else StallThievingScript(engine, script_config)

    def setup(self):  return self._delegate.setup()
    def loop(self):   return self._delegate.loop()
    def teardown(self): self._delegate.teardown()
    def get_paint_data(self): return self._delegate.get_paint_data()
