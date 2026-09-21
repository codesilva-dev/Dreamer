"""
Dismiss Junk Offers — Click the X button on popup offers that block the home screen.

Detects the close (X) button on popup offers via template matching
and clicks it to dismiss. Loops until no more are found.
"""

import pyautogui
from natural_click import NaturalClick

from config import TEMPLATE_CLOSE_OFFER


class DismissJunkOffersSequence:
    """Dismiss all popup junk offers on screen."""

    def __init__(self, window_capture, template_matcher, log_func=None,
                 stop_check=None):
        self.window_capture = window_capture
        self.template_matcher = template_matcher
        self.log = log_func or print
        self.stop_check = stop_check
        self.clicker = NaturalClick()

    def should_stop(self):
        return self.stop_check and self.stop_check()

    def run(self):
        """
        Dismiss junk offers until none remain.

        Returns:
            True if completed (even if none found).
        """
        self.log('')
        self.log('  --- Dismiss Junk Offers ---')

        try:
            self.window_capture.get_window()

            dismissed = 0
            while not self.should_stop():
                self.clicker.natural_delay(1.0)
                found, location, _ = self.template_matcher.find_template(
                    TEMPLATE_CLOSE_OFFER, threshold=0.8
                )
                if not found:
                    break

                dismissed += 1
                left, top, _, _ = self.window_capture.window_info
                abs_x = left + location[0]
                abs_y = top + location[1]
                self.log(f'  Dismissing junk offer #{dismissed}...')
                pyautogui.moveTo(abs_x, abs_y, duration=0.3)
                self.clicker.natural_delay(0.2)
                self.clicker.click()

            if dismissed:
                self.log(f'  Dismissed {dismissed} junk offer(s)')
            else:
                self.log(f'  No junk offers found')

            return True

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
