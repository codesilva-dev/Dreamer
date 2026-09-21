"""
Quests — Open the quests panel, claim rewards, and run any actionable quests.

Loop: questIcon → claimQuests → scan for known quests → back → run sub-sequence → repeat.
Stops when no actionable quests are found.
"""

from natural_click import NaturalClick

from config import (
    TEMPLATE_QUEST_ICON, TEMPLATE_CLAIM_QUESTS, TEMPLATE_BACK,
    TEMPLATE_SUM3_CHAMPS,
)
from sequences.sum3 import Sum3Sequence


class QuestsSequence:
    """Open quests panel, claim rewards, and complete actionable quests."""

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
        Run the quests sequence in a loop.

        Each iteration: open quests → claim → scan for actionable quests →
        back out → run sub-sequence → repeat.

        Returns:
            True if completed successfully, False on error/abort.
        """
        self.log('')
        self.log('  --- Quests ---')

        try:
            iteration = 0
            while True:
                if self.should_stop():
                    return False

                iteration += 1
                if iteration > 1:
                    self.log('')
                    self.log(f'  --- Quests (pass #{iteration}) ---')

                self.window_capture.get_window()

                # Step 1: Open quests
                found, _, _ = self.template_matcher.find_template(
                    TEMPLATE_QUEST_ICON, threshold=0.8
                )
                if not found:
                    self.log('  Quest icon not found — skipping')
                    return True

                self.template_matcher.find_and_click(
                    TEMPLATE_QUEST_ICON, wait_after=1.5
                )
                self.log('  Clicked Quest Icon')

                if self.should_stop():
                    return False

                # Step 2: Claim any completed quests
                self.clicker.natural_delay(1.0)
                found, _, _ = self.template_matcher.find_template(
                    TEMPLATE_CLAIM_QUESTS, threshold=0.8
                )
                if found:
                    self.template_matcher.find_and_click(
                        TEMPLATE_CLAIM_QUESTS, wait_after=1.5
                    )
                    self.log('  Clicked Claim Quests')
                else:
                    self.log('  Claim Quests not found')

                if self.should_stop():
                    return False

                # Step 3: Scan for actionable quests
                self.clicker.natural_delay(1.0)
                action_taken = False

                # Check for "Summon 3 Champions"
                found, _, _ = self.template_matcher.find_template(
                    TEMPLATE_SUM3_CHAMPS, threshold=0.8
                )
                if found:
                    self.log('  Found: Summon 3 Champions')

                    # Back out of quests panel
                    self.clicker.natural_delay(0.5)
                    self.template_matcher.find_and_click(
                        TEMPLATE_BACK, threshold=0.8, wait_after=1.5
                    )
                    self.log('  Backed out to run Sum3')

                    # Run the sum3 sub-sequence
                    seq = Sum3Sequence(
                        self.window_capture, self.template_matcher,
                        self.log, stop_check=self.stop_check
                    )
                    seq.run()
                    action_taken = True

                # No actionable quests found — done
                if not action_taken:
                    self.log('  No actionable quests found')

                    # Back out of quests panel
                    self.clicker.natural_delay(0.5)
                    found, _, _ = self.template_matcher.find_template(
                        TEMPLATE_BACK, threshold=0.8
                    )
                    if found:
                        self.template_matcher.find_and_click(
                            TEMPLATE_BACK, wait_after=1.5
                        )
                        self.log('  Backed out of quests')
                    return True

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
