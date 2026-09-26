"""
Playtime Rewards — Collect all available playtime rewards.

Flow:
  1. Click AccruedRewards icon on home screen
  2. Check for PT1.png through PT9.png and click each visible reward
  3. Click closeoffer (X) to close the rewards panel
"""

import os
from natural_click import NaturalClick

from config import (
    TEMPLATE_ACCRUED_REWARDS,
    TEMPLATE_CLOSE_OFFER,
    TEMPLATE_PT1,
    TEMPLATE_PT2,
    TEMPLATE_PT3,
    TEMPLATE_PT4,
    TEMPLATE_PT5,
    TEMPLATE_PT6,
    TEMPLATE_PT7,
    TEMPLATE_PT8,
    TEMPLATE_PT9,
)


class PlaytimeRewardsSequence:
    """Open playtime rewards and collect all available ones."""

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
        Run the playtime rewards sequence.

        Returns:
            True if completed successfully, False on error/abort.
        """
        self.log('')
        self.log('  --- Playtime Rewards ---')

        try:
            self.window_capture.get_window()

            # Step 1: Click AccruedRewards icon
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_ACCRUED_REWARDS, threshold=0.89
            )
            if not found:
                self.log('  AccruedRewards not found — skipping')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_ACCRUED_REWARDS, wait_after=2.0
            )
            self.log('  Clicked AccruedRewards')

            if self.should_stop():
                return False

            # Step 2: Check for PT1-PT9 and click each visible reward
            pt_templates = [
                (TEMPLATE_PT1, 'PT1'),
                (TEMPLATE_PT2, 'PT2'),
                (TEMPLATE_PT3, 'PT3'),
                (TEMPLATE_PT4, 'PT4'),
                (TEMPLATE_PT5, 'PT5'),
                (TEMPLATE_PT6, 'PT6'),
                (TEMPLATE_PT7, 'PT7'),
                (TEMPLATE_PT8, 'PT8'),
                (TEMPLATE_PT9, 'PT9'),
            ]

            claimed = 0
            self.clicker.natural_delay(1.0)

            for template, label in pt_templates:
                if self.should_stop():
                    return False

                # Skip PT6 if the file doesn't exist yet
                if not os.path.exists(template):
                    continue

                found, _, _ = self.template_matcher.find_template(
                    template, threshold=0.99
                )
                if found:
                    self.template_matcher.find_and_click(
                        template, wait_after=1.5
                    )
                    self.log(f'  Clicked {label}')
                    claimed += 1
                    self.clicker.natural_delay(0.5)

            if claimed == 0:
                self.log('  No playtime rewards available')
            else:
                self.log(f'  Claimed {claimed} playtime reward(s)')

            if self.should_stop():
                return False

            # Step 3: Close the panel
            self.clicker.natural_delay(0.5)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_CLOSE_OFFER, threshold=0.8
            )
            if found:
                self.template_matcher.find_and_click(
                    TEMPLATE_CLOSE_OFFER, wait_after=1.5
                )
                self.log('  Closed rewards panel')
            else:
                self.log('  Close button not found')

            return True

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
