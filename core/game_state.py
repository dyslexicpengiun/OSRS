"""
Game State Machine
High-level state machine that tracks overall game context:
logged in, at bank, in combat, world-hopping, etc.
Aggregates data from all subsystems into a single queryable state.
"""

import time
import logging
from enum import Enum, auto
from typing import Optional, Dict, Any

import numpy as np

from core.screen_capture import ScreenCapture
from core.vision import Vision
from core.color_detection import ColorDetection
from core.player_state import PlayerStateTracker, PlayerState
from core.interfaces import InterfaceManager

logger = logging.getLogger(__name__)


class GameContext(Enum):
    """Top-level game context."""
    UNKNOWN = auto()
    LOGIN_SCREEN = auto()
    WORLD_SELECT = auto()
    LOADING = auto()
    IN_GAME = auto()
    BANK_OPEN = auto()
    SHOP_OPEN = auto()
    TRADE_OPEN = auto()
    DIALOG_OPEN = auto()
    DEAD = auto()
    WORLD_HOPPING = auto()


class GameState:
    """
    Central game state aggregator.
    Polls subsystems to maintain a real-time picture of game status.
    """

    # Login screen detection: look for the specific orange RuneScape logo area
    LOGIN_SCREEN_COLOR = (0, 100, 200)     # Approx dark blue login bg

    def __init__(
        self,
        config: dict,
        capture: ScreenCapture,
        vision: Vision,
        color: ColorDetection,
        player_tracker: PlayerStateTracker,
        interface_manager: InterfaceManager
    ):
        self.config = config
        self.capture = capture
        self.vision = vision
        self.color = color
        self.player = player_tracker
        self.interfaces = interface_manager

        self._context = GameContext.UNKNOWN
        self._last_update: float = 0
        self._update_interval: float = 0.5

        # Aggregated game data
        self._health: float = 1.0
        self._prayer: float = 1.0
        self._run_energy: float = 1.0
        self._inventory_full: bool = False
        self._in_combat: bool = False

        # XP tracking
        self._xp_gains: Dict[str, int] = {}
        self._session_start = time.time()

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    def update(self, screen: np.ndarray = None) -> GameContext:
        """
        Update all game state. Call from script main loop.
        Returns the current GameContext.
        """
        now = time.time()
        if (now - self._last_update) < self._update_interval:
            return self._context

        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return self._context

        self._last_update = now

        # Detect context
        self._context = self._detect_context(screen)

        # Update vitals if in-game
        if self._context not in (GameContext.LOGIN_SCREEN, GameContext.LOADING, GameContext.UNKNOWN):
            self._update_vitals(screen)
            self.player.update(screen)

        return self._context

    def _detect_context(self, screen: np.ndarray) -> GameContext:
        """Identify the current game context from the screenshot."""

        # Loading screen: nearly black
        h, w = screen.shape[:2]
        center = screen[h//3:2*h//3, w//4:3*w//4]
        if center.mean() < 15:
            return GameContext.LOADING

        # Login screen: look for the login interface
        login_match = self.vision.find_template(
            screen, "interfaces/login_screen.png",
            threshold=0.75,
            region=(0, 0, w, h // 2)
        )
        if login_match:
            return GameContext.LOGIN_SCREEN

        # Bank open
        bank_bg = self.color.check_color_at(screen, 78, 69, 'bank_background')
        if bank_bg:
            return GameContext.BANK_OPEN

        # Dialog open
        if self.interfaces.is_continue_prompt_visible(screen):
            return GameContext.DIALOG_OPEN

        # Dead: health orb at zero
        if self.player.is_dead():
            return GameContext.DEAD

        # Default: in game
        return GameContext.IN_GAME

    def _update_vitals(self, screen: np.ndarray):
        """Update health, prayer, and run energy readings."""
        hp = self.player.get_health_percent(screen)
        if hp is not None:
            self._health = hp

        pr = self.player.get_prayer_percent(screen)
        if pr is not None:
            self._prayer = pr

    # ------------------------------------------------------------------
    # Convenience queries
    # ------------------------------------------------------------------

    @property
    def context(self) -> GameContext:
        return self._context

    @property
    def health(self) -> float:
        """Health percentage 0.0-1.0."""
        return self._health

    @property
    def prayer(self) -> float:
        """Prayer percentage 0.0-1.0."""
        return self._prayer

    def is_in_game(self) -> bool:
        return self._context in (
            GameContext.IN_GAME,
            GameContext.BANK_OPEN,
            GameContext.DIALOG_OPEN
        )

    def is_bank_open(self) -> bool:
        return self._context == GameContext.BANK_OPEN

    def is_loading(self) -> bool:
        return self._context in (GameContext.LOADING, GameContext.WORLD_HOPPING)

    def is_player_idle(self) -> bool:
        return self.player.is_idle()

    def is_player_animating(self) -> bool:
        return self.player.is_animating()

    def is_low_health(self, threshold: float = 0.35) -> bool:
        return self._health < threshold

    def is_low_prayer(self, threshold: float = 0.15) -> bool:
        return self._prayer < threshold

    def wait_for_game(self, timeout: float = 30.0) -> bool:
        """Wait until we're in-game (past login/loading). Returns True if successful."""
        start = time.time()
        while (time.time() - start) < timeout:
            ctx = self.update()
            if self.is_in_game():
                return True
            time.sleep(1.0)
        return False

    def wait_for_idle(self, timeout: float = 15.0) -> bool:
        """Wait until player is idle. Delegates to player tracker."""
        return self.player.wait_until_idle(timeout)

    # ------------------------------------------------------------------
    # XP tracking
    # ------------------------------------------------------------------

    def register_xp_gain(self, skill: str, amount: int):
        """Record an XP gain (called by scripts when XP drop detected)."""
        self._xp_gains[skill] = self._xp_gains.get(skill, 0) + amount

    def get_xp_gained(self, skill: str = None) -> int:
        """Get total XP gained this session for a skill, or all skills."""
        if skill:
            return self._xp_gains.get(skill, 0)
        return sum(self._xp_gains.values())

    def get_xp_per_hour(self, skill: str = None) -> float:
        """Calculate XP/hour rate for this session."""
        elapsed = (time.time() - self._session_start) / 3600
        if elapsed < 0.001:
            return 0
        return self.get_xp_gained(skill) / elapsed

    def get_session_summary(self) -> Dict[str, Any]:
        return {
            "context": self._context.name,
            "health": round(self._health * 100, 1),
            "prayer": round(self._prayer * 100, 1),
            "player_state": self.player.state.name,
            "xp_gained": self._xp_gains,
            "session_hours": round((time.time() - self._session_start) / 3600, 2),
        }
