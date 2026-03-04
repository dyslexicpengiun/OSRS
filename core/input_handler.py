"""
Humanized Input Handler using Interception Driver
All inputs go through the interception driver so they appear as
genuine hardware events with no synthetic flags.

Uses cubic spline curves (no bezier library needed) for natural mouse movement.
"""

import time
import random
import math
import threading
import ctypes
from typing import Optional, Tuple, List

import numpy as np
from scipy.interpolate import CubicSpline

try:
    import interception
    INTERCEPTION_AVAILABLE = True
except ImportError:
    INTERCEPTION_AVAILABLE = False
    print("[WARNING] interception-python not available. Falling back to ctypes SendInput.")


# Windows constants for fallback
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT)
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUT_UNION)
    ]


class HumanizedInput:
    """
    Provides humanized mouse movement and keyboard input through
    the Interception driver for hardware-level authenticity.
    """

    def __init__(self, config: dict, capture=None):
        self.config = config
        self.global_settings = config.get("global_settings", {})
        # Optional ScreenCapture reference for automatic window→screen conversion
        self._capture = capture

        # Mouse speed parameters
        self.speed_min = self.global_settings.get("mouse_speed_min", 0.08)
        self.speed_max = self.global_settings.get("mouse_speed_max", 0.35)
        self.click_delay_min = self.global_settings.get("click_delay_min", 45)
        self.click_delay_max = self.global_settings.get("click_delay_max", 180)
        self.misclick_chance = self.global_settings.get("misclick_chance", 0.008)

        # Current mouse position tracking
        self._current_x = 0
        self._current_y = 0
        self._lock = threading.Lock()

        # Fatigue simulation
        self._session_start = time.time()
        self._action_count = 0
        self._fatigue_enabled = self.global_settings.get("fatigue_enabled", True)

        # Initialize interception
        self._interception_ctx = None
        self._mouse_device = None
        self._keyboard_device = None

        if INTERCEPTION_AVAILABLE:
            self._init_interception()
        else:
            print("[INPUT] Using SendInput fallback - inputs may have synthetic tags")

        # Initialize position from current cursor
        self._sync_cursor_position()

    def _init_interception(self):
        """Initialize the interception driver context."""
        try:
            self._interception_ctx = interception.auto_capture_devices(
                keyboard=True,
                mouse=True
            )
            print("[INPUT] Interception driver initialized successfully")
        except Exception as e:
            print(f"[INPUT] Interception init failed: {e}")
            print("[INPUT] Falling back to SendInput")

    def _sync_cursor_position(self):
        """Sync internal position tracking with actual cursor position."""
        try:
            point = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
            self._current_x = point.x
            self._current_y = point.y
        except Exception:
            pass

    def _get_fatigue_multiplier(self) -> float:
        """
        Returns a multiplier that increases with session time,
        simulating human fatigue (slower, less precise movements).
        """
        if not self._fatigue_enabled:
            return 1.0

        elapsed_hours = (time.time() - self._session_start) / 3600
        # Logarithmic fatigue curve: starts at 1.0, slowly increases
        fatigue = 1.0 + 0.15 * math.log1p(elapsed_hours)
        # Cap at 1.5x slowdown
        return min(fatigue, 1.5)

    def _generate_human_curve(
        self,
        start_x: float, start_y: float,
        end_x: float, end_y: float,
        num_points: int = None
    ) -> List[Tuple[int, int]]:
        """
        Generate a natural-looking mouse movement curve using cubic splines
        with random control points that simulate human hand tremor and overshoot.
        """
        distance = math.hypot(end_x - start_x, end_y - start_y)

        if distance < 3:
            return [(int(end_x), int(end_y))]

        # Number of intermediate control points scales with distance
        if num_points is None:
            num_points = max(15, min(int(distance / 8), 80))

        # Generate control points with human-like characteristics
        num_controls = random.randint(2, max(3, min(int(distance / 100), 6)))

        # Parametric t values for control points
        t_controls = sorted([0.0] + [random.uniform(0.1, 0.9) for _ in range(num_controls)] + [1.0])

        # Generate control point positions with randomness
        cx_points = []
        cy_points = []

        for i, t in enumerate(t_controls):
            # Linear interpolation as base
            base_x = start_x + (end_x - start_x) * t
            base_y = start_y + (end_y - start_y) * t

            if i == 0:
                cx_points.append(start_x)
                cy_points.append(start_y)
            elif i == len(t_controls) - 1:
                cx_points.append(end_x)
                cy_points.append(end_y)
            else:
                # Perpendicular offset for natural curve
                # Bigger offset for longer distances, but capped
                max_offset = min(distance * 0.12, 60) * self._get_fatigue_multiplier()
                offset_x = random.gauss(0, max_offset * 0.4)
                offset_y = random.gauss(0, max_offset * 0.4)

                cx_points.append(base_x + offset_x)
                cy_points.append(base_y + offset_y)

        # Build cubic spline
        t_array = np.array(t_controls)
        cx_array = np.array(cx_points)
        cy_array = np.array(cy_points)

        try:
            spline_x = CubicSpline(t_array, cx_array)
            spline_y = CubicSpline(t_array, cy_array)
        except Exception:
            # Fallback to simple linear if spline fails
            points = []
            for i in range(num_points):
                t = i / (num_points - 1)
                x = int(start_x + (end_x - start_x) * t)
                y = int(start_y + (end_y - start_y) * t)
                points.append((x, y))
            return points

        # Sample the spline
        t_samples = np.linspace(0, 1, num_points)
        path_x = spline_x(t_samples)
        path_y = spline_y(t_samples)

        # Add micro-tremor (subtle noise simulating hand shake)
        tremor_magnitude = 0.5 + 0.3 * self._get_fatigue_multiplier()
        for i in range(1, len(path_x) - 1):
            path_x[i] += random.gauss(0, tremor_magnitude)
            path_y[i] += random.gauss(0, tremor_magnitude)

        # Occasional overshoot near the end (human tendency)
        if distance > 80 and random.random() < 0.15:
            overshoot_amount = random.uniform(2, min(8, distance * 0.03))
            direction_x = (end_x - start_x) / max(distance, 1)
            direction_y = (end_y - start_y) / max(distance, 1)
            # Insert overshoot point near the end
            overshoot_idx = int(num_points * random.uniform(0.85, 0.95))
            if overshoot_idx < len(path_x):
                path_x[overshoot_idx] = end_x + direction_x * overshoot_amount
                path_y[overshoot_idx] = end_y + direction_y * overshoot_amount

        # Build final point list
        points = []
        prev_x, prev_y = -1, -1
        for x, y in zip(path_x, path_y):
            ix, iy = int(round(x)), int(round(y))
            if ix != prev_x or iy != prev_y:
                points.append((ix, iy))
                prev_x, prev_y = ix, iy

        # Ensure we end exactly at target
        if points and points[-1] != (int(end_x), int(end_y)):
            points.append((int(end_x), int(end_y)))

        return points

    def _calculate_move_duration(self, distance: float) -> float:
        """
        Calculate how long a mouse movement should take based on
        Fitts' Law approximation with human variance.
        """
        if distance < 2:
            return 0.01

        # Base time using Fitts' law-like formula
        a = random.uniform(0.05, 0.08)  # Base time
        b = random.uniform(0.08, 0.15)  # Distance scaling
        base_duration = a + b * math.log2(1 + distance / 10)

        # Apply fatigue
        base_duration *= self._get_fatigue_multiplier()

        # Add human variance (±20%)
        variance = random.gauss(1.0, 0.1)
        variance = max(0.7, min(1.3, variance))
        duration = base_duration * variance

        # Clamp to reasonable range
        return max(self.speed_min, min(self.speed_max * 2, duration))

    def _generate_timing_profile(self, num_points: int, duration: float) -> List[float]:
        """
        Generate non-uniform timing for mouse movement points.
        Humans accelerate, then decelerate (bell curve velocity profile).
        """
        if num_points <= 1:
            return [duration]

        # Generate a velocity profile using a modified sine curve
        # This creates smooth acceleration/deceleration
        t_normalized = np.linspace(0, math.pi, num_points)
        velocity_profile = np.sin(t_normalized)

        # Avoid division by zero
        velocity_sum = velocity_profile.sum()
        if velocity_sum == 0:
            velocity_profile = np.ones(num_points)
            velocity_sum = num_points

        # Convert velocity to time intervals
        # Higher velocity = shorter time at that point
        inverse_velocity = 1.0 / (velocity_profile + 0.1)
        time_fractions = inverse_velocity / inverse_velocity.sum()
        time_intervals = time_fractions * duration

        return time_intervals.tolist()


    def _to_screen(self, x: int, y: int):
        """
        Convert game-window-relative coordinates to absolute screen coordinates.
        All template match results are in window-relative space; the OS expects
        absolute screen coordinates for mouse movement.
        """
        if self._capture is not None:
            return self._capture.game_to_screen(x, y)
        return (x, y)

    def _move_mouse_raw(self, x: int, y: int):
        """Move mouse to absolute position using interception or fallback."""
        if INTERCEPTION_AVAILABLE and self._interception_ctx:
            try:
                interception.move_to(x, y)
                self._current_x = x
                self._current_y = y
                return
            except Exception:
                pass

        # Fallback: use ctypes SetCursorPos
        ctypes.windll.user32.SetCursorPos(x, y)
        self._current_x = x
        self._current_y = y

    def _click_raw(self, button: str = "left"):
        """Perform a raw click using interception or fallback."""
        if INTERCEPTION_AVAILABLE and self._interception_ctx:
            try:
                if button == "left":
                    interception.click()
                elif button == "right":
                    interception.right_click()
                return
            except Exception:
                pass

        # Fallback: SendInput
        if button == "left":
            self._send_input_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
        elif button == "right":
            self._send_input_click(MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)

    def _send_input_click(self, down_flag: int, up_flag: int):
        """Send a click using Windows SendInput as fallback."""
        down = INPUT()
        down.type = INPUT_MOUSE
        down.union.mi.dwFlags = down_flag

        up = INPUT()
        up.type = INPUT_MOUSE
        up.union.mi.dwFlags = up_flag

        # Human-like click duration
        ctypes.windll.user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        time.sleep(random.uniform(0.04, 0.12))
        ctypes.windll.user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))

    def _press_key_raw(self, scan_code: int, release: bool = False):
        """Press/release a key using interception or fallback."""
        if INTERCEPTION_AVAILABLE and self._interception_ctx:
            try:
                if release:
                    interception.key_up(scan_code)
                else:
                    interception.key_down(scan_code)
                return
            except Exception:
                pass

        # Fallback
        ki = INPUT()
        ki.type = INPUT_KEYBOARD
        ki.union.ki.wScan = scan_code
        ki.union.ki.dwFlags = KEYEVENTF_SCANCODE
        if release:
            ki.union.ki.dwFlags |= KEYEVENTF_KEYUP
        ctypes.windll.user32.SendInput(1, ctypes.byref(ki), ctypes.sizeof(INPUT))

    def move_to(self, x: int, y: int, variance: int = 2):
        """
        Move mouse to target position with humanized curve.

        Args:
            x: Target x position (screen coordinates)
            y: Target y position (screen coordinates)
            variance: Random offset from target (simulates imprecision)
        """
        with self._lock:
            self._sync_cursor_position()

            # Add targeting variance (humans don't click exact center)
            if variance > 0:
                target_x = x + random.randint(-variance, variance)
                target_y = y + random.randint(-variance, variance)
            else:
                target_x = x
                target_y = y

            # Generate the movement curve
            points = self._generate_human_curve(
                self._current_x, self._current_y,
                target_x, target_y
            )

            if not points:
                return

            # Calculate duration
            distance = math.hypot(target_x - self._current_x, target_y - self._current_y)
            duration = self._calculate_move_duration(distance)

            # Generate timing
            timings = self._generate_timing_profile(len(points), duration)

            # Execute movement
            for i, (px, py) in enumerate(points):
                self._move_mouse_raw(px, py)
                if i < len(timings):
                    time.sleep(timings[i])

            self._action_count += 1

    def move_to_with_randomness(self, x: int, y: int, x_range: int = 5, y_range: int = 5):
        """Move to a position with larger random area (e.g., for clicking game objects)."""
        offset_x = random.randint(-x_range, x_range)
        offset_y = random.randint(-y_range, y_range)
        self.move_to(x + offset_x, y + offset_y, variance=1)

    def click(self, x: int = None, y: int = None, button: str = "left",
              variance: int = 2, double: bool = False):
        """
        Click at position with humanized movement.

        Args:
            x, y: Target position. If None, clicks at current position.
            button: "left" or "right"
            variance: Click position variance
            double: Double-click if True
        """
        with self._lock:
            if x is not None and y is not None:
                # Release lock temporarily for move
                pass

        if x is not None and y is not None:
            x, y = self._to_screen(x, y)
            self.move_to(x, y, variance=variance)

        # Pre-click delay (human reaction time)
        pre_delay = random.uniform(
            self.click_delay_min / 1000,
            self.click_delay_max / 1000
        )
        time.sleep(pre_delay * self._get_fatigue_multiplier())

        # Simulate misclick
        if random.random() < self.misclick_chance:
            # Click slightly off target, then correct
            self._sync_cursor_position()
            off_x = self._current_x + random.randint(-15, 15)
            off_y = self._current_y + random.randint(-15, 15)
            self._move_mouse_raw(off_x, off_y)
            self._click_raw(button)
            time.sleep(random.uniform(0.2, 0.5))
            # Move back and click correctly
            if x is not None and y is not None:
                self.move_to(x, y, variance=variance)
                self._click_raw(button)
            return

        # Normal click
        self._click_raw(button)

        if double:
            time.sleep(random.uniform(0.05, 0.12))
            self._click_raw(button)

        # Post-click micro-delay
        time.sleep(random.uniform(0.02, 0.08))

    def right_click(self, x: int = None, y: int = None, variance: int = 2):
        """Right-click at position."""
        self.click(x, y, button="right", variance=variance)

    def press_key(self, key: str, duration: float = None):
        """
        Press a key with humanized timing.

        Args:
            key: Key name (e.g., 'space', 'escape', '1', 'f1', etc.)
            duration: How long to hold. If None, uses random short duration.
        """
        scan_code = self._key_to_scancode(key)
        if scan_code is None:
            return

        if duration is None:
            duration = random.uniform(0.04, 0.12)

        self._press_key_raw(scan_code, release=False)
        time.sleep(duration * self._get_fatigue_multiplier())
        self._press_key_raw(scan_code, release=True)

        # Post-key delay
        time.sleep(random.uniform(0.02, 0.06))

    def type_text(self, text: str, wpm: float = None):
        """
        Type text with humanized per-character timing.

        Args:
            text: String to type
            wpm: Words per minute. If None, uses random 40-80 WPM.
        """
        if wpm is None:
            wpm = random.uniform(40, 80)

        # Average 5 chars per word
        chars_per_second = (wpm * 5) / 60
        base_delay = 1.0 / chars_per_second

        for i, char in enumerate(text):
            scan_code = self._char_to_scancode(char)
            if scan_code is not None:
                needs_shift = char.isupper() or char in '!@#$%^&*()_+{}|:"<>?'

                if needs_shift:
                    self._press_key_raw(0x2A, release=False)  # Left Shift
                    time.sleep(random.uniform(0.02, 0.05))

                self._press_key_raw(scan_code, release=False)
                time.sleep(random.uniform(0.03, 0.08))
                self._press_key_raw(scan_code, release=True)

                if needs_shift:
                    time.sleep(random.uniform(0.02, 0.04))
                    self._press_key_raw(0x2A, release=True)

                # Inter-key delay with variance
                delay = base_delay * random.uniform(0.6, 1.8)
                # Occasional longer pause (thinking)
                if random.random() < 0.05:
                    delay += random.uniform(0.2, 0.5)
                time.sleep(delay)

    def scroll(self, direction: str = "down", clicks: int = 3):
        """
        Scroll mouse wheel.

        Args:
            direction: "up" or "down"
            clicks: Number of scroll clicks
        """
        if INTERCEPTION_AVAILABLE and self._interception_ctx:
            try:
                for _ in range(clicks):
                    if direction == "up":
                        interception.scroll_up()
                    else:
                        interception.scroll_down()
                    time.sleep(random.uniform(0.05, 0.15))
                return
            except Exception:
                pass

        # Fallback using ctypes
        MOUSEEVENTF_WHEEL = 0x0800
        WHEEL_DELTA = 120
        for _ in range(clicks):
            mi = INPUT()
            mi.type = INPUT_MOUSE
            mi.union.mi.dwFlags = MOUSEEVENTF_WHEEL
            mi.union.mi.mouseData = WHEEL_DELTA if direction == "up" else -WHEEL_DELTA
            ctypes.windll.user32.SendInput(1, ctypes.byref(mi), ctypes.sizeof(INPUT))
            time.sleep(random.uniform(0.05, 0.15))

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, button: str = "left"):
        """
        Drag from start to end with humanized movement.
        button: "left", "right", or "middle"
        """
        # Windows constants for middle mouse
        MOUSEEVENTF_MIDDLEDOWN = 0x0020
        MOUSEEVENTF_MIDDLEUP   = 0x0040

        self.move_to(start_x, start_y)
        time.sleep(random.uniform(0.05, 0.15))

        # Mouse down
        if INTERCEPTION_AVAILABLE and self._interception_ctx:
            try:
                if button == "left":
                    interception.mouse_down("left")
                elif button == "right":
                    interception.mouse_down("right")
                else:
                    # middle — interception may not expose middle, fall through to SendInput
                    raise Exception("middle not in interception")
            except Exception:
                if button == "middle":
                    flag = MOUSEEVENTF_MIDDLEDOWN
                elif button == "right":
                    flag = MOUSEEVENTF_RIGHTDOWN
                else:
                    flag = MOUSEEVENTF_LEFTDOWN
                mi = INPUT()
                mi.type = INPUT_MOUSE
                mi.union.mi.dwFlags = flag
                ctypes.windll.user32.SendInput(1, ctypes.byref(mi), ctypes.sizeof(INPUT))
        else:
            if button == "middle":
                flag = MOUSEEVENTF_MIDDLEDOWN
            elif button == "right":
                flag = MOUSEEVENTF_RIGHTDOWN
            else:
                flag = MOUSEEVENTF_LEFTDOWN
            mi = INPUT()
            mi.type = INPUT_MOUSE
            mi.union.mi.dwFlags = flag
            ctypes.windll.user32.SendInput(1, ctypes.byref(mi), ctypes.sizeof(INPUT))

        time.sleep(random.uniform(0.08, 0.2))

        # Move to destination
        self._sync_cursor_position()
        points = self._generate_human_curve(
            self._current_x, self._current_y,
            end_x, end_y
        )
        distance = math.hypot(end_x - self._current_x, end_y - self._current_y)
        duration = self._calculate_move_duration(distance) * 1.3  # Drags are slower
        timings = self._generate_timing_profile(len(points), duration)

        for i, (px, py) in enumerate(points):
            self._move_mouse_raw(px, py)
            if i < len(timings):
                time.sleep(timings[i])

        time.sleep(random.uniform(0.05, 0.12))

        # Mouse up
        if INTERCEPTION_AVAILABLE and self._interception_ctx:
            try:
                if button == "left":
                    interception.mouse_up("left")
                elif button == "right":
                    interception.mouse_up("right")
                else:
                    raise Exception("middle not in interception")
            except Exception:
                if button == "middle":
                    flag = 0x0040  # MOUSEEVENTF_MIDDLEUP
                elif button == "right":
                    flag = MOUSEEVENTF_RIGHTUP
                else:
                    flag = MOUSEEVENTF_LEFTUP
                mi = INPUT()
                mi.type = INPUT_MOUSE
                mi.union.mi.dwFlags = flag
                ctypes.windll.user32.SendInput(1, ctypes.byref(mi), ctypes.sizeof(INPUT))
        else:
            if button == "middle":
                flag = 0x0040  # MOUSEEVENTF_MIDDLEUP
            elif button == "right":
                flag = MOUSEEVENTF_RIGHTUP
            else:
                flag = MOUSEEVENTF_LEFTUP
            mi = INPUT()
            mi.type = INPUT_MOUSE
            mi.union.mi.dwFlags = flag
            ctypes.windll.user32.SendInput(1, ctypes.byref(mi), ctypes.sizeof(INPUT))

    def get_position(self) -> Tuple[int, int]:
        """Get current mouse position."""
        self._sync_cursor_position()
        return (self._current_x, self._current_y)

    def reset_fatigue(self):
        """Reset fatigue counter (call after breaks)."""
        self._session_start = time.time()
        self._action_count = 0

    def _key_to_scancode(self, key: str) -> Optional[int]:
        """Convert key name to scan code."""
        key_map = {
            'escape': 0x01, 'esc': 0x01,
            '1': 0x02, '2': 0x03, '3': 0x04, '4': 0x05,
            '5': 0x06, '6': 0x07, '7': 0x08, '8': 0x09,
            '9': 0x0A, '0': 0x0B,
            'minus': 0x0C, 'equals': 0x0D, 'backspace': 0x0E,
            'tab': 0x0F,
            'q': 0x10, 'w': 0x11, 'e': 0x12, 'r': 0x13,
            't': 0x14, 'y': 0x15, 'u': 0x16, 'i': 0x17,
            'o': 0x18, 'p': 0x19,
            'enter': 0x1C, 'return': 0x1C,
            'lctrl': 0x1D, 'ctrl': 0x1D,
            'a': 0x1E, 's': 0x1F, 'd': 0x20, 'f': 0x21,
            'g': 0x22, 'h': 0x23, 'j': 0x24, 'k': 0x25,
            'l': 0x26,
            'lshift': 0x2A, 'shift': 0x2A,
            'z': 0x2C, 'x': 0x2D, 'c': 0x2E, 'v': 0x2F,
            'b': 0x30, 'n': 0x31, 'm': 0x32,
            'space': 0x39,
            'f1': 0x3B, 'f2': 0x3C, 'f3': 0x3D, 'f4': 0x3E,
            'f5': 0x3F, 'f6': 0x40, 'f7': 0x41, 'f8': 0x42,
            'f9': 0x43, 'f10': 0x44, 'f11': 0x57, 'f12': 0x58,
            'up': 0x48, 'down': 0x50, 'left': 0x4B, 'right': 0x4D,
        }
        return key_map.get(key.lower())

    def _char_to_scancode(self, char: str) -> Optional[int]:
        """Convert a character to its scan code."""
        return self._key_to_scancode(char.lower())