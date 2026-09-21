"""
Sum3 — Summon 3 champions quest sequence.

Flow: summonPortal → (next steps TBD)
"""

from natural_click import NaturalClick

from config import (
    TEMPLATE_SUMMON_PORTAL, TEMPLATE_MYSTERY_SHARD,
    TEMPLATE_SUM_BTN, TEMPLATE_SUM_BTN_V2, TEMPLATE_BACK,
)


class Sum3Sequence:
    """Complete the 'Summon 3 Champions' daily quest."""

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
        Run the sum3 sequence.

        Returns:
            True if completed successfully, False on error/abort.
        """
        self.log('')
        self.log('  --- Sum3: Summon 3 Champions ---')

        try:
            self.window_capture.get_window()

            # Step 1: Find and click Summon Portal
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_SUMMON_PORTAL, threshold=0.8
            )
            if not found:
                self.log('  Summon Portal not found — skipping')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_SUMMON_PORTAL, wait_after=1.5
            )
            self.log('  Clicked Summon Portal')

            if self.should_stop():
                return False

            # Step 2: Find and click Mystery Shard
            self.clicker.natural_delay(1.0)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_MYSTERY_SHARD, threshold=0.8
            )
            if not found:
                self.log('  Mystery Shard not found')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_MYSTERY_SHARD, wait_after=1.5
            )
            self.log('  Clicked Mystery Shard')

            if self.should_stop():
                return False

            # Step 3: Find and click Summon button
            self.clicker.natural_delay(1.0)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_SUM_BTN, threshold=0.8
            )
            if not found:
                self.log('  Summon button not found')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_SUM_BTN, wait_after=1.5
            )
            self.log('  Clicked Summon')

            if self.should_stop():
                return False

            # Step 4: Wait for animation, click SumBtnV2
            self.clicker.natural_delay(5.0)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_SUM_BTN_V2, threshold=0.8
            )
            if not found:
                self.log('  Summon V2 button not found')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_SUM_BTN_V2, wait_after=1.5
            )
            self.log('  Clicked Summon V2')

            if self.should_stop():
                return False

            # Step 5: Wait for animation, click SumBtnV2 again
            self.clicker.natural_delay(5.0)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_SUM_BTN_V2, threshold=0.8
            )
            if not found:
                self.log('  Summon V2 button not found (2nd)')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_SUM_BTN_V2, wait_after=1.5
            )
            self.log('  Clicked Summon V2 (2nd)')

            if self.should_stop():
                return False

            # Step 6: Wait, then click Back
            self.clicker.natural_delay(5.0)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_BACK, threshold=0.8
            )
            if found:
                self.template_matcher.find_and_click(
                    TEMPLATE_BACK, wait_after=1.5
                )
                self.log('  Navigated back')
            else:
                self.log('  Back button not found')

            # Step 7: Click Back a second time
            self.clicker.natural_delay(1.0)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_BACK, threshold=0.8
            )
            if found:
                self.template_matcher.find_and_click(
                    TEMPLATE_BACK, wait_after=1.5
                )
                self.log('  Navigated back (2nd)')
            else:
                self.log('  Back button not found (2nd)')

            return True

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
