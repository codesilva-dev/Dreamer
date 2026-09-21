"""
Check Market — Find and click the freshMarket icon, then buy all available shards.

Flow: freshMarket (with red dot) → BuyShard → getShard → repeat until no more BuyShard.
"""

from natural_click import NaturalClick

from config import (
    TEMPLATE_FRESH_MARKET, TEMPLATE_BUY_SHARD, TEMPLATE_GET_SHARD,
    TEMPLATE_BACK,
)


class CheckMarketSequence:
    """Find the freshMarket icon, enter market, and buy all shards."""

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
        Run the check market sequence.

        Returns:
            True if completed successfully, False on error/abort.
        """
        self.log('')
        self.log('  --- Check Market ---')

        try:
            self.window_capture.get_window()

            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_FRESH_MARKET, threshold=0.96
            )
            if not found:
                self.log('  Fresh Market not found — skipping')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_FRESH_MARKET, wait_after=1.5
            )
            self.log('  Clicked Fresh Market')

            if self.should_stop():
                return False

            # Buy all available shards
            shards = 0
            for _ in range(20):
                if self.should_stop():
                    break

                self.clicker.natural_delay(1.0)
                found, _, _ = self.template_matcher.find_template(
                    TEMPLATE_BUY_SHARD, threshold=0.8
                )
                if not found:
                    break

                self.template_matcher.find_and_click(
                    TEMPLATE_BUY_SHARD, wait_after=1.5
                )
                self.log(f'  Clicked Buy Shard')

                if self.should_stop():
                    break

                # Confirm with getShard
                self.clicker.natural_delay(1.0)
                found, _, _ = self.template_matcher.find_template(
                    TEMPLATE_GET_SHARD, threshold=0.8
                )
                if found:
                    self.template_matcher.find_and_click(
                        TEMPLATE_GET_SHARD, wait_after=1.5
                    )
                    shards += 1
                    self.log(f'  Shard #{shards} purchased')
                else:
                    self.log('  getShard not found — stopping')
                    break

            if shards:
                self.log(f'  Market: {shards} shard(s) purchased')
            else:
                self.log('  Market: no shards available')

            # Navigate back
            self.clicker.natural_delay(0.5)
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_BACK, threshold=0.8
            )
            if found:
                self.template_matcher.find_and_click(
                    TEMPLATE_BACK, wait_after=1.5
                )
                self.log('  Navigated back from Market')
            else:
                self.log('  Back button not found')

            return True

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
