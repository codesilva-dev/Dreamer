"""
Collect Gem — Find and click the collectGem icon on the home screen.

Simple single-click task: detect the gem, click it, done.
"""

from natural_click import NaturalClick

from config import TEMPLATE_COLLECT_GEM


class CollectGemSequence:
    """Find the collectGem icon and click it."""

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

        Returns:
            True if completed successfully, False on error/abort.
        """
        self.log('')
        self.log('  --- Collect Gem ---')

        try:
            self.window_capture.get_window()

            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_COLLECT_GEM, threshold=0.8
            )
            if not found:
                self.log('  Collect Gem not found — skipping')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_COLLECT_GEM, wait_after=1.5
            )
            self.log('  Clicked Collect Gem')

            return True

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
