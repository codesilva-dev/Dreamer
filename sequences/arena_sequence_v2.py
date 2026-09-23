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
                 log_func=None, stop_check=None):
        self.window_capture = window_capture
        self.template_matcher = template_matcher
        self.text_recognizer = text_recognizer
        self.log = log_func or print
        self.stop_check = stop_check

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
        if defeated > 0:
            self.log(f"  Filtered out {defeated} already defeated")

        max_power = config.ARENA_MAX_OPPONENT_POWER
        max_level = config.ARENA_MAX_OPPONENT_LEVEL
        or_power = config.ARENA_OR_POWER

        # Combined filter: (power AND level) OR or_power
        if max_power > 0 or max_level > 0 or or_power > 0:
            before = len(available)
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

            # Log what filters were applied
            parts = []
            if max_power > 0:
                parts.append(f"power ≤ {max_power:,}")
            if max_level > 0:
                parts.append(f"level ≤ L{max_level}")
            filter_desc = ' AND '.join(parts) if parts else 'none'
            if or_power > 0:
                filter_desc += f" OR power ≤ {or_power:,}"
            self.log(f"  Filter ({filter_desc}): {before} → {len(available)}")

        # Sort
        available.sort(key=lambda x: x['power'],
                       reverse=not config.ARENA_ATTACK_WEAKEST_FIRST)

        order = "weakest first" if config.ARENA_ATTACK_WEAKEST_FIRST else "strongest first"
        self.log(f"  Targets ({order}): {len(available)}")
        if available:
            powers = [f"{o['power']:,}" for o in available[:8]]
            if len(available) > 8:
                powers.append(f"...+{len(available) - 8} more")
            self.log(f"    {', '.join(powers)}")

        return available

    def click_refresh_list(self):
        """Click the free Refresh button. Never clicks paid refresh to avoid spending gems."""
        success, _ = self.template_matcher.find_and_click(
            TEMPLATE_FREE_REFRESH, threshold=0.8, wait_after=2.0
        )
        if success:
            self.log(f"  Refreshing opponent list (free)...")
            return True

        self.log(f"  No free refresh available")
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
            return False

        # Try free refresh
        if self.click_refresh_list():
            return True

        # No free refresh — wait for timer to reset
        wait_min = REFRESH_WAIT_SECONDS // 60
        self.log(f'  No free refresh — waiting {wait_min} minutes for reset...')

        elapsed = 0
        while elapsed < REFRESH_WAIT_SECONDS:
            if self.should_stop():
                self.log('  STOPPED BY USER during wait')
                return False

            # Sleep in 30-second chunks so stop checks are responsive
            time.sleep(30)
            elapsed += 30
            remaining = (REFRESH_WAIT_SECONDS - elapsed) // 60
            if remaining > 0 and elapsed % 60 == 0:
                self.log(f'    {remaining} minute(s) remaining...')

        self.log('  Wait complete — trying refresh again')

        # Try refresh again after waiting
        if self.click_refresh_list():
            return True

        # Still no refresh — check tokens one more time
        token_status = self.battle_runner.ensure_arena_tokens()
        if token_status == 'no_tokens':
            self.log('  Out of arena tokens — session complete')
            return False

        # Have tokens but refresh failed — try once more
        self.log('  Refresh still unavailable — retrying...')
        return self.click_refresh_list()

    def run(self, scan_only=False, test_single_attack=False, max_battles=None):
        """
        Run the Classic Arena sequence.

        Args:
            scan_only: Just scan and report, no attacks.
            test_single_attack: Scan and attack one target only.
            max_battles: Override per-cycle battle limit.
        """
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
                    continue

                # Phase 2: Sort & filter
                targets = self.filter_and_sort_targets(opponents)

                if not targets:
                    self.log('  No available targets — refreshing...')
                    if not self._refresh_or_wait():
                        break
                    continue

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
