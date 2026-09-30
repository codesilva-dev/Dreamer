"""
Classic Arena Sequence V2 — Vision-based orchestrator.

Coordinates: scan list → sort targets → attack all → refresh → repeat.
Uses ArenaListScanner for scanning and ArenaBattleRunner for attacking.

When no free refresh is available, waits 15 minutes for the refresh timer
to reset, then tries again. Only stops when truly out of arena tokens
(0 tokens and no free refill available).
"""

import time

from sequences.arena_scanner_v2 import ArenaListScanner
from sequences.arena_battle_v2 import ArenaBattleRunner
from natural_click import NaturalClick
from utils import reset_home_screen_zoom

import config
from config import (
    ARENA_MAX_BATTLES,
    TEMPLATE_FREE_REFRESH,
    TEMPLATE_BACK,
)

# How long to wait (seconds) when no free refresh is available
REFRESH_WAIT_SECONDS = 15 * 60  # 15 minutes


class ClassicArenaSequenceV2:
    """
    V2 Classic Arena orchestrator.

    Scan → Sort → Attack → Refresh → Repeat.
    Uses vision-based target finding instead of scroll position tracking.
    """

    def __init__(self, window_capture, template_matcher, text_recognizer,
                 log_func=None, stop_check=None, arena_status_callback=None):
        self.window_capture = window_capture
        self.template_matcher = template_matcher
        self.text_recognizer = text_recognizer
        self.log = log_func or print
        self.stop_check = stop_check
        self.arena_status_callback = arena_status_callback
        self.clicker = NaturalClick()
        self.tokens_exhausted = False  # Track if arena tokens are exhausted

        # Shared scanner instance
        self.scanner = ArenaListScanner(
            window_capture, text_recognizer, log_func
        )

        # Battle runner uses the same scanner
        self.battle_runner = ArenaBattleRunner(
            window_capture, text_recognizer, template_matcher,
            self.scanner, log_func, stop_check
        )

    def should_stop(self):
        return self.stop_check and self.stop_check()

    def _display_opponent_table(self, all_opponents, targets):
        """
        Display a clean table of all opponents with targets highlighted in green.
        Shows opponents in SCAN ORDER (top to bottom as they appeared in arena list).

        Args:
            all_opponents: Full list of scanned opponents (sorted by power for battle)
            targets: Filtered list of opponents that will be fought
        """
        # Create set of target powers for quick lookup
        target_powers = {o['power'] for o in targets}

        # Sort by scan_index to show in original scan order (NOT power order)
        display_opponents = sorted(all_opponents, key=lambda x: x.get('scan_index', 0))

        # Build table for UI (plain text, no ANSI codes)
        ui_lines = []
        ui_lines.append("╔═══════════════════════════════════════════════════════╗")
        ui_lines.append("║      ARENA OPPONENTS (in scan order)                  ║")
        ui_lines.append("╠═════╦════════════╦═══════╦═══════════════════════════╣")
        ui_lines.append("║  #  ║   Power    ║ Level ║         Status            ║")
        ui_lines.append("╠═════╬════════════╬═══════╬═══════════════════════════╣")

        # Rows - show in scan order for debugging
        for i, opp in enumerate(display_opponents, 1):
            power = opp['power']
            level = opp.get('level')
            level_str = f"L{level}" if level else "?"

            # Determine status
            if not opp.get('available', True):
                status = "Already defeated"
            elif power in target_powers:
                status = "✓ WILL FIGHT"
            else:
                status = "Skipped (filters)"

            # Format row with proper spacing
            power_str = f"{power:,}".rjust(10)
            level_str = level_str.center(5)

            ui_lines.append(f"║ {i:3d} ║ {power_str} ║ {level_str} ║ {status:25s} ║")

        # Footer
        ui_lines.append("╚═════╩════════════╩═══════╩═══════════════════════════╝")
        ui_lines.append("")

        # Summary
        total = len(all_opponents)
        will_fight = len(targets)
        defeated = sum(1 for o in all_opponents if not o.get('available', True))
        filtered = total - defeated - will_fight

        ui_lines.append(f"Summary: {total} total opponents")
        ui_lines.append(f"         {will_fight} will be fought")
        ui_lines.append(f"         {defeated} already defeated")
        ui_lines.append(f"         {filtered} filtered out")

        # Send to UI if callback available
        if self.arena_status_callback:
            self.arena_status_callback('\n'.join(ui_lines))

        # Also log a simplified version
        self.log("")
        self.log(f"  📋 Scan Results: {total} opponents found")
        self.log(f"     • {will_fight} will be fought")
        self.log(f"     • {defeated} already defeated")
        self.log(f"     • {filtered} filtered out")
        self.log("")

        # Print full opponent list for debugging (in scan order)
        self.log("  📋 Full Opponent List (scan order):")
        for i, opp in enumerate(display_opponents, 1):
            level_str = f"L{opp['level']}" if opp['level'] else "L?"
            status = "✓" if opp.get('available', True) else "✗"
            target = "→" if opp['power'] in target_powers else " "
            self.log(f"     {target} {i:2d}. {status} {opp['power']:7,} power {level_str:4s}")
        self.log("")

    def filter_and_sort_targets(self, opponents):
        """
        Filter out defeated/too-strong/too-high-level opponents and sort by power.

        Filter logic per opponent:
            Pass if (power <= max_power AND level <= max_level)
                 OR (power <= or_power)

        The OR condition catches easy wins from high-level players with
        weak teams, regardless of their level.

        Returns:
            Sorted list of available opponents.
        """
        # Filter defeated
        available = [o for o in opponents if o.get('available', True)]
        defeated = len(opponents) - len(available)

        max_power = config.ARENA_MAX_OPPONENT_POWER
        max_level = config.ARENA_MAX_OPPONENT_LEVEL
        or_power = config.ARENA_OR_POWER

        # Combined filter: (power AND level) OR or_power
        if max_power > 0 or max_level > 0 or or_power > 0:
            filtered = []
            for o in available:
                power = o['power']
                level = o.get('level')

                # Check primary condition: power <= max AND level <= max
                # When level is None (OCR couldn't read it confidently),
                # assume the level is TOO HIGH — don't let unknown-level
                # opponents pass the primary filter. They can still pass
                # via the OR power condition if their power is low enough.
                passes_primary = True
                if max_power > 0 and power > max_power:
                    passes_primary = False
                if max_level > 0:
                    if level is None or level > max_level:
                        passes_primary = False

                # Check OR condition: power <= or_power (regardless of level)
                passes_or = or_power > 0 and power <= or_power

                if passes_primary or passes_or:
                    filtered.append(o)

            available = filtered

        # Sort
        available.sort(key=lambda x: x['power'],
                       reverse=not config.ARENA_ATTACK_WEAKEST_FIRST)

        # Display nice table showing all opponents and which will be fought
        self._display_opponent_table(opponents, available)

        return available

    def click_refresh_list(self):
        """Click the free Refresh button. Never clicks paid refresh to avoid spending gems."""
        # First check if template exists with find_template to get match score
        found, location, size = self.template_matcher.find_template(
            TEMPLATE_FREE_REFRESH, threshold=0.8
        )

        if found:
            # Click it
            self.template_matcher.click_at_offset(
                location[0], location[1], wait_after=2.0
            )
            self.log(f"  Refreshing opponent list (free)...")
            return True

        # Debug: save screenshot when refresh not found
        import os
        import cv2
        from config import SCRIPT_DIR

        # Get the best match score even if below threshold
        img = self.window_capture.capture()
        if img is not None:
            # Save full screenshot
            debug_path = os.path.join(SCRIPT_DIR, 'debug', 'refresh_not_found_full.png')
            cv2.imwrite(debug_path, img)

            # Find where the refresh button should be and crop that area
            template = cv2.imread(TEMPLATE_FREE_REFRESH, cv2.IMREAD_COLOR)
            if template is not None:
                result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)

                # Crop around the best match location (even if below threshold)
                h, w = template.shape[:2]
                height, width = img.shape[:2]

                # Expand the crop area around the best match
                x1 = max(0, max_loc[0] - 50)
                y1 = max(0, max_loc[1] - 50)
                x2 = min(width, max_loc[0] + w + 50)
                y2 = min(height, max_loc[1] + h + 50)

                crop = img[y1:y2, x1:x2]
                crop_path = os.path.join(SCRIPT_DIR, 'debug', 'refresh_button_area.png')
                cv2.imwrite(crop_path, crop)

                # Draw rectangle on full image showing where we looked
                img_marked = img.copy()
                cv2.rectangle(img_marked, (max_loc[0], max_loc[1]),
                             (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
                marked_path = os.path.join(SCRIPT_DIR, 'debug', 'refresh_not_found_marked.png')
                cv2.imwrite(marked_path, img_marked)

                self.log(f"  No free refresh available (best match: {max_val:.3f}, threshold: 0.8)")
                self.log(f"  Debug images saved:")
                self.log(f"    - debug/refresh_not_found_full.png")
                self.log(f"    - debug/refresh_not_found_marked.png (shows best match location)")
                self.log(f"    - debug/refresh_button_area.png (cropped region)")
            else:
                self.log(f"  No free refresh available (template file not found)")
        else:
            self.log(f"  No free refresh available (screenshot failed)")

        return False

    def _navigate_home(self):
        """Navigate back to home screen."""
        for i in range(5):
            success, _ = self.template_matcher.find_and_click(
                TEMPLATE_BACK, threshold=0.8, wait_after=1.5
            )
            if success:
                self.log(f'    Clicked Back ({i + 1})')
            else:
                self.log(f'    Reached home (no more Back buttons)')
                break

        # Reset home screen zoom to prevent accidental zoom issues
        self.log('    Resetting home screen zoom...')
        reset_home_screen_zoom(self.window_capture, self.clicker)

    def _check_tokens_or_stop(self):
        """
        Check if we have arena tokens. If empty, try free refill.

        Returns:
            True if we have tokens (or got a free refill).
            False if truly out of tokens (stop the session).
        """
        token_status = self.battle_runner.ensure_arena_tokens()
        if token_status == 'no_tokens':
            self.log('  Out of arena tokens — session complete')
            return False
        return True

    def _refresh_or_wait(self):
        """
        Try to refresh the opponent list. If no free refresh, check
        tokens and wait 15 minutes for the refresh timer to reset.

        Returns:
            True if we should continue (refreshed or waited).
            False if we should stop (out of tokens).
        """
        # First make sure we have tokens
        token_status = self.battle_runner.ensure_arena_tokens()
        if token_status == 'no_tokens':
            self.log('  Out of arena tokens — session complete')
            self.tokens_exhausted = True
            return False

        # Try free refresh
        if self.click_refresh_list():
            # Clean up old power snapshots since list has refreshed
            self.scanner._cleanup_snapshots()
            return True

        # No free refresh available
        if getattr(self, 'skip_refresh_wait', False):
            # Daily loop mode: return False to signal we should try again later
            self.log('  No free refresh — will retry arena later in daily loop')
            return False

        # Standalone mode: wait for timer to reset
        wait_min = REFRESH_WAIT_SECONDS // 60
        self.log(f'  No free refresh — waiting {wait_min} minutes for reset...')

        elapsed = 0
        while elapsed < REFRESH_WAIT_SECONDS:
            if self.should_stop():
                self.log('  STOPPED BY USER during wait')
                return False

            # Sleep in 30-second chunks so stop checks are responsive
            self.clicker.natural_delay(30)
            elapsed += 30
            remaining = (REFRESH_WAIT_SECONDS - elapsed) // 60
            if remaining > 0 and elapsed % 60 == 0:
                self.log(f'    {remaining} minute(s) remaining...')

        self.log('  Wait complete — trying refresh again')

        # Try refresh again after waiting
        if self.click_refresh_list():
            # Clean up old power snapshots since list has refreshed
            self.scanner._cleanup_snapshots()
            return True

        # Still no refresh — check tokens one more time
        token_status = self.battle_runner.ensure_arena_tokens()
        if token_status == 'no_tokens':
            self.log('  Out of arena tokens — session complete')
            self.tokens_exhausted = True
            return False

        # Have tokens but refresh failed — try once more
        self.log('  Refresh still unavailable — retrying...')
        if self.click_refresh_list():
            self.scanner._cleanup_snapshots()
            return True

        # No refresh available but we have tokens — continue with same list
        self.log('  No refresh available, but arena tokens remain')
        self.log('  Continuing with current opponent list...')
        return True

    def run(self, scan_only=False, test_single_attack=False, max_battles=None, skip_refresh_wait=False):
        """
        Run the Classic Arena sequence.

        Args:
            scan_only: Just scan and report, no attacks.
            test_single_attack: Scan and attack one target only.
            max_battles: Override per-cycle battle limit.
            skip_refresh_wait: If True, return early when refresh unavailable instead of waiting 15min.
        """
        self.skip_refresh_wait = skip_refresh_wait
        effective_max = max_battles or ARENA_MAX_BATTLES

        if scan_only:
            mode = "SCAN ONLY"
        elif test_single_attack:
            mode = "TEST (single attack)"
        else:
            mode = "FULL BATTLE (continuous)"

        self.log('')
        self.log('=' * 60)
        self.log(f'  [V2] CLASSIC ARENA — {mode}')
        self.log('=' * 60)

        try:
            # Acquire window
            self.log('  Acquiring game window...')
            window_info = self.window_capture.get_window()
            self.log(f'  Window: ({window_info[0]}, {window_info[1]}) {window_info[2]}x{window_info[3]}')

            # ── SCAN ONLY ──────────────────────────────────────────
            if scan_only:
                self.scanner.scroll_to_top_fast()
                opponents = self.scanner.run_fluid_scan()
                if opponents:
                    self.filter_and_sort_targets(opponents)
                self.log('')
                self.log('  [SCAN ONLY — done]')
                return True

            # ── TEST SINGLE ATTACK ─────────────────────────────────
            if test_single_attack:
                self.scanner.scroll_to_top_fast()
                opponents = self.scanner.run_fluid_scan()
                if not opponents:
                    self.log('  No opponents found!')
                    return False

                targets = self.filter_and_sort_targets(opponents)
                if not targets:
                    self.log('  No available targets!')
                    return False

                # Snapshot first opponent for list-change detection
                self.scanner.scroll_to_top_fast()
                self.scanner.snapshot_first_opponent()

                self.battle_runner.attack_targets(targets, single_attack=True)
                return True

            # ── FULL CONTINUOUS LOOP ───────────────────────────────
            total_battles = 0
            cycle = 0
            consecutive_no_targets = 0

            while True:
                if self.should_stop():
                    self.log('')
                    self.log('  STOPPED BY USER')
                    break

                cycle += 1
                self.log('')
                self.log(f'  ┌─ CYCLE #{cycle} (total battles: {total_battles}) ─┐')

                # Phase 1: Scan
                self.scanner.scroll_to_top_fast()
                opponents = self.scanner.run_fluid_scan()

                if not opponents:
                    self.log('  No opponents found — refreshing...')
                    if not self._refresh_or_wait():
                        break
                    consecutive_no_targets = 0
                    continue

                # Phase 2: Sort & filter
                targets = self.filter_and_sort_targets(opponents)

                if not targets:
                    consecutive_no_targets += 1
                    self.log(f'  No available targets — refreshing... (attempt {consecutive_no_targets})')

                    # If we've tried 3 times and still no targets, we're done
                    if consecutive_no_targets >= 3:
                        self.log('  All opponents defeated or filtered out — session complete')
                        break

                    if not self._refresh_or_wait():
                        break
                    continue

                # Reset counter when we find targets
                consecutive_no_targets = 0

                # Snapshot first opponent for list-change detection
                self.scanner.scroll_to_top_fast()
                self.scanner.snapshot_first_opponent()

                # Phase 3: Attack
                results = self.battle_runner.attack_targets(targets)
                total_battles += results['completed']

                if self.should_stop():
                    self.log('')
                    self.log('  STOPPED BY USER')
                    break

                if results['exit_reason'] == 'no_tokens':
                    # Out of tokens mid-attack — check if we can refill
                    if not self._check_tokens_or_stop():
                        break
                    # Got tokens back, continue to refresh
                    if not self._refresh_or_wait():
                        break
                    continue

                # If the game already refreshed the list (tier change),
                # skip clicking refresh — just rescan the new list.
                if results['exit_reason'] == 'list_changed':
                    self.log(f"  Game refreshed list — rescanning without using a refresh")
                    # Clean up old power snapshots since list has changed
                    self.scanner._cleanup_snapshots()
                    continue

                # Phase 4: Refresh for next cycle
                if not self._refresh_or_wait():
                    break

            # ── Done ───────────────────────────────────────────────
            self.log('')
            self.log('=' * 60)
            self.log(f'  [V2] COMPLETE — {total_battles} battles')
            self.log('=' * 60)

            self.log('')
            self.log('  Navigating home...')
            self._navigate_home()

            return True

        except Exception as e:
            import traceback
            self.log('')
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
