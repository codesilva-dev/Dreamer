"""
Menu Rewards — Find and click the checkMenu icon on the home screen.

Simple single-click task: detect the menu reward indicator, click it, done.
"""

from natural_click import NaturalClick

from config import (
    TEMPLATE_CHECK_MENU, TEMPLATE_DAILY_LOGIN, TEMPLATE_COLLECT,
    TEMPLATE_PPP, TEMPLATE_PPP_RED_DOT, TEMPLATE_FREE_DRAW, TEMPLATE_BACK,
)


class MenuRewardsSequence:
    """Find the checkMenu icon and click it."""

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
        Run the menu rewards sequence.

        Returns:
            True if completed successfully, False on error/abort.
        """
        self.log('')
        self.log('  --- Menu Rewards ---')

        try:
            self.window_capture.get_window()

            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_CHECK_MENU, threshold=0.8
            )
            if not found:
                self.log('  Menu reward not found — skipping')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_CHECK_MENU, wait_after=1.5
            )
            self.log('  Clicked Menu Rewards')

            if self.should_stop():
                return False

            # Step 2: Look for Daily Login
            self.clicker.natural_delay(1.0)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_DAILY_LOGIN, threshold=0.89
            )
            if found:
                self.template_matcher.find_and_click(
                    TEMPLATE_DAILY_LOGIN, wait_after=1.5
                )
                self.log('  Clicked Daily Login')

                if self.should_stop():
                    return False

                # Step 3: Look for Collect button (only after Daily Login)
                self.clicker.natural_delay(1.0)
                found, _, _ = self.template_matcher.find_template(
                    TEMPLATE_COLLECT, threshold=0.8
                )
                if found:
                    self.template_matcher.find_and_click(
                        TEMPLATE_COLLECT, wait_after=1.5
                    )
                    self.log('  Clicked Collect')
                else:
                    self.log('  Collect not found')
            else:
                self.log('  Daily Login not found')

            if self.should_stop():
                return False

            # Step 4: Look for Plarium Points Program
            self.clicker.natural_delay(1.0)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_PPP, threshold=0.92
            )
            if found:
                self.template_matcher.find_and_click(
                    TEMPLATE_PPP, wait_after=1.5
                )
                self.log('  Clicked Plarium Points Program')

                if self.should_stop():
                    return False

                # Step 5: Look for red dot indicator
                self.clicker.natural_delay(1.0)
                found, _, _ = self.template_matcher.find_template(
                    TEMPLATE_PPP_RED_DOT, threshold=0.8
                )
                if found:
                    self.template_matcher.find_and_click(
                        TEMPLATE_PPP_RED_DOT, wait_after=1.5
                    )
                    self.log('  Clicked Treasure Tickets tab')

                    if self.should_stop():
                        return False

                    # Step 6: Click all Free Draw buttons
                    claims = 0
                    for _ in range(10):
                        if self.should_stop():
                            break
                        self.clicker.natural_delay(1.0)
                        found, _, _ = self.template_matcher.find_template(
                            TEMPLATE_FREE_DRAW, threshold=0.8
                        )
                        if not found:
                            break
                        claims += 1
                        self.template_matcher.find_and_click(
                            TEMPLATE_FREE_DRAW, wait_after=1.5
                        )
                        self.log(f'  Free Draw #{claims}')

                    if claims:
                        self.log(f'  PPP: {claims} free draw(s)')
                    else:
                        self.log('  PPP: no Free Draw buttons found')
                else:
                    self.log('  PPP: no red dot — nothing to collect')

                # Step 7: Click Back to return
                self.clicker.natural_delay(0.5)
                self.template_matcher.find_and_click(
                    TEMPLATE_BACK, threshold=0.8, wait_after=1.5
                )
                self.log('  Navigated back from PPP')
            else:
                self.log('  Plarium Points Program not found')

            return True

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
