"""
Clan Boss (CB Main) — Navigate to Clan Boss and select a difficulty.

Navigation: Home -> Battle -> CBStages -> CB1 -> select difficulty.

Phase 1: Configuration and navigation only.
    - Navigates to the CB1 screen.
    - Finds the selected difficulty template on screen and clicks it.
    - Future: fighting logic, key tracking, cascading to easier difficulties.
"""

from natural_click import NaturalClick

from config import (
    TEMPLATE_BATTLE, TEMPLATE_CB_STAGES, TEMPLATE_CB1, TEMPLATE_BACK,
    TEMPLATE_CB_EASY, TEMPLATE_CB_NORMAL, TEMPLATE_CB_HARD,
    TEMPLATE_CB_BRUTAL, TEMPLATE_CB_NIGHTMARE, TEMPLATE_CB_ULTRA_NIGHTMARE,
    CLICK_DELAY,
)
import config


class ClanBossSequence:
    """Navigate to Clan Boss and click the selected difficulty."""

    # Map difficulty names to template paths
    DIFFICULTY_TEMPLATES = {
        'easy': TEMPLATE_CB_EASY,
        'normal': TEMPLATE_CB_NORMAL,
        'hard': TEMPLATE_CB_HARD,
        'brutal': TEMPLATE_CB_BRUTAL,
        'nightmare': TEMPLATE_CB_NIGHTMARE,
        'ultranightmare': TEMPLATE_CB_ULTRA_NIGHTMARE,
    }

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
        Run the Clan Boss navigation sequence.

        Returns:
            dict with 'success' key on success, False on error/abort.
        """
        difficulty = config.CB_DIFFICULTY
        self.log('')
        self.log(f'  --- Clan Boss: {difficulty} ---')

        try:
            self.window_capture.get_window()

            # Step 1: Click Battle
            self.log('  Looking for Battle button...')
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_BATTLE, threshold=0.8
            )
            if not found:
                self.log('  Battle button not found -- aborting')
                return False

            self.template_matcher.find_and_click(
                TEMPLATE_BATTLE, threshold=0.8, wait_after=CLICK_DELAY
            )
            self.log('  Clicked Battle')

            if self.should_stop():
                return False

            # Step 2: Click CBStages
            self.clicker.natural_delay(1.0)
            self.log('  Looking for CB Stages...')
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_CB_STAGES, threshold=0.8
            )
            if not found:
                self.log('  CB Stages not found -- aborting')
                return False

            self.template_matcher.find_and_click(
                TEMPLATE_CB_STAGES, threshold=0.8, wait_after=CLICK_DELAY
            )
            self.log('  Clicked CB Stages')

            if self.should_stop():
                return False

            # Step 3: Click CB1
            self.clicker.natural_delay(1.0)
            self.log('  Looking for CB1...')
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_CB1, threshold=0.8
            )
            if not found:
                self.log('  CB1 not found -- aborting')
                return False

            self.template_matcher.find_and_click(
                TEMPLATE_CB1, threshold=0.8, wait_after=CLICK_DELAY
            )
            self.log('  Clicked CB1')

            if self.should_stop():
                return False

            # Step 4: Find and click the selected difficulty
            self.clicker.natural_delay(1.5)
            template = self.DIFFICULTY_TEMPLATES.get(difficulty)
            if not template:
                self.log(f'  Unknown difficulty: {difficulty}')
                return False

            self.log(f'  Looking for {difficulty} difficulty...')
            found, _, _ = self.template_matcher.find_template(
                template, threshold=0.8
            )
            if not found:
                self.log(f'  {difficulty} difficulty not found on screen')
                return False

            self.template_matcher.find_and_click(
                template, threshold=0.8, wait_after=CLICK_DELAY
            )
            self.log(f'  Clicked {difficulty} difficulty')

            return {'success': True}

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
