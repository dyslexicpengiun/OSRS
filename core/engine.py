"""
Main Automation Engine
Wires all subsystems together into a single Engine object.
Scripts receive an Engine instance and use it to access all functionality.
"""

import time
import json
import logging
from pathlib import Path
import threading
from typing import Optional, Dict, Any

from core.screen_capture import ScreenCapture
from core.vision import Vision
from core.input_handler import HumanizedInput
from core.color_detection import ColorDetection
from core.ocr import OSRSTextReader
from core.inventory import Inventory
from core.bank import BankInterface
from core.minimap import MinimapNavigator
from core.camera import Camera
from core.player_state import PlayerStateTracker
from core.antiban import AntiBan
from core.overlay import GameOverlay
from core.random_events import RandomEventHandler
from core.game_state import GameState
from core.interfaces import InterfaceManager
from core.pathfinding import PathFinder

logger = logging.getLogger(__name__)


class Engine:
    """
    Central engine that bootstraps and connects all subsystems.
    Passed to scripts as their primary interface to the game.
    """

    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self._running = False
        self._paused = False
        self._stop_event = threading.Event()

        logger.info("[Engine] Initializing subsystems...")

        # Core subsystems
        self.capture = ScreenCapture(self.config)
        self.assets_path = Path(self.config.get("assets_path", "assets"))
        self.vision = Vision(assets_path=str(self.assets_path))
        self.color = ColorDetection()
        self.ocr = OSRSTextReader()
        self.input = HumanizedInput(self.config, capture=self.capture)

        # Game systems (depend on core)
        self.inventory = Inventory(
            self.config, self.capture, self.vision, self.input, self.color
        )
        self.camera = Camera(self.config, self.input, self.capture)
        self.minimap = MinimapNavigator(
            self.config, self.capture, self.vision, self.input, self.color
        )
        self.player = PlayerStateTracker(
            self.config, self.capture, self.vision, self.color
        )
        self.interfaces = InterfaceManager(
            self.config, self.capture, self.vision, self.input, self.color, self.ocr
        )
        self.bank = BankInterface(
            self.config, self.capture, self.vision, self.input, self.color, self.inventory
        )
        self.antiban = AntiBan(self.config, self.input, self.camera)
        self.overlay = GameOverlay(self.config)
        self.random_events = RandomEventHandler(
            self.config, self.capture, self.vision, self.input, self.color, self.interfaces
        )
        self.game_state = GameState(
            self.config, self.capture, self.vision, self.color, self.player, self.interfaces
        )
        self.pathfinder = PathFinder(
            self.config, self.capture, self.minimap, self.player, self.input
        )

        # Stats
        self._session_start = time.time()
        self._tick_count = 0

        logger.info("[Engine] All subsystems initialized.")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the engine. Finds game window and starts overlay."""
        logger.info("[Engine] Starting...")
        found = self.capture.find_game_window()
        if not found:
            tried = self.capture._client_titles
            logger.warning(
                f"[Engine] Game window not found. Searched for: {tried}. "
                "Is RuneLite or the official client open?"
            )
        else:
            logger.info(f"[Engine] Game window found: '{self.capture.detected_client}'")

        if self.config.get("overlay_enabled", True):
            self.overlay.start()

        self._running = True
        self._stop_event.clear()
        logger.info("[Engine] Ready.")

    def stop(self):
        """Stop the engine and all subsystems."""
        logger.info("[Engine] Stopping...")
        self._running = False
        self._stop_event.set()
        self.antiban.stop()
        self.overlay.stop()

    def pause(self):
        """Pause script execution."""
        self._paused = True
        logger.info("[Engine] Paused.")

    def resume(self):
        """Resume script execution."""
        self._paused = False
        logger.info("[Engine] Resumed.")

    @property
    def is_running(self) -> bool:
        return self._running and not self._stop_event.is_set()

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------

    def tick(self) -> bool:
        """
        Call this at the start of every script loop iteration.
        Handles anti-ban, random events, state updates.
        Returns False if the script should stop.
        """
        if not self.is_running:
            return False

        while self._paused:
            time.sleep(0.5)
            if not self.is_running:
                return False

        self._tick_count += 1

        # Anti-ban tick
        if not self.antiban.tick():
            logger.info("[Engine] Anti-ban triggered stop.")
            self.stop()
            return False

        # Random event check (every N ticks)
        if self._tick_count % 15 == 0:
            screen = self.capture.capture_full()
            self.random_events.check_and_handle(screen)
            # Update game state
            self.game_state.update(screen)
            # Update overlay status
            self._update_overlay()

        return True

    def _update_overlay(self):
        """Push current stats to the overlay."""
        if not self.config.get("overlay_enabled", True):
            return

        elapsed = time.time() - self._session_start
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)

        self.overlay.update_status("State", self.player.state.name)
        self.overlay.update_status("Health", f"{self.game_state.health*100:.0f}%")
        self.overlay.update_status("Prayer", f"{self.game_state.prayer*100:.0f}%")
        self.overlay.update_status("Runtime", f"{hours}:{minutes:02d}:{seconds:02d}")
        self.overlay.update_status(
            "XP/hr", f"{self.game_state.get_xp_per_hour():,.0f}"
        )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def sleep(self, seconds: float = None):
        """Sleep for a given duration, or a randomized action delay."""
        if seconds is not None:
            time.sleep(seconds)
        else:
            time.sleep(self.antiban.action_delay())

    def wait_idle(self, timeout: float = 15.0) -> bool:
        """Wait until the player becomes idle."""
        return self.player.wait_until_idle(timeout)

    def screenshot(self):
        """Take a fresh screenshot."""
        return self.capture.capture_full()

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(path: str) -> dict:
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[Engine] Could not load config {path}: {e}")
            return {}

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def __repr__(self):
        elapsed = int(time.time() - self._session_start)
        return f"Engine(running={self._running}, ticks={self._tick_count}, elapsed={elapsed}s)"
