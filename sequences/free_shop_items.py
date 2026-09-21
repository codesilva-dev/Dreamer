"""
Free Shop Items Sequence — Collect all free items from the shop.

Flow:
  1. Click FreeShopButton to enter shop
  2. Packs tab (default): click all ClaimPack buttons
  3. Click Limited Special Offers sidebar tab
  4. Click Small Pack top tab
  5. Click all ClaimGift buttons
  6. Click Back to go home

In DRY RUN mode, moves mouse to claim buttons without clicking.
"""

import pyautogui
from natural_click import NaturalClick

from config import (
    CLICK_DELAY,
    TEMPLATE_FREE_SHOP_BUTTON,
    TEMPLATE_CLAIM_GIFT,
    TEMPLATE_CLAIM_PACK,
    TEMPLATE_LIMITED_OFFERS,
    TEMPLATE_SMALL_PACK,
    TEMPLATE_BACK,
)


class FreeShopItemsSequence:
    """
    Navigates Home -> Shop, collects all free items, navigates home.

    Set dry_run=False to actually click and collect.
    """

    def __init__(self, window_capture, template_matcher, log_func=None,
                 stop_check=None, dry_run=True):
        self.window_capture = window_capture
        self.template_matcher = template_matcher
        self.log = log_func or print
        self.stop_check = stop_check
        self.dry_run = dry_run
        self.clicker = NaturalClick()

    def should_stop(self):
        return self.stop_check and self.stop_check()

    def _click_or_move(self, location, label):
        """Click at location (live) or just move mouse there (dry run)."""
        left, top, _, _ = self.window_capture.window_info
        abs_x = left + location[0]
        abs_y = top + location[1]

        if self.dry_run:
            self.log(f'    [DRY RUN] {label} at ({abs_x}, {abs_y}) — move only')
            pyautogui.moveTo(abs_x, abs_y, duration=0.5)
            self.clicker.natural_delay(1.0)
        else:
            self.log(f'    {label} at ({abs_x}, {abs_y})')
            pyautogui.moveTo(abs_x, abs_y, duration=0.3)
            self.clicker.natural_delay(0.2)
            self.clicker.click()
            self.clicker.natural_delay(2.0)

    def _collect_all_claims(self, claim_template):
        """Find and click/move-to all claim buttons on the current view."""
        claims = 0
        for _ in range(10):
            if self.should_stop():
                break
            self.clicker.natural_delay(0.5)
            found, location, _ = self.template_matcher.find_template(
                claim_template, threshold=0.8
            )
            if not found:
                break
            claims += 1
            self._click_or_move(location, f'Claim #{claims}')
            if self.dry_run:
                break
        return claims

    def run(self):
        """
        Run the free shop items sequence.

        Returns:
            True if completed successfully, False on error/abort.
        """
        mode = "DRY RUN (move only)" if self.dry_run else "LIVE (collecting)"

        self.log('')
        self.log('=' * 60)
        self.log(f'  FREE SHOP ITEMS — {mode}')
        self.log('=' * 60)

        try:
            self.window_capture.get_window()

            # Step 1: Enter shop via Free indicator
            found, _, _ = self.template_matcher.find_template(
                TEMPLATE_FREE_SHOP_BUTTON, threshold=0.8
            )
            if not found:
                self.log('  No free shop indicator — nothing to collect')
                return True

            self.template_matcher.find_and_click(
                TEMPLATE_FREE_SHOP_BUTTON, wait_after=CLICK_DELAY
            )
            self.log(f'  Entered shop')
            self.clicker.natural_delay(1.5)

            if self.should_stop():
                return False

            total = 0

            # Step 2: Packs tab (default landing page)
            self.log('  Scanning Packs tab...')
            claims = self._collect_all_claims(TEMPLATE_CLAIM_PACK)
            total += claims
            if claims:
                self.log(f'  Packs: {claims} claim(s)')

            if self.should_stop():
                return False

            # Step 3-4: Limited Special Offers -> Small Pack
            self.clicker.natural_delay(0.5)
            lo_found, _, _ = self.template_matcher.find_template(
                TEMPLATE_LIMITED_OFFERS, threshold=0.8
            )
            if lo_found:
                self.log('  Navigating to Limited Special Offers...')
                self.template_matcher.find_and_click(
                    TEMPLATE_LIMITED_OFFERS, wait_after=CLICK_DELAY
                )
                self.clicker.natural_delay(1.5)

                sp_found, _, _ = self.template_matcher.find_template(
                    TEMPLATE_SMALL_PACK, threshold=0.8
                )
                if sp_found:
                    self.log('  Clicking Small Pack tab...')
                    self.template_matcher.find_and_click(
                        TEMPLATE_SMALL_PACK, wait_after=CLICK_DELAY
                    )
                    self.clicker.natural_delay(1.0)

                # Step 5: Collect claims
                self.log('  Scanning for claims...')
                claims = self._collect_all_claims(TEMPLATE_CLAIM_GIFT)
                total += claims
                if claims:
                    self.log(f'  Limited Offers: {claims} claim(s)')

            # Step 6: Navigate home
            self.log('  Navigating home...')
            self.template_matcher.find_and_click(
                TEMPLATE_BACK, threshold=0.8, wait_after=1.5
            )

            self.log(f'  Free Shop done — {total} claim(s)')

            self.log('')
            self.log('=' * 60)
            self.log(f'  FREE SHOP ITEMS — COMPLETE')
            self.log('=' * 60)
            return True

        except Exception as e:
            import traceback
            self.log('')
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
