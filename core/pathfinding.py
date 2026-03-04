"""
Pathfinding & World Navigation
Handles walking between locations using minimap clicks,
waypoint chains, and basic obstacle avoidance.
"""

import time
import random
import math
import json
import logging
from typing import List, Tuple, Optional, Dict

import numpy as np

from core.screen_capture import ScreenCapture
from core.minimap import MinimapNavigator
from core.player_state import PlayerStateTracker, PlayerState
from core.input_handler import HumanizedInput

logger = logging.getLogger(__name__)

# World coordinate type alias
Tile = Tuple[int, int]  # (x, y) in OSRS world coordinates


class Waypoint:
    """A single navigation waypoint."""

    def __init__(self, x: int, y: int, label: str = "", radius: int = 3):
        self.x = x
        self.y = y
        self.label = label
        self.radius = radius  # Acceptable arrival radius in tiles

    def distance_to(self, other: "Waypoint") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def __repr__(self):
        return f"Waypoint({self.x}, {self.y} '{self.label}')"


class PathFinder:
    """
    Handles navigation in OSRS using minimap clicks and waypoint sequences.
    Does not implement A* over the full tile map — instead uses high-level
    waypoints and visual minimap feedback to walk routes.
    """

    # Pixels per OSRS tile on the minimap at default zoom
    MM_PX_PER_TILE = 4.0

    # Maximum tiles to click per minimap step (~65 tiles at max click)
    MAX_CLICK_TILES = 15

    def __init__(
        self,
        config: dict,
        capture: ScreenCapture,
        minimap: MinimapNavigator,
        player_tracker: PlayerStateTracker,
        input_handler: HumanizedInput,
        locations_db_path: str = "data/locations.json"
    ):
        self.config = config
        self.capture = capture
        self.minimap = minimap
        self.player = player_tracker
        self.input = input_handler

        self._locations: Dict[str, Tile] = {}
        self._load_locations(locations_db_path)

        self._current_tile: Optional[Tile] = None
        self._destination: Optional[Tile] = None

    def _load_locations(self, path: str):
        """Load named location coordinates from JSON database."""
        try:
            with open(path) as f:
                data = json.load(f)
            for name, coords in data.items():
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    self._locations[name.lower()] = (coords[0], coords[1])
            logger.debug(f"[Pathfinding] Loaded {len(self._locations)} locations")
        except FileNotFoundError:
            logger.debug("[Pathfinding] locations.json not found; no preset locations loaded")
        except Exception as e:
            logger.warning(f"[Pathfinding] Error loading locations: {e}")

    # ------------------------------------------------------------------
    # High-level walking
    # ------------------------------------------------------------------

    def walk_to(
        self,
        destination: Tile,
        current_tile: Tile = None,
        timeout: float = 60.0,
        arrival_radius: int = 5,
        waypoints: List[Tile] = None
    ) -> bool:
        """
        Walk to a destination tile using minimap clicks.
        If waypoints are provided, visits each in sequence.
        Returns True if destination reached within timeout.
        """
        self._destination = destination

        if waypoints:
            for wp_tile in waypoints:
                success = self._walk_to_tile(
                    wp_tile, current_tile,
                    timeout=timeout / len(waypoints),
                    arrival_radius=arrival_radius
                )
                if not success:
                    logger.warning(f"[Pathfinding] Failed to reach waypoint {wp_tile}")
                    return False

        return self._walk_to_tile(destination, current_tile, timeout, arrival_radius)

    def walk_to_named(self, location_name: str, **kwargs) -> bool:
        """Walk to a named location from the locations database."""
        tile = self._locations.get(location_name.lower())
        if not tile:
            logger.warning(f"[Pathfinding] Unknown location: {location_name}")
            return False
        return self.walk_to(tile, **kwargs)

    def _walk_to_tile(
        self,
        destination: Tile,
        current_tile: Optional[Tile],
        timeout: float,
        arrival_radius: int
    ) -> bool:
        """Core walk loop: repeatedly click minimap toward destination."""
        start = time.time()
        dest_x, dest_y = destination

        while (time.time() - start) < timeout:
            # Estimate remaining distance
            if current_tile:
                cur_x, cur_y = current_tile
                dist_tiles = math.hypot(dest_x - cur_x, dest_y - cur_y)
                if dist_tiles <= arrival_radius:
                    logger.debug(f"[Pathfinding] Arrived at {destination}")
                    return True

            # Click minimap in direction of destination
            if current_tile:
                self._click_towards(current_tile, destination)
            else:
                # Without current position, use directional minimap click
                self._click_minimap_toward_destination(destination)

            # Wait for player to walk
            walked = self.player.wait_until_idle(timeout=8.0, poll_interval=0.4)
            if not walked:
                # Player didn't stop — might be stuck
                logger.debug("[Pathfinding] Player movement timeout, retrying")

            time.sleep(random.uniform(0.1, 0.3))

        logger.warning(f"[Pathfinding] Timed out walking to {destination}")
        return False

    def _click_towards(self, current: Tile, destination: Tile):
        """Click the minimap toward the destination tile."""
        cur_x, cur_y = current
        dest_x, dest_y = destination

        # Vector from current to dest
        dx_tiles = dest_x - cur_x
        dy_tiles = dest_y - cur_y
        dist = math.hypot(dx_tiles, dy_tiles)

        # Clamp to max click distance
        if dist > self.MAX_CLICK_TILES:
            scale = self.MAX_CLICK_TILES / dist
            dx_tiles *= scale
            dy_tiles *= scale

        # Convert to minimap pixels (Y is inverted)
        mm_dx = int(dx_tiles * self.MM_PX_PER_TILE)
        mm_dy = int(-dy_tiles * self.MM_PX_PER_TILE)  # Minimap Y is flipped

        self.minimap.click_tile(mm_dx, mm_dy)

    def _click_minimap_toward_destination(self, destination: Tile):
        """
        Fallback: click the minimap edge in the general direction without
        knowing precise current position. Uses last known movement direction.
        """
        # Click near max range in a random direction
        angle = random.uniform(0, 2 * math.pi)
        reach = self.minimap.MM_RADIUS * 0.8
        dx = int(math.cos(angle) * reach)
        dy = int(math.sin(angle) * reach)
        self.minimap.click_tile(dx, dy)

    # ------------------------------------------------------------------
    # Tile estimation from minimap
    # ------------------------------------------------------------------

    def estimate_position_from_minimap(
        self,
        screen: np.ndarray,
        reference_tile: Tile,
        reference_screen_pos: Tuple[int, int]
    ) -> Optional[Tile]:
        """
        Estimate current world tile by comparing a known reference point
        on the minimap to the current player dot position.
        """
        player_dot = self.minimap.find_player_dot(screen)
        if not player_dot:
            return None

        ref_x, ref_y = reference_screen_pos
        dot_x, dot_y = player_dot

        dx_px = dot_x - ref_x
        dy_px = dot_y - ref_y

        # Convert back to tiles (Y flipped)
        tile_dx = int(dx_px / self.MM_PX_PER_TILE)
        tile_dy = int(-dy_px / self.MM_PX_PER_TILE)

        ref_tx, ref_ty = reference_tile
        return (ref_tx + tile_dx, ref_ty + tile_dy)

    # ------------------------------------------------------------------
    # Route utilities
    # ------------------------------------------------------------------

    def build_route(self, start: Tile, end: Tile, step_size: int = 12) -> List[Tile]:
        """
        Build a straight-line route of tiles from start to end.
        In practice routes should be handcrafted for obstacle avoidance.
        """
        sx, sy = start
        ex, ey = end
        dist = math.hypot(ex - sx, ey - sy)
        steps = max(1, int(dist / step_size))

        route = []
        for i in range(1, steps + 1):
            t = i / steps
            x = int(sx + (ex - sx) * t)
            y = int(sy + (ey - sy) * t)
            route.append((x, y))

        return route

    def get_named_location(self, name: str) -> Optional[Tile]:
        return self._locations.get(name.lower())

    def register_location(self, name: str, tile: Tile):
        self._locations[name.lower()] = tile
