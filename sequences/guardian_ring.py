"""
Guardian Ring Sequence — Click the Guardian Ring, then upgrade all available levels.

Flow:
  1. Find and click guardianRing on home screen
  2. Click all UpgradeLvl buttons (max 5)
  3. Click Back to return home
"""

from natural_click import NaturalClick

from config import (
    CLICK_DELAY,
    TEMPLATE_GUARDIAN_RING,
    TEMPLATE_UPGRADE_LVL,
    TEMPLATE_BACK,
)


class GuardianRingSequence:
    """Click Guardian Ring and upgrade all available levels."""

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
        Run the guardian ring sequence.

        Returns:
            True if completed successfully, False on error/abort.
        """
        self.log('')
        self.log('=' * 60)
        self.log(f'  GUARDIAN RING')
        self.log('=' * 60)

        try:
            self.window_capture.get_window()

            # Step 1: Find and click Guardian Ring
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_GUARDIAN_RING, threshold=0.86
            )
            if not found:
                self.log('  Guardian Ring not found — skipping')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_GUARDIAN_RING, wait_after=CLICK_DELAY
            )
            self.log('  Clicked Guardian Ring')
            self.clicker.natural_delay(1.5)

            if self.should_stop():
                return False

            # Step 2: Click all Upgrade buttons (max 5)
            upgrades = 0
            for _ in range(5):
                if self.should_stop():
                    break

                self.clicker.natural_delay(0.5)
                success, _ = self.template_matcher.find_and_click(
                    TEMPLATE_UPGRADE_LVL, threshold=0.8, wait_after=CLICK_DELAY
                )
                if not success:
                    break

                upgrades += 1
                self.log(f'  Upgrade #{upgrades}')
                self.clicker.natural_delay(1.0)

            if upgrades:
                self.log(f'  Upgraded {upgrades} level(s)')
            else:
                self.log(f'  No upgrades available')

            # Step 3: Navigate home
            self.log('  Navigating home...')
            self.template_matcher.find_and_click(
                TEMPLATE_BACK, threshold=0.8, wait_after=1.5
            )

            self.log('')
            self.log('=' * 60)
            self.log(f'  GUARDIAN RING — COMPLETE')
            self.log('=' * 60)
            return True

        except Exception as e:
            import traceback
            self.log('')
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
