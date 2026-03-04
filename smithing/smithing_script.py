"""
Smithing Script
Dispatcher that delegates to Smelting or AnvilSmithing sub-scripts.
"""
import logging
from scripts.base_script import BaseScript
from scripts.smithing.smelting import SmeltingScript
from scripts.smithing.anvil_smithing import AnvilSmithingScript

logger = logging.getLogger(__name__)

class SmithingScript(BaseScript):
    """Thin dispatcher — instantiates the correct sub-script and runs it."""

    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        mode = self.script_config.get("mode", "smelting")
        if mode == "smelting":
            self._delegate = SmeltingScript(engine, script_config)
        else:
            self._delegate = AnvilSmithingScript(engine, script_config)

    def setup(self) -> bool:
        return self._delegate.setup()

    def loop(self) -> bool:
        return self._delegate.loop()

    def teardown(self):
        self._delegate.teardown()

    def get_paint_data(self):
        return self._delegate.get_paint_data()
