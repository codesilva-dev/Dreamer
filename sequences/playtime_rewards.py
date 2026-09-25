"""
Playtime Rewards — Collect all available playtime rewards.

Flow:
  1. Click AccruedRewards icon on home screen
  2. Click claimAllRewards button
  3. Click closeoffer (X) to close the rewards panel
"""

from natural_click import NaturalClick

from config import (
    TEMPLATE_ACCRUED_REWARDS,
    TEMPLATE_CLAIM_ALL_REWARDS,
    TEMPLATE_CLOSE_OFFER,
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

            # Step 2: Click Claim All Rewards
            self.clicker.natural_delay(1.0)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_CLAIM_ALL_REWARDS, threshold=0.8
            )
            if found:
                self.template_matcher.find_and_click(
                    TEMPLATE_CLAIM_ALL_REWARDS, wait_after=2.0
                )
                self.log('  Clicked Claim All Rewards')
            else:
                self.log('  Claim All Rewards not found — no rewards available')

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
