"""
Arena Battle Runner V2 — Vision-based target finding and attack.

For each target: scroll through the list scanning until the target power
appears on screen, then click the battle button at the LIVE Y position.
No stored scroll positions — purely reactive to what's visible.
"""

import time
import os
import cv2
import pyautogui
from natural_click import NaturalClick

from config import (
    SCRIPT_DIR,
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
            roi_frame = frame[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w].copy()

            powers = self.text_recognizer.find_team_powers_hsv(roi_frame)

            # Filter out invalid entries (should be dicts, not ints)
            valid_powers = [p for p in powers if isinstance(p, dict) and 'power' in p]
            all_seen.update(p['power'] for p in valid_powers)

            for p in valid_powers:
                if p['power'] == target_power:
                    y_pos = (p['y_position'] or 0) + roi_y
                    return y_pos, frozenset(all_seen)

            if attempt < retries:
                self.clicker.natural_delay(0.3)

        return None, frozenset(all_seen)

    def find_target_by_template(self, target_power):
        """
        Find target using template matching on saved power snapshot.

        This is much more reliable than OCR - uses the exact power region
        image saved during the initial scan.

        Args:
            target_power: int power value to find

        Returns:
            y_position (int) if found via template matching, None otherwise
        """
        # Load the template snapshot
        snapshot_dir = os.path.join(SCRIPT_DIR, 'debug', 'arena_targets')
        template_path = os.path.join(snapshot_dir, f'power_{target_power}.png')

        if not os.path.exists(template_path):
            # No snapshot saved for this target (might have been defeated already)
            self.log(f"    [TEMPLATE] No snapshot found at {template_path}")
            return None

        template = cv2.imread(template_path)
        if template is None:
            self.log(f"    [TEMPLATE] Failed to load image from {template_path}")
            return None

        template_h, template_w = template.shape[:2]

        # Capture current frame
        frame = self.window_capture.capture()
        if frame is None:
            return None

        # Get the power OCR region for vertical bounds
        roi_x, roi_y, roi_w, roi_h = self.scanner.get_fluid_ocr_region(frame)
        frame_h, frame_w = frame.shape[:2]

        # Search from 55% to 90% of screen width (where templates were captured)
        # This matches the horizontal region where power values + battle buttons appear
        search_x_start = int(frame_w * 0.55)
        search_x_end = int(frame_w * 0.90)
        search_region = frame[roi_y:roi_y + roi_h, search_x_start:search_x_end]

        # Template match
        result = cv2.matchTemplate(search_region, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Lower threshold to handle slight variations and OCR misreads
        # If we're seeing 0.77 scores, opponent is there but template has minor differences
        if max_val >= 0.75:
            # max_loc[1] is the top of the match in search_region
            # Template was cropped with power text at y_position, and template top at y_position - 90
            # So to get back to y_position (power text location), we add 90 to the match top
            match_top_in_roi = max_loc[1]  # Top of match in search_region (starts at roi_y)
            y_pos = roi_y + match_top_in_roi + 90  # Add 90 to get to power text position

            self.log(f"    [TEMPLATE] Found at y={y_pos} (score={max_val:.3f})")

            # Create detailed debug visualization
            import numpy as np
            debug_dir = os.path.join(SCRIPT_DIR, 'debug')
            os.makedirs(debug_dir, exist_ok=True)

            # Template with label
            template_display = template.copy()
            cv2.putText(template_display, f"Template {target_power}", (5, 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # Search region with match highlighted
            search_display = search_region.copy()
            cv2.putText(search_display, f"Search Region (score={max_val:.3f})", (5, 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.rectangle(search_display,
                         (max_loc[0], max_loc[1]),
                         (max_loc[0] + template_w, max_loc[1] + template_h),
                         (0, 255, 0), 2)

            # Full frame with search region and match highlighted
            debug_frame = frame.copy()
            # Draw search region boundary (blue)
            cv2.rectangle(debug_frame, (search_x_start, roi_y), (search_x_end, roi_y + roi_h), (255, 0, 0), 2)
            # Draw match location (green)
            match_x_frame = search_x_start + max_loc[0]
            match_y_frame = roi_y + max_loc[1]
            cv2.rectangle(debug_frame,
                         (match_x_frame, match_y_frame),
                         (match_x_frame + template_w, match_y_frame + template_h),
                         (0, 255, 0), 3)

            # Combine into single debug image: template | search_region | full_frame (scaled)
            h_max = max(template_display.shape[0], search_display.shape[0])
            template_padded = np.zeros((h_max, template_display.shape[1], 3), dtype=np.uint8)
            template_padded[:template_display.shape[0], :] = template_display
            search_padded = np.zeros((h_max, search_display.shape[1], 3), dtype=np.uint8)
            search_padded[:search_display.shape[0], :] = search_display

            top_row = np.hstack([template_padded, search_padded])
            scale = top_row.shape[1] / debug_frame.shape[1] if debug_frame.shape[1] > top_row.shape[1] else 1.0
            scaled_frame = cv2.resize(debug_frame, None, fx=scale, fy=scale)
            combined = np.vstack([top_row, scaled_frame])

            cv2.imwrite(os.path.join(debug_dir, f'arena_match_{target_power}.png'), combined)

            return y_pos

        self.log(f"    [TEMPLATE] Match score too low: {max_val:.3f} < 0.75")

        # Save debug showing why it didn't match
        import numpy as np
        debug_dir = os.path.join(SCRIPT_DIR, 'debug')
        os.makedirs(debug_dir, exist_ok=True)

        template_display = template.copy()
        cv2.putText(template_display, f"Template {target_power}", (5, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        search_display = search_region.copy()
        cv2.putText(search_display, f"NO MATCH (score={max_val:.3f})", (5, 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        # Show best match location even though score is low (red)
        cv2.rectangle(search_display,
                     (max_loc[0], max_loc[1]),
                     (max_loc[0] + template_w, max_loc[1] + template_h),
                     (0, 0, 255), 2)

        h_max = max(template_display.shape[0], search_display.shape[0])
        template_padded = np.zeros((h_max, template_display.shape[1], 3), dtype=np.uint8)
        template_padded[:template_display.shape[0], :] = template_display
        search_padded = np.zeros((h_max, search_display.shape[1], 3), dtype=np.uint8)
        search_padded[:search_display.shape[0], :] = search_display

        combined = np.hstack([template_padded, search_padded])
        cv2.imwrite(os.path.join(debug_dir, f'arena_nomatch_{target_power}.png'), combined)

        return None

    def scroll_and_find(self, target_power):
        """
        Search for a target by scrolling and using ONLY template matching.

        NO OCR during battle phase - templates were saved during scan.
        If template isn't found, opponent doesn't exist or was already defeated.

        Returns:
            y_position (int) if found, None if not found after full traversal.
        """
        # Start from the top
        self.scanner.scroll_to_top_fast()

        # Check visible area at top (search region includes all 4 visible opponents)
        # Template matching searches the entire region in one pass
        y_pos = self.find_target_by_template(target_power)
        if y_pos is not None:
            self.log(f"    Found via template at top: y={y_pos}")
            return y_pos

        # Scroll down scanning at each position
        for i in range(ARENA_MAX_SCROLL_ATTEMPTS):
            if self.should_stop():
                return None

            self.scanner._fluid_scroll_down()
            self.clicker.natural_delay(1.0)  # Wait for scroll to settle

            y_pos = self.find_target_by_template(target_power)
            if y_pos is not None:
                self.log(f"    Found via template after scroll {i+1}: y={y_pos}")
                return y_pos

        return None

    # ── Click actions ──────────────────────────────────────────────────

    def click_battle_at_position(self, y_position):
        """
        Click the battle button for an opponent at the given Y position.

        Uses the LIVE y_position from the scan that just found the target.
        Verifies the button is orange (available) before clicking.

        Args:
            y_position: Y coordinate in FRAME coordinates (not screen coordinates)

        Returns:
            True if clicked, False if button is gray (defeated).
        """
        frame = self.window_capture.capture()

        # Verify opponent is still available
        if not self.scanner.check_battle_available(frame, y_position):
            self.log(f"    Opponent already defeated (gray button)")
            return False

        left, top, win_w, win_h = self.scanner.get_window_dimensions()
        frame_height, frame_width = frame.shape[:2]

        # Calculate click position in frame coordinates
        button_x_frame = int(frame_width * ARENA_BATTLE_BUTTON_X)
        button_y_frame = y_position + BUTTON_Y_OFFSET

        # Convert to screen coordinates
        button_x_screen = left + button_x_frame
        button_y_screen = top + button_y_frame

        self.log(f"    Clicking Battle at screen ({button_x_screen}, {button_y_screen}) "
                 f"[frame: ({button_x_frame}, {button_y_frame}), y_pos={y_position}]")

        # Save debug image showing click position
        debug_frame = frame.copy()
        cv2.circle(debug_frame, (button_x_frame, button_y_frame), 15, (0, 0, 255), 3)  # Red circle at click
        cv2.circle(debug_frame, (button_x_frame, y_position), 8, (0, 255, 0), 2)  # Green circle at power position
        debug_dir = os.path.join(SCRIPT_DIR, 'debug')
        os.makedirs(debug_dir, exist_ok=True)
        debug_path = os.path.join(debug_dir, 'arena_battle_click.png')
        cv2.imwrite(debug_path, debug_frame)

        pyautogui.moveTo(button_x_screen, button_y_screen, duration=0.3)
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

    def wait_for_battle_complete(self, timeout=600, check_interval=3.0):
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

            level_str = f"L{target['level']}" if target.get('level') else ""
            level_info = f" {level_str}" if level_str else ""
            self.log(f"  ⚔️  Battle {i + 1}/{len(targets)}: {target['power']:,} power{level_info}")

            result = self.run_battle_flow(target['power'])

            if result == 'success':
                results['completed'] += 1
                consecutive_not_found = 0
                self.log(f"      ✓ Victory!")
            elif result == 'no_tokens':
                results['exit_reason'] = 'no_tokens'
                self.log(f"      ⚠️  Out of arena tokens")
                break
            elif result == 'list_changed':
                self.log(f"      ⚠️  List refreshed, stopping to rescan")
                results['exit_reason'] = 'list_changed'
                break
            elif result == 'not_found':
                results['not_found'] += 1
                consecutive_not_found += 1
                self.log(f"      ✗ Opponent not found in list")
                if consecutive_not_found >= 3:
                    self.log(f"      ⚠️  List likely refreshed after 3 misses")
                    results['exit_reason'] = 'list_changed'
                    break
            else:
                results['skipped'] += 1
                consecutive_not_found = 0
                self.log(f"      ⊘ Skipped ({result})")

            if single_attack:
                break

        if results['exit_reason'] is None:
            results['exit_reason'] = 'all_done'

        self.log(f"")
        self.log(f"  📊 Results: {results['completed']} victories, "
                 f"{results['not_found']} not found, {results['skipped']} skipped")

        return results
