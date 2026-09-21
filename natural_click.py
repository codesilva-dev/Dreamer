"""
Natural Click - Simulates human-like mouse click behavior.

Provides two layers of human-like timing variance:

1. Click hold duration - realistic mouse-down to mouse-up timing.
   Real humans don't produce instantaneous clicks. Typical durations:
     - Fast/reflexive clicks:  50-100ms
     - Normal clicks:          80-150ms
     - Deliberate clicks:     120-250ms
     - Occasional slow press: 200-350ms

2. Delay variance - adds slight natural jitter to any wait/delay.
   Instead of sleeping exactly 2.0s, sleep 2.037s or 1.958s.
   Keeps delays close to the target so UI rendering still has time,
   but removes the robotic precision of exact repeated timings.
"""

import random
import time
import pyautogui


# Default hold duration parameters (seconds)
DEFAULT_HOLD_MIN = 0.055       # Floor: fastest possible human release
DEFAULT_HOLD_MEDIAN = 0.105    # Center of the distribution
DEFAULT_HOLD_MAX = 0.350       # Ceiling: slowest normal hold
DEFAULT_HOLD_SIGMA = 0.040     # Spread of the normal component


class NaturalClick:
    """
    Generates human-like mouse click hold durations and executes clicks
    with realistic mouse-down / mouse-up timing.

    The hold duration follows a right-skewed distribution built from a
    log-normal base with occasional deliberate-press outliers, matching
    observed human click behavior.
    """

    def __init__(self,
                 hold_min=DEFAULT_HOLD_MIN,
                 hold_median=DEFAULT_HOLD_MEDIAN,
                 hold_max=DEFAULT_HOLD_MAX,
                 hold_sigma=DEFAULT_HOLD_SIGMA):
        """
        Args:
            hold_min:    Minimum hold duration in seconds (hard floor).
            hold_median: Central tendency of hold durations.
            hold_max:    Maximum hold duration in seconds (hard ceiling).
            hold_sigma:  Standard deviation controlling spread around median.
        """
        self.hold_min = hold_min
        self.hold_median = hold_median
        self.hold_max = hold_max
        self.hold_sigma = hold_sigma

    def next_hold_duration(self):
        """
        Generate the next click hold duration in seconds.

        Returns:
            float: hold time between mouse-down and mouse-up
        """
        # Base: normal distribution centered on median
        duration = random.gauss(self.hold_median, self.hold_sigma)

        # ~12% chance of a "deliberate" press (slightly longer hold)
        if random.random() < 0.12:
            duration += random.uniform(0.05, 0.15)

        # ~4% chance of a micro-hesitation on release
        if random.random() < 0.04:
            duration += random.uniform(0.10, 0.20)

        # Clamp to bounds
        duration = max(self.hold_min, min(self.hold_max, duration))

        return round(duration, 4)

    def click(self, x=None, y=None, button='left'):
        """
        Perform a single click with natural hold duration.

        If x and y are provided, moves to that position first (using
        pyautogui's current move duration), then clicks. If omitted,
        clicks at the current cursor position.

        Args:
            x: Screen x coordinate (or None for current position)
            y: Screen y coordinate (or None for current position)
            button: Mouse button ('left', 'right', 'middle')
        """
        hold = self.next_hold_duration()

        if x is not None and y is not None:
            pyautogui.moveTo(x, y)

        pyautogui.mouseDown(button=button)
        time.sleep(hold)
        pyautogui.mouseUp(button=button)

        return hold

    def natural_delay(self, target_delay):
        """
        Sleep for approximately *target_delay* seconds with slight human variance.

        The jitter is proportional to the delay size:
          - Delays under 0.3s get +/- up to ~15ms  (tight, for UI micro-waits)
          - Delays 0.3-1.0s  get +/- up to ~50ms
          - Delays over 1.0s  get +/- up to ~5% of the delay

        The result is always >= 50% of the target (never undershoots dangerously)
        so screen rendering still has time to finish.

        Args:
            target_delay: The intended delay in seconds.

        Returns:
            float: the actual delay that was used (seconds)
        """
        if target_delay <= 0:
            return 0.0

        # Scale jitter proportionally to delay size
        if target_delay < 0.3:
            jitter = random.gauss(0, 0.008)
        elif target_delay < 1.0:
            jitter = random.gauss(0, 0.025)
        else:
            jitter = random.gauss(0, target_delay * 0.025)

        actual = target_delay + jitter

        # Never go below half the target or below zero
        actual = max(target_delay * 0.5, actual)

        time.sleep(actual)
        return round(actual, 4)

    def preview(self, count=20):
        """
        Generate a preview of hold durations (for debugging/display).

        Args:
            count: Number of durations to generate

        Returns:
            list of floats (seconds)
        """
        return [self.next_hold_duration() for _ in range(count)]


# Module-level default instance for convenience
_default = NaturalClick()


def natural_click(x=None, y=None, button='left'):
    """
    Module-level convenience function: perform a single natural click.

    Uses the default NaturalClick instance. For custom parameters,
    create your own NaturalClick instance.

    Args:
        x: Screen x coordinate (or None for current position)
        y: Screen y coordinate (or None for current position)
        button: Mouse button ('left', 'right', 'middle')

    Returns:
        float: the hold duration used (seconds)
    """
    return _default.click(x, y, button)


def natural_delay(target_delay):
    """
    Module-level convenience function: sleep with natural variance.

    Args:
        target_delay: The intended delay in seconds.

    Returns:
        float: the actual delay used (seconds)
    """
    return _default.natural_delay(target_delay)
