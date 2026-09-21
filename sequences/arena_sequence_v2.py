"""
Classic Arena Sequence V2 — Vision-based orchestrator.

Coordinates: scan list → sort targets → attack all → refresh → repeat.
Uses ArenaListScanner for scanning and ArenaBattleRunner for attacking.
"""

from sequences.arena_scanner_v2 import ArenaListScanner
from sequences.arena_battle_v2 import ArenaBattleRunner

import config
from config import (
    ARENA_MAX_BATTLES,
    TEMPLATE_FREE_REFRESH,
    TEMPLATE_BACK,
)


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

        Returns:
            Sorted list of available opponents.
        """
        # Filter defeated
        available = [o for o in opponents if o.get('available', True)]
        defeated = len(opponents) - len(available)
        if defeated > 0:
            self.log(f"  Filtered out {defeated} already defeated")

        # Filter by max power
        if config.ARENA_MAX_OPPONENT_POWER > 0:
            before = len(available)
            available = [o for o in available if o['power'] <= config.ARENA_MAX_OPPONENT_POWER]
            self.log(f"  Power filter: {before} → {len(available)} (max {config.ARENA_MAX_OPPONENT_POWER:,})")

        # Filter by max level
        if config.ARENA_MAX_OPPONENT_LEVEL > 0:
            before = len(available)
            available = [o for o in available
                         if o.get('level') is None or o['level'] <= config.ARENA_MAX_OPPONENT_LEVEL]
            self.log(f"  Level filter: {before} → {len(available)} (max L{config.ARENA_MAX_OPPONENT_LEVEL})")

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
                    token_status = self.battle_runner.ensure_arena_tokens()
                    if token_status == 'no_tokens':
                        break
                    if not self.click_refresh_list():
                        self.log('  No free refresh and no opponents — done')
                        break
                    continue

                # Phase 2: Sort & filter
                targets = self.filter_and_sort_targets(opponents)

                if not targets:
                    self.log('  No available targets — refreshing...')
                    token_status = self.battle_runner.ensure_arena_tokens()
                    if token_status == 'no_tokens':
                        break
                    if not self.click_refresh_list():
                        self.log('  No free refresh and no valid targets — done')
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
                    break

                # If the game already refreshed the list (tier change),
                # skip clicking refresh — just rescan the new list.
                if results['exit_reason'] == 'list_changed':
                    self.log(f"  Game refreshed list — rescanning without using a refresh")
                    continue

                # Phase 4: Refresh for next cycle
                token_status = self.battle_runner.ensure_arena_tokens()
                if token_status == 'no_tokens':
                    break
                if not self.click_refresh_list():
                    self.log('  No free refresh available — done')
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
