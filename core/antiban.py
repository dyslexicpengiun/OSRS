"""
Anti-Ban / Humanization System
Provides randomized, human-like behavior patterns to avoid detection.
Includes break scheduling, micro-events, fatigue simulation, and
behavioral profiles that can be loaded per-session.
"""

import time
import random
import math
import json
import logging
from typing import Optional, Dict, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AntiBanProfile:
    """Defines a behavioral profile for an automation session."""
    name: str = "default"

    # Break settings
    break_enabled: bool = True
    break_interval_min: float = 25 * 60    # seconds
    break_interval_max: float = 90 * 60
    break_duration_min: float = 30
    break_duration_max: float = 300

    # Micro events
    micro_break_chance: float = 0.03       # Per-action chance
    afk_chance: float = 0.02
    misclick_chance: float = 0.008
    camera_move_chance: float = 0.05
    hover_nearby_chance: float = 0.04      # Hover near (but not on) target

    # Fatigue
    fatigue_enabled: bool = True
    fatigue_curve: str = "logarithmic"     # "logarithmic", "linear", "none"
    session_max_hours: float = 6.0

    # Timing multipliers
    action_delay_min: float = 0.20
    action_delay_max: float = 0.80
    reaction_time_min: float = 0.15
    reaction_time_max: float = 0.55

    # Mouse behavior
    mouse_speed_min: float = 0.08
    mouse_speed_max: float = 0.35
    target_miss_chance: float = 0.01       # Miss target, correct self


@dataclass
class SessionStats:
    start_time: float = field(default_factory=time.time)
    actions_performed: int = 0
    breaks_taken: int = 0
    micro_breaks: int = 0
    total_break_time: float = 0.0
    afk_events: int = 0


class AntiBan:
    """
    Central anti-ban controller.
    Manages break scheduling, micro-events, and behavioral randomization.
    """

    def __init__(self, config: dict, input_handler=None, camera=None):
        self.config = config
        self.input = input_handler
        self.camera = camera

        gs = config.get("global_settings", {})
        self.profile = AntiBanProfile(
            break_enabled=gs.get("break_enabled", True),
            break_interval_min=gs.get("break_interval_min_minutes", 25) * 60,
            break_interval_max=gs.get("break_interval_max_minutes", 90) * 60,
            break_duration_min=gs.get("break_duration_min_seconds", 30),
            break_duration_max=gs.get("break_duration_max_seconds", 300),
            micro_break_chance=gs.get("micro_break_chance", 0.03),
            afk_chance=gs.get("afk_chance", 0.02),
            misclick_chance=gs.get("misclick_chance", 0.008),
            camera_move_chance=gs.get("camera_move_chance", 0.05),
            fatigue_enabled=gs.get("fatigue_enabled", True),
            fatigue_curve=gs.get("fatigue_curve", "logarithmic"),
            session_max_hours=gs.get("session_max_hours", 6.0),
            action_delay_min=gs.get("action_delay_min", 200) / 1000,
            action_delay_max=gs.get("action_delay_max", 800) / 1000,
        )

        self.stats = SessionStats()
        self._next_break_time = self._schedule_next_break()
        self._break_callback: Optional[Callable] = None
        self._stop_flag = False
        # No AFK or micro-breaks for the first 2 minutes — gives scripts
        # time to settle before random interruptions can fire.
        self._warmup_until = time.time() + 120.0

    def load_profile(self, path: str):
        """Load an anti-ban profile from a JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)
            for key, val in data.items():
                if hasattr(self.profile, key):
                    setattr(self.profile, key, val)
            logger.info(f"[AntiBan] Loaded profile: {path}")
        except Exception as e:
            logger.warning(f"[AntiBan] Could not load profile {path}: {e}")

    def set_break_callback(self, fn: Callable):
        """Register a function to call when a break starts/ends."""
        self._break_callback = fn

    # ---------------------------------------------------------------
    # Main tick - call this every action loop iteration
    # ---------------------------------------------------------------

    def tick(self) -> bool:
        """
        Call this once per script action loop.
        Returns True if execution should continue, False if session should end.
        """
        if self._stop_flag:
            return False

        # Session time limit
        elapsed_hours = (time.time() - self.stats.start_time) / 3600
        if elapsed_hours >= self.profile.session_max_hours:
            logger.info("[AntiBan] Session time limit reached. Stopping.")
            return False

        self.stats.actions_performed += 1

        # Scheduled break check
        if self.profile.break_enabled and time.time() >= self._next_break_time:
            self._take_break()

        # Random micro events
        self._maybe_micro_break()
        self._maybe_afk()
        self._maybe_camera_move()

        return True

    def action_delay(self) -> float:
        """
        Return a humanized delay to wait between actions.
        Applies fatigue curve so delays lengthen over time.
        """
        base = random.uniform(self.profile.action_delay_min, self.profile.action_delay_max)
        return base * self._fatigue_multiplier()

    def reaction_delay(self) -> float:
        """Return a short reaction-time delay (e.g. after something appears on screen)."""
        base = random.uniform(self.profile.reaction_time_min, self.profile.reaction_time_max)
        return base * self._fatigue_multiplier()

    def sleep_action(self):
        """Sleep for a randomized action delay."""
        time.sleep(self.action_delay())

    def sleep_reaction(self):
        """Sleep for a short reaction delay."""
        time.sleep(self.reaction_delay())

    def should_misclick(self) -> bool:
        """Return True if the next click should simulate a misclick."""
        return random.random() < self.profile.misclick_chance

    def should_move_camera(self) -> bool:
        return random.random() < self.profile.camera_move_chance

    # ---------------------------------------------------------------
    # Break handling
    # ---------------------------------------------------------------

    def _take_break(self):
        """Execute a scheduled break."""
        duration = random.uniform(
            self.profile.break_duration_min,
            self.profile.break_duration_max
        )
        logger.info(f"[AntiBan] Taking break for {duration:.0f}s")
        self.stats.breaks_taken += 1
        self.stats.total_break_time += duration

        if self._break_callback:
            self._break_callback("start", duration)

        # Simulate pre-break behavior: move mouse away, maybe press escape
        if self.input:
            screen_w = self.config.get("resolution", {}).get("width", 1920)
            screen_h = self.config.get("resolution", {}).get("height", 1080)
            # Move to a random safe zone
            rand_x = random.randint(200, screen_w - 200)
            rand_y = random.randint(200, screen_h - 200)
            try:
                self.input.move_to(rand_x, rand_y)
            except Exception:
                pass

        time.sleep(duration)
        self._next_break_time = self._schedule_next_break()

        if self._break_callback:
            self._break_callback("end", duration)

        logger.info("[AntiBan] Break finished. Resuming.")

    def _schedule_next_break(self) -> float:
        """Calculate the timestamp for the next break."""
        interval = random.uniform(
            self.profile.break_interval_min,
            self.profile.break_interval_max
        )
        return time.time() + interval

    # ---------------------------------------------------------------
    # Micro events
    # ---------------------------------------------------------------

    def _maybe_micro_break(self):
        """Small pause (1-8 seconds) to simulate distraction."""
        if time.time() < self._warmup_until:
            return
        if random.random() < self.profile.micro_break_chance:
            duration = random.uniform(1.0, 8.0)
            logger.debug(f"[AntiBan] Micro break: {duration:.1f}s")
            self.stats.micro_breaks += 1
            time.sleep(duration)

    def _maybe_afk(self):
        """Longer inactivity period (10-45 seconds) simulating user looking away."""
        if time.time() < self._warmup_until:
            return
        if random.random() < self.profile.afk_chance:
            duration = random.uniform(10.0, 45.0)
            logger.debug(f"[AntiBan] AFK event: {duration:.1f}s")
            self.stats.afk_events += 1
            time.sleep(duration)

    def _maybe_camera_move(self):
        """Randomly rotate the camera angle slightly."""
        if random.random() < self.profile.camera_move_chance and self.camera:
            try:
                direction = random.choice(['left', 'right', 'up', 'down'])
                amount = random.uniform(5, 25)
                self.camera.rotate(direction, amount)
            except Exception:
                pass

    # ---------------------------------------------------------------
    # Fatigue
    # ---------------------------------------------------------------

    def _fatigue_multiplier(self) -> float:
        """
        Returns a multiplier > 1.0 that grows with session time,
        modeling human fatigue (slower reactions, longer pauses).
        """
        if not self.profile.fatigue_enabled:
            return 1.0

        elapsed_hours = (time.time() - self.stats.start_time) / 3600

        if self.profile.fatigue_curve == "logarithmic":
            mult = 1.0 + 0.18 * math.log1p(elapsed_hours * 2)
        elif self.profile.fatigue_curve == "linear":
            mult = 1.0 + 0.08 * elapsed_hours
        else:
            mult = 1.0

        return min(mult, 1.6)  # Cap at 60% slowdown

    # ---------------------------------------------------------------
    # Session info
    # ---------------------------------------------------------------

    def session_duration_hours(self) -> float:
        return (time.time() - self.stats.start_time) / 3600

    def stop(self):
        """Signal the anti-ban system to stop."""
        self._stop_flag = True

    def get_stats_summary(self) -> Dict:
        return {
            "session_hours": round(self.session_duration_hours(), 2),
            "actions": self.stats.actions_performed,
            "breaks": self.stats.breaks_taken,
            "micro_breaks": self.stats.micro_breaks,
            "afk_events": self.stats.afk_events,
            "total_break_time_min": round(self.stats.total_break_time / 60, 1),
            "fatigue_multiplier": round(self._fatigue_multiplier(), 3),
        }
