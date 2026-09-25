"""
Collect Gem — Find and click the collectGem icon on the home screen.

Simple single-click task: detect the gem, click it, done.
"""

from natural_click import NaturalClick

from config import TEMPLATE_COLLECT_GEM, TEMPLATE_GEM_CLAIM


class CollectGemSequence:
    """Find the collectGem or gemClaim icon and click it."""

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
        Run the collect gem sequence.

        Checks for both collectGem (full gems) and gemClaim (partial gems).

        Returns:
            True if completed successfully, False on error/abort.
        """
        self.log('')
        self.log('  --- Collect Gem ---')

        try:
            self.window_capture.get_window()

            # Try collectGem first, then gemClaim
            for template, label in [
                (TEMPLATE_COLLECT_GEM, 'Collect Gem'),
                (TEMPLATE_GEM_CLAIM, 'Gem Claim'),
            ]:
                found, _, _ = self.template_matcher.find_template(
                    template, threshold=0.8
                )
                if found:
                    self.template_matcher.find_and_click(
                        template, wait_after=1.5
                    )
                    self.log(f'  Clicked {label}')
                    return True

            self.log('  Collect Gem not found — skipping')
            return True

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
