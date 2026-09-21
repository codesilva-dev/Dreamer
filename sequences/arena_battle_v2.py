"""
Arena Battle Runner V2 — Vision-based target finding and attack.

For each target: scroll through the list scanning until the target power
appears on screen, then click the battle button at the LIVE Y position.
No stored scroll positions — purely reactive to what's visible.
"""

import time
import pyautogui
from natural_click import NaturalClick

from config import (
    ARENA_SCAN_DELAY,
    ARENA_MAX_SCROLL_ATTEMPTS,
    ARENA_MAX_BATTLES,
    ARENA_BATTLE_BUTTON_X,
    TEMPLATE_START_FIGHT,
    TEMPLATE_BATTLE_COMPLETE,
    TEMPLATE_RETURN_ARENA,
    TEMPLATE_EMPTY_ATOKENS,
    TEMPLATE_FREE_ATOKENS,
)


# Battle button is vertically centered in the opponent row.
# OCR returns Y of the "Team Power:" text which is near the bottom of the row.
# Offset upward to reach the button center.
BUTTON_Y_OFFSET = -50


class ArenaBattleRunner:
    """
    Attacks arena opponents using visual search.

    Instead of navigating to a stored scroll position, each attack starts
    from the top of the list and scrolls down scanning until the target
    power value is found on screen.
    """

    def __init__(self, window_capture, text_recognizer, template_matcher,
                 scanner, log_func=None, stop_check=None):
        """
        Args:
            scanner: ArenaListScanner instance (shared with orchestrator)
        """
        self.window_capture = window_capture
        self.text_recognizer = text_recognizer
        self.template_matcher = template_matcher
        self.scanner = scanner
        self.log = log_func or print
        self.stop_check = stop_check
        self.clicker = NaturalClick()

    def should_stop(self):
        return self.stop_check and self.stop_check()

    # ── Visual search ──────────────────────────────────────────────────

    def find_target_on_screen(self, target_power, retries=1):
        """
        Scan the visible area for a specific power value.

        Returns:
            (y_position, visible_powers) — y_position is int if found, None
            otherwise. visible_powers is a frozenset of all power values seen.
        """
        all_seen = set()
        for attempt in range(1 + retries):
            self.clicker.natural_delay(ARENA_SCAN_DELAY)
            frame = self.window_capture.capture()
            roi_x, roi_y, roi_w, roi_h = self.scanner.get_fluid_ocr_region(frame)
            roi_frame = frame[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]

            powers = self.text_recognizer.find_team_powers_hsv(roi_frame)
            all_seen.update(p['power'] for p in powers)

            for p in powers:
                if p['power'] == target_power:
                    y_pos = (p['y_position'] or 0) + roi_y
                    return y_pos, frozenset(all_seen)

            if attempt < retries:
                self.clicker.natural_delay(0.3)

        return None, frozenset(all_seen)

    def scroll_and_find(self, target_power):
        """
        Search for a target by scanning from current position.

        First checks what's visible now, then scrolls down scanning.
        If the bottom is reached without finding the target, wraps around
        by scrolling to top and scanning downward again.

        Uses fluid scrolls (broad, ~45% window height) for reliable movement.

        Returns:
            y_position (int) if found, None if not found after full traversal.
        """
        # Start from the top
        self.scanner.scroll_to_top_fast()

        # Check visible area at top
        y_pos, _ = self.find_target_on_screen(target_power)
        if y_pos is not None:
            return y_pos

        # Scroll down scanning at each position
        for i in range(ARENA_MAX_SCROLL_ATTEMPTS):
            if self.should_stop():
                return None

            self.scanner._fluid_scroll_down()
            y_pos, _ = self.find_target_on_screen(target_power)
            if y_pos is not None:
                return y_pos

        return None

    # ── Click actions ──────────────────────────────────────────────────

    def click_battle_at_position(self, y_position):
        """
        Click the battle button for an opponent at the given Y position.

        Uses the LIVE y_position from the scan that just found the target.
        Verifies the button is orange (available) before clicking.

        Returns:
            True if clicked, False if button is gray (defeated).
        """
        frame = self.window_capture.capture()

        # Verify opponent is still available
        if not self.scanner.check_battle_available(frame, y_position):
            self.log(f"    Opponent already defeated (gray button)")
            return False

        left, top, win_w, win_h = self.scanner.get_window_dimensions()
        frame_width = frame.shape[1]

        button_x = left + int(frame_width * ARENA_BATTLE_BUTTON_X)
        button_y = top + y_position + BUTTON_Y_OFFSET

        self.log(f"    Clicking Battle at ({button_x}, {button_y})")

        pyautogui.moveTo(button_x, button_y, duration=0.3)
        self.clicker.natural_delay(0.2)
        self.clicker.click()

        return True

    # ── Battle flow steps ──────────────────────────────────────────────

    def ensure_arena_tokens(self):
        """
        Check if we have arena tokens. If empty, try to get free tokens.

        Returns:
            'ok' — have tokens
            'refilled' — got free tokens
            'no_tokens' — out of tokens, can't refill
        """
        found, location, size = self.template_matcher.find_template(
            TEMPLATE_EMPTY_ATOKENS, threshold=0.98
        )

        if not found:
            return 'ok'

        self.log(f"    ! Empty tokens — attempting refill...")

        # Click the + button (left of the empty tokens image)
        plus_offset_x = -(size[0] // 2) - 20
        self.template_matcher.click_at_offset(
            location[0], location[1],
            offset_x=plus_offset_x,
            wait_after=1.5,
        )

        self.clicker.natural_delay(0.5)
        found_free, _, _ = self.template_matcher.find_template(
            TEMPLATE_FREE_ATOKENS, threshold=0.8
        )

        if found_free:
            self.template_matcher.find_and_click(
                TEMPLATE_FREE_ATOKENS, threshold=0.8, wait_after=2.0
            )
            self.log(f"    Tokens refilled (free)")
            return 'refilled'
        else:
            self.log(f"    No free tokens — out of tokens")
            pyautogui.press('escape')
            self.clicker.natural_delay(0.5)
            return 'no_tokens'

    def click_start_fight(self):
        """Click the Start Fight button. Returns True if clicked."""
        success, _ = self.template_matcher.find_and_click(
            TEMPLATE_START_FIGHT, threshold=0.8, wait_after=1.0
        )
        if not success:
            self.log(f"    Start Fight button not found")
        return success

    def wait_for_battle_complete(self, timeout=120, check_interval=3.0):
        """Poll for Battle Complete screen. Returns True if found."""
        start = time.time()
        while time.time() - start < timeout:
            if self.should_stop():
                return False

            success, _ = self.template_matcher.find_and_click(
                TEMPLATE_BATTLE_COMPLETE, threshold=0.8, wait_after=1.0
            )
            if success:
                return True

            self.clicker.natural_delay(check_interval)

        self.log(f"    Timeout waiting for Battle Complete ({timeout}s)")
        return False

    def click_return_arena(self, max_attempts=5, check_interval=1.0):
        """Click Return Arena button. Retries up to max_attempts."""
        for attempt in range(max_attempts):
            success, _ = self.template_matcher.find_and_click(
                TEMPLATE_RETURN_ARENA, threshold=0.8, wait_after=1.5
            )
            if success:
                return True

            if attempt < max_attempts - 1:
                self.clicker.natural_delay(check_interval)

        self.log(f"    Return Arena button not found")
        return False

    # ── Full single-target battle flow ─────────────────────────────────

    def run_battle_flow(self, target_power):
        """
        Execute the full battle flow for one opponent.

        Returns:
            'success', 'no_tokens', 'not_found', 'defeated',
            'fight_failed', 'timeout', 'return_failed', 'list_changed'
        """
        # 1. Check if list has refreshed (tier bracket change)
        if not self.scanner.is_list_unchanged():
            return 'list_changed'

        # 2. Check tokens
        token_status = self.ensure_arena_tokens()
        if token_status == 'no_tokens':
            return 'no_tokens'

        # 3. Find target by visual search
        self.log(f"    Searching for Power {target_power:,}...")
        y_pos = self.scroll_and_find(target_power)
        if y_pos is None:
            self.log(f"    Target {target_power:,} not found in list")
            return 'not_found'

        self.log(f"    Found at y={y_pos}")

        # 3. Click battle button
        if not self.click_battle_at_position(y_pos):
            return 'defeated'

        # 4. Wait for team selection screen
        self.clicker.natural_delay(1.0)

        # 5. Click Start Fight
        if not self.click_start_fight():
            return 'fight_failed'

        # 6. Wait for battle to complete
        if not self.wait_for_battle_complete():
            return 'timeout'

        # 7. Return to arena
        self.clicker.natural_delay(1.0)
        if not self.click_return_arena():
            return 'return_failed'

        # 8. Wait for arena list to load (game resets to top)
        self.clicker.natural_delay(2.0)

        return 'success'

    # ── Attack all targets ─────────────────────────────────────────────

    def attack_targets(self, targets, single_attack=False):
        """
        Attack targets in order, using visual search for each.

        Args:
            targets: Sorted list of opponent dicts [{power, available}]
            single_attack: If True, only attack the first target.

        Returns:
            Dict with {completed, skipped, not_found, exit_reason}
        """
        results = {
            'completed': 0,
            'skipped': 0,
            'not_found': 0,
            'exit_reason': None,
        }

        consecutive_not_found = 0

        for i, target in enumerate(targets):
            if self.should_stop():
                results['exit_reason'] = 'stopped'
                break

            if results['completed'] >= ARENA_MAX_BATTLES:
                results['exit_reason'] = 'max_reached'
                break

            self.log(f"  [{i + 1}/{len(targets)}] Targeting Power {target['power']:,}")

            result = self.run_battle_flow(target['power'])

            if result == 'success':
                results['completed'] += 1
                consecutive_not_found = 0
                self.log(f"    Battle {results['completed']} complete")
            elif result == 'no_tokens':
                results['exit_reason'] = 'no_tokens'
                break
            elif result == 'list_changed':
                self.log(f"    List refreshed — stopping attack phase for rescan")
                results['exit_reason'] = 'list_changed'
                break
            elif result == 'not_found':
                results['not_found'] += 1
                consecutive_not_found += 1
                if consecutive_not_found >= 3:
                    self.log(f"    3 consecutive not found — list likely refreshed")
                    results['exit_reason'] = 'list_changed'
                    break
            else:
                results['skipped'] += 1
                consecutive_not_found = 0
                self.log(f"    Skipped ({result})")

            if single_attack:
                break

        if results['exit_reason'] is None:
            results['exit_reason'] = 'all_done'

        self.log(f"  Attack phase done: {results['completed']} battles, "
                 f"{results['not_found']} not found, {results['skipped']} skipped")

        return results
