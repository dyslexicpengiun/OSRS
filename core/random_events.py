"""
Random Event Detection & Handling
Detects OSRS random events (Mysterious Old Man, Certer, etc.)
and dismisses them to prevent script interruption.
"""

import time
import random
import logging
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass

import numpy as np

from core.screen_capture import ScreenCapture
from core.vision import Vision
from core.input_handler import HumanizedInput
from core.color_detection import ColorDetection
from core.interfaces import InterfaceManager

logger = logging.getLogger(__name__)


@dataclass
class RandomEvent:
    name: str
    template_path: str          # Template for detection
    dialog_template: str        # Template when already engaged
    dismiss_method: str         # 'esc', 'walk_away', 'click_x', 'answer'
    threshold: float = 0.82
    detection_region: Tuple = None  # None = full screen


# All known OSRS random events
KNOWN_RANDOMS: List[RandomEvent] = [
    RandomEvent(
        name="Mysterious Old Man",
        template_path="random_events/mom_npc.png",
        dialog_template="random_events/mom_dialog.png",
        dismiss_method="walk_away"
    ),
    RandomEvent(
        name="Certer",
        template_path="random_events/certer_npc.png",
        dialog_template="random_events/certer_dialog.png",
        dismiss_method="walk_away"
    ),
    RandomEvent(
        name="Frog",
        template_path="random_events/frog_npc.png",
        dialog_template="random_events/frog_dialog.png",
        dismiss_method="walk_away"
    ),
    RandomEvent(
        name="Drill Demon",
        template_path="random_events/drill_demon_npc.png",
        dialog_template="random_events/drill_demon_dialog.png",
        dismiss_method="walk_away"
    ),
    RandomEvent(
        name="Evil Bob",
        template_path="random_events/evil_bob_npc.png",
        dialog_template="random_events/evil_bob_dialog.png",
        dismiss_method="walk_away"
    ),
    RandomEvent(
        name="Freaky Forester",
        template_path="random_events/freaky_forester_npc.png",
        dialog_template="random_events/freaky_forester_dialog.png",
        dismiss_method="walk_away"
    ),
    RandomEvent(
        name="Genie",
        template_path="random_events/genie_npc.png",
        dialog_template="random_events/genie_dialog.png",
        dismiss_method="walk_away"
    ),
    RandomEvent(
        name="Mime",
        template_path="random_events/mime_npc.png",
        dialog_template="random_events/mime_dialog.png",
        dismiss_method="walk_away"
    ),
    RandomEvent(
        name="Sandwich Lady",
        template_path="random_events/sandwich_lady_npc.png",
        dialog_template="random_events/sandwich_lady_dialog.png",
        dismiss_method="walk_away"
    ),
    RandomEvent(
        name="Bee Keeper",
        template_path="random_events/bee_keeper_npc.png",
        dialog_template="random_events/bee_keeper_dialog.png",
        dismiss_method="walk_away"
    ),
    RandomEvent(
        name="Drunken Dwarf",
        template_path="random_events/drunken_dwarf_npc.png",
        dialog_template="random_events/drunken_dwarf_dialog.png",
        dismiss_method="walk_away"
    ),
    # Pillory event (jail) - more urgent
    RandomEvent(
        name="Pillory Guard",
        template_path="random_events/pillory_guard_npc.png",
        dialog_template="random_events/pillory_interface.png",
        dismiss_method="esc"
    ),
]


class RandomEventHandler:
    """
    Monitors for and handles OSRS random events.
    Should be checked regularly during script loops.
    """

    def __init__(
        self,
        config: dict,
        capture: ScreenCapture,
        vision: Vision,
        input_handler: HumanizedInput,
        color: ColorDetection,
        interfaces: InterfaceManager
    ):
        self.config = config
        self.capture = capture
        self.vision = vision
        self.input = input_handler
        self.color = color
        self.interfaces = interfaces

        self._last_check: float = 0
        self._check_interval: float = 8.0  # seconds between full checks
        self._event_count: int = 0
        self._dismissed: Dict[str, int] = {}

        # Allow disabling specific randoms
        self._disabled: set = set()

    def disable(self, event_name: str):
        self._disabled.add(event_name)

    def check_and_handle(
        self,
        screen: np.ndarray = None,
        force: bool = False
    ) -> Optional[str]:
        """
        Check for random events and handle any found.
        Returns the name of the event handled, or None.
        Should be called in the main script loop.
        """
        now = __import__('time').time()
        if not force and (now - self._last_check) < self._check_interval:
            return None

        self._last_check = now

        if screen is None:
            screen = self.capture.capture_full()
        if screen is None:
            return None

        # First check for dialog-based events (already engaged)
        event = self._check_dialog_event(screen)
        if event:
            logger.warning(f"[Randoms] Dialog event detected: {event.name}")
            self._handle_event(event)
            return event.name

        # Check for NPC presence
        event = self._check_npc_event(screen)
        if event:
            logger.warning(f"[Randoms] NPC event detected: {event.name}")
            self._handle_event(event)
            return event.name

        return None

    def _check_dialog_event(self, screen: np.ndarray) -> Optional[RandomEvent]:
        """Check if we're currently in a random event dialog."""
        for event in KNOWN_RANDOMS:
            if event.name in self._disabled:
                continue
            if not event.dialog_template:
                continue

            match = self.vision.find_template(
                screen, event.dialog_template,
                threshold=event.threshold
            )
            if match:
                return event
        return None

    def _check_npc_event(self, screen: np.ndarray) -> Optional[RandomEvent]:
        """Check for random event NPCs appearing on screen."""
        for event in KNOWN_RANDOMS:
            if event.name in self._disabled:
                continue

            match = self.vision.find_template(
                screen, event.template_path,
                threshold=event.threshold,
                region=event.detection_region
            )
            if match:
                return event
        return None

    def _handle_event(self, event: RandomEvent):
        """Handle a detected random event."""
        self._event_count += 1
        self._dismissed[event.name] = self._dismissed.get(event.name, 0) + 1
        logger.info(f"[Randoms] Handling {event.name} via method: {event.dismiss_method}")

        if event.dismiss_method == "esc":
            self._dismiss_esc()
        elif event.dismiss_method == "walk_away":
            self._dismiss_walk_away()
        elif event.dismiss_method == "click_x":
            self._dismiss_click_x()
        else:
            self._dismiss_walk_away()

    def _dismiss_esc(self):
        """Dismiss by pressing escape."""
        self.input.press_key('escape')
        time.sleep(random.uniform(0.3, 0.6))
        # Press a few more times in case of stacked dialogs
        for _ in range(random.randint(1, 3)):
            if self.interfaces.is_continue_prompt_visible():
                self.interfaces.click_continue()
                time.sleep(random.uniform(0.2, 0.4))
            else:
                break

    def _dismiss_walk_away(self):
        """
        Walk away from the random event NPC.
        OSRS randoms teleport you back if you don't interact; safest approach
        for modern OSRS is to simply dismiss any dialog and keep skilling.
        """
        # Dismiss dialog first if open
        for _ in range(4):
            screen = self.capture.capture_full()
            if self.interfaces.is_continue_prompt_visible(screen):
                self.interfaces.click_continue(screen)
                time.sleep(random.uniform(0.25, 0.45))
            else:
                break

        # Press escape to close any remaining interface
        self.input.press_key('escape')
        time.sleep(random.uniform(0.2, 0.4))

    def _dismiss_click_x(self):
        """Dismiss by clicking the X/close button on an interface."""
        screen = self.capture.capture_full()
        match = self.vision.find_template(
            screen, "interfaces/close_button.png",
            threshold=0.80
        )
        if match:
            self.input.click(match.center_x, match.center_y)
            time.sleep(random.uniform(0.2, 0.4))
        else:
            self._dismiss_esc()

    @property
    def total_handled(self) -> int:
        return self._event_count

    def get_summary(self) -> Dict:
        return {
            "total": self._event_count,
            "by_type": dict(self._dismissed)
        }
