"""
Base Script
Abstract base class for all automation scripts.
Provides the standard lifecycle, stat tracking, logging, and loop control.
"""

import time
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

import cv2

from core.engine import Engine

logger = logging.getLogger(__name__)


@dataclass
class ScriptStats:
    """Tracks per-script performance metrics."""
    start_time: float = field(default_factory=time.time)
    actions_performed: int = 0
    items_gained: int = 0
    xp_gained: Dict[str, int] = field(default_factory=dict)
    errors: int = 0
    custom: Dict[str, Any] = field(default_factory=dict)

    def add_xp(self, skill: str, amount: int):
        self.xp_gained[skill] = self.xp_gained.get(skill, 0) + amount

    def elapsed_hours(self) -> float:
        return (time.time() - self.start_time) / 3600

    def xp_per_hour(self, skill: str = None) -> float:
        h = self.elapsed_hours()
        if h < 0.001:
            return 0
        total = self.xp_gained.get(skill, 0) if skill else sum(self.xp_gained.values())
        return total / h

    def items_per_hour(self) -> float:
        h = self.elapsed_hours()
        if h < 0.001:
            return 0
        return self.items_gained / h


class BaseScript(ABC):
    """
    Abstract base for all OSRS automation scripts.

    Subclass this and implement:
        - setup()          : one-time initialization (validate inventory, find location, etc.)
        - loop()           : one iteration of the main action loop
        - teardown()       : cleanup when script stops

    Optionally override:
        - on_error(e)      : handle unexpected exceptions
        - get_paint_data() : return dict of overlay display values
    """

    def __init__(self, engine: Engine, script_config: dict = None):
        self.engine = engine
        self.script_config = script_config or {}
        self.stats = ScriptStats()
        self.logger = logging.getLogger(self.__class__.__name__)

        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def setup(self) -> bool:
        """
        One-time setup before the main loop begins.
        Return True to proceed, False to abort.
        """
        ...

    @abstractmethod
    def loop(self) -> bool:
        """
        Single iteration of the script's main action loop.
        Return True to continue, False to stop the script.
        """
        ...

    def teardown(self):
        """Called when the script stops. Override for cleanup."""
        pass

    def on_error(self, error: Exception) -> bool:
        """
        Called when an unhandled exception occurs in loop().
        Return True to retry, False to stop the script.
        """
        self.stats.errors += 1
        self.logger.error(f"[{self.__class__.__name__}] Unhandled error: {error}", exc_info=True)
        if self.stats.errors > 10:
            self.logger.error("Too many errors. Stopping script.")
            return False
        time.sleep(2.0)
        return True

    def get_paint_data(self) -> Dict[str, Any]:
        """
        Return a dict of values to display on the overlay.
        Override to customize what's shown.
        """
        return {
            "Script": self.__class__.__name__,
            "Runtime": self._format_elapsed(),
            "Actions": self.stats.actions_performed,
            "Errors": self.stats.errors,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self):
        """Run the script (blocking). Prefer start() for threaded use."""
        self.logger.info(f"[{self.__class__.__name__}] Starting...")
        self._running = True
        self._stop_event.clear()
        self.stats = ScriptStats()

        if not self.setup():
            self.logger.warning("Setup failed. Aborting.")
            return

        self.logger.info(f"[{self.__class__.__name__}] Setup complete. Entering main loop.")

        try:
            while self._running and not self._stop_event.is_set():
                # Engine tick (anti-ban, randoms, state update)
                if not self.engine.tick():
                    break

                # Script loop
                try:
                    should_continue = self.loop()
                    self.stats.actions_performed += 1
                except cv2.error as e:
                    # Almost always a None/empty frame from screen capture —
                    # log once, wait, and retry rather than burning through
                    # the error budget.
                    if "empty" in str(e).lower() or "Assertion" in str(e):
                        self.logger.warning(
                            f"[{self.__class__.__name__}] Screen capture returned empty frame "
                            "(game window may be minimised or not yet found). Retrying in 2s..."
                        )
                        time.sleep(2.0)
                        continue
                    if not self.on_error(e):
                        break
                    continue
                except Exception as e:
                    if not self.on_error(e):
                        break
                    continue

                if not should_continue:
                    break

                # Update overlay
                self._push_paint_data()

                # Minimum tick interval — prevents spinning at hundreds of
                # iterations/second which breaks frame-diff state detection
                # and fires antiban events far too frequently.
                time.sleep(0.2)

        finally:
            self._running = False
            self.teardown()
            self.logger.info(f"[{self.__class__.__name__}] Stopped. {self._summary()}")

    def start(self):
        """Start the script in a background thread."""
        self._thread = threading.Thread(target=self.run, daemon=True, name=self.__class__.__name__)
        self._thread.start()

    def stop(self):
        """Signal the script to stop."""
        self._running = False
        self._stop_event.set()
        self.logger.info(f"[{self.__class__.__name__}] Stop requested.")

    def join(self, timeout: float = None):
        """Wait for the script thread to finish."""
        if self._thread:
            self._thread.join(timeout)

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Helpers available to subclasses
    # ------------------------------------------------------------------

    def sleep(self, seconds: float = None):
        """Anti-ban aware sleep."""
        self.engine.sleep(seconds)

    def log(self, msg: str, level: str = "info"):
        getattr(self.logger, level)(f"[{self.__class__.__name__}] {msg}")

    def wait_idle(self, timeout: float = 15.0) -> bool:
        return self.engine.wait_idle(timeout)

    def screenshot(self):
        return self.engine.screenshot()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _push_paint_data(self):
        """Send script-specific overlay data to the overlay system."""
        try:
            paint = self.get_paint_data()
            for key, val in paint.items():
                self.engine.overlay.update_status(key, str(val))
        except Exception:
            pass

    def _format_elapsed(self) -> str:
        elapsed = int((time.time() - self.stats.start_time))
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return f"{h}:{m:02d}:{s:02d}"

    def _summary(self) -> str:
        return (
            f"Runtime: {self._format_elapsed()} | "
            f"Actions: {self.stats.actions_performed} | "
            f"Errors: {self.stats.errors}"
        )
