"""
Agility Script
Runs rooftop agility courses using obstacle template matching.
Delegates to RooftopCourse for course-specific obstacle sequences.
"""
import time, random, logging
from enum import Enum, auto
from scripts.base_script import BaseScript
from scripts.agility.rooftop_courses import COURSES, RooftopCourse

logger = logging.getLogger(__name__)

class AgilityState(Enum):
    START=auto(); OBSTACLE=auto(); COLLECT_MARKS=auto(); EAT=auto()

class AgilityScript(BaseScript):
    def __init__(self, engine, script_config=None):
        super().__init__(engine, script_config)
        c = self.script_config
        self.course_name  = c.get("course","gnome_stronghold")
        self.eat_food     = c.get("eat_food", True)
        self.food_template= c.get("food_template","inventory/salmon.png")
        self.hp_threshold = c.get("hp_threshold", 0.45)

        course_data = COURSES.get(self.course_name)
        if not course_data:
            raise ValueError(f"Unknown agility course: {self.course_name}")
        self._course = RooftopCourse(course_data)
        self._state  = AgilityState.START
        self._laps   = 0

    def setup(self) -> bool:
        self.log(f"Agility: {self.course_name}")
        self.engine.camera.set_max_pitch()
        time.sleep(random.uniform(0.5,1.0))
        return True

    def loop(self) -> bool:
        e = self.engine
        screen = e.screenshot()

        # Health check
        if self.eat_food:
            hp = e.game_state.health
            if hp < self.hp_threshold:
                self._eat_food(screen)
                return True

        if self._state == AgilityState.START:
            self._course.reset()
            self._state = AgilityState.OBSTACLE

        elif self._state == AgilityState.OBSTACLE:
            obstacle = self._course.current_obstacle()
            if obstacle is None:
                # Completed lap
                self._laps += 1
                self.stats.items_gained = self._laps
                xp = self._course.data.get("xp_per_lap", 100)
                self.stats.add_xp("agility", xp)
                self.log(f"Lap {self._laps} complete. XP: {self.stats.xp_gained.get('agility',0):,}")
                self._state = AgilityState.START
                return True

            success = self._do_obstacle(obstacle, screen)
            if success:
                self._course.advance()
                e.player.wait_until_idle(timeout=15)
                time.sleep(random.uniform(0.15, 0.4))
            else:
                time.sleep(1.5)

        return True

    def _do_obstacle(self, obstacle: dict, screen) -> bool:
        e = self.engine
        tmpl = obstacle.get("template","")
        region = obstacle.get("region", None)

        match = e.vision.find_template(screen, tmpl, threshold=0.78, region=region)
        if match:
            e.input.click(match.center_x + random.randint(-8,8),
                           match.center_y + random.randint(-8,8))
            time.sleep(e.antiban.reaction_delay())
            return True

        # Fallback: click the region center
        if region:
            rx, ry, rw, rh = region
            e.input.click(rx + rw//2 + random.randint(-10,10),
                           ry + rh//2 + random.randint(-10,10))
            return True
        return False

    def _eat_food(self, screen):
        slot = self.engine.inventory.find_item(self.food_template, screen)
        if slot:
            self.engine.inventory.click_slot(slot.index)
            time.sleep(random.uniform(0.3, 0.7))

    def get_paint_data(self):
        xp = self.stats.xp_gained.get("agility", 0)
        return {"Script": f"Agility ({self.course_name})", "Laps": self._laps,
                "XP": f"{xp:,}", "XP/hr": f"{self.stats.xp_per_hour('agility'):,.0f}",
                "Runtime": self._format_elapsed()}
