"""
Battle Sequence - Handles attacking opponents and battle flow
Uses smart scroll traversal to minimize scrolling
"""

import time
import pyautogui

from config import (
    ARENA_SCAN_DELAY,
    ARENA_SCROLL_DELAY,
    ARENA_BATTLE_DELAY,
    ARENA_BATTLE_BUTTON_X,
    ARENA_MAX_BATTLES,
    ARENA_MAX_OPPONENT_POWER,
    ARENA_ATTACK_WEAKEST_FIRST,
    TEMPLATE_START_FIGHT,
    TEMPLATE_BATTLE_COMPLETE,
    TEMPLATE_RETURN_ARENA,
    TEMPLATE_FREE_REFRESH,
    TEMPLATE_PAY_REFRESH,
    TEMPLATE_EMPTY_ATOKENS,
    TEMPLATE_FREE_ATOKENS,
    TEMPLATE_BACK,
)


class BattleSequence:
    """
    Manages attacking opponents and the battle flow.
    
    Key features:
    - Smart traversal: navigates directly to target scroll position
    - Post-battle verification: ensures opponent list hasn't changed
    - Handles tier bracket changes that refresh the list
    """
    
    def __init__(self, window_capture, opponent_scanner, template_matcher, log_func=None, stop_check=None):
        self.window_capture = window_capture
        self.scanner = opponent_scanner  # OpponentScanner instance
        self.template_matcher = template_matcher
        self.log = log_func or print
        self.stop_check = stop_check  # Function to check if stop requested
        
        # Battle state
        self.sorted_targets = []
        self.current_target_index = 0
        self.battles_completed = 0
        self.max_battles = ARENA_MAX_BATTLES
        
        # List verification
        self.list_valid = True
    
    def should_stop(self):
        """Check if stop was requested"""
        return self.stop_check and self.stop_check()
        
    def reset(self):
        """Reset battle state"""
        self.sorted_targets = []
        self.current_target_index = 0
        self.battles_completed = 0
        self.list_valid = True
    
    def prepare_targets(self, opponents, weakest_first=True, max_power=None):
        """
        Prepare sorted target list from scanned opponents
        
        Args:
            opponents: List of opponent dicts from scanner
            weakest_first: If True, attack weakest first
            max_power: Skip opponents above this power (0 = no limit)
        """
        self.reset()
        
        # Start with all opponents
        filtered = opponents
        
        # Filter out unavailable (defeated) opponents
        available_opponents = [o for o in filtered if o.get('available', True)]
        defeated_count = len(filtered) - len(available_opponents)
        if defeated_count > 0:
            self.log(f"  Filtered out {defeated_count} already defeated opponent(s)")
        filtered = available_opponents
        
        # Filter by max power if specified
        if max_power and max_power > 0:
            before_count = len(filtered)
            filtered = [o for o in filtered if o['power'] <= max_power]
            self.log(f"  Filtered from {before_count} to {len(filtered)} opponents (max power: {max_power:,})")
        
        # Sort by power
        self.sorted_targets = sorted(
            filtered,
            key=lambda x: x['power'],
            reverse=not weakest_first
        )
        
        self._log_target_list()
        
        return self.sorted_targets
    
    def _log_target_list(self):
        """Log the sorted target list"""
        order = "weakest first" if ARENA_ATTACK_WEAKEST_FIRST else "strongest first"
        
        self.log("")
        self.log(f"  Targets sorted ({order}): {len(self.sorted_targets)} available")
        
        # Compact list - just show powers on one line
        powers = [f"{o['power']:,}" for o in self.sorted_targets[:5]]  # First 5
        if len(self.sorted_targets) > 5:
            powers.append(f"...+{len(self.sorted_targets)-5} more")
        self.log(f"    Powers: {', '.join(powers)}")
    
    def navigate_to_target(self, target):
        """
        Navigate to a target's scroll position using smart traversal
        
        Args:
            target: Opponent dict with 'power' and 'scroll_position'
            
        Returns:
            True if navigation successful and target is visible
        """
        target_power = target['power']
        target_scroll = target.get('scroll_position', 0)
        current_scroll = self.scanner.scroll_count
        
        # Navigate to the target scroll position
        if target_scroll != current_scroll:
            if target_scroll < current_scroll:
                scrolls_needed = current_scroll - target_scroll
                for i in range(scrolls_needed):
                    self.scanner.scroll_list(direction='up')
            else:
                scrolls_needed = target_scroll - current_scroll
                for i in range(scrolls_needed):
                    self.scanner.scroll_list(direction='down')
        
        # Verify target is visible
        time.sleep(ARENA_SCAN_DELAY)
        
        if self.scanner.verify_opponent_at_position(target_power):
            return True
        
        # Try one scroll in each direction if not found
        self.scanner.scroll_list(direction='down')
        time.sleep(ARENA_SCAN_DELAY)
        if self.scanner.verify_opponent_at_position(target_power):
            return True
        
        # Try up (2 scrolls to go past original)
        self.scanner.scroll_list(direction='up')
        self.scanner.scroll_list(direction='up')
        time.sleep(ARENA_SCAN_DELAY)
        if self.scanner.verify_opponent_at_position(target_power):
            return True
        
        # Return to expected position
        self.scanner.scroll_list(direction='down')
        
        self.log(f"    ✗ Could not find target {target_power:,} after scrolling")
        return False
    
    def click_battle_button(self, target_power, stored_y_position=None):
        """
        Click the battle button for an opponent
        
        Args:
            target_power: The power value of the opponent
            stored_y_position: Pre-stored Y position from initial scan (preferred)
        
        Returns:
            True if button was clicked successfully
        """
        # Use stored Y position if available, otherwise re-scan (less reliable)
        if stored_y_position is not None:
            y_pos = stored_y_position
        else:
            y_pos = self.scanner.find_opponent_y_position(target_power)
        
        if y_pos is None:
            self.log(f"    ✗ Could not find target Y position")
            return False
        
        # Calculate button position
        left, top, width, height = self.scanner.get_window_dimensions()
        
        # Get frame to calculate x position AND verify button is available
        frame = self.window_capture.capture()
        frame_width = frame.shape[1]
        
        # Verify opponent is still available (orange button, not defeated)
        is_available = self.scanner.check_battle_available(frame, y_pos)
        if not is_available:
            self.log(f"    ✗ Opponent already defeated (gray button)")
            return False
        
        button_x = left + int(frame_width * ARENA_BATTLE_BUTTON_X)
        
        # The OCR y_position is where "Team Power:" text appears (bottom of opponent row)
        # The battle button is centered vertically in the row, so we need to go UP
        # Opponent rows are ~115px tall, text is at bottom, button center is ~50px higher
        BUTTON_Y_OFFSET = -50
        button_y = top + y_pos + BUTTON_Y_OFFSET
        
        self.log(f"    Clicking Battle button at ({button_x}, {button_y}) [y_pos={y_pos}, offset={BUTTON_Y_OFFSET}]")
        
        pyautogui.moveTo(button_x, button_y, duration=0.3)
        time.sleep(0.2)
        pyautogui.click()
        
        return True
    
    def click_start_fight(self):
        """
        Click the "Start Fight" button to begin the battle.
        Uses template matching to find the button.
        
        Returns:
            True if button was clicked successfully
        """
        success, message = self.template_matcher.find_and_click(
            TEMPLATE_START_FIGHT,
            threshold=0.8,
            wait_after=1.0  # Short wait, battle loading handled separately
        )
        
        if success:
            return True
        else:
            self.log(f"    ✗ Start Fight button not found")
            return False
    
    def ensure_arena_tokens(self):
        """
        Check if we have arena tokens. If empty, try to get free tokens.
        
        Returns:
            'ok' - Have tokens, proceed
            'refilled' - Got free tokens, proceed (scroll reset to top)
            'no_tokens' - No tokens and can't get free ones, need to exit
        """
        # Look for empty tokens indicator (very high threshold - 9/10 and 0/10 look nearly identical)
        found, location, size = self.template_matcher.find_template(
            TEMPLATE_EMPTY_ATOKENS,
            threshold=0.98
        )
        
        if not found:
            return 'ok'
        
        self.log(f"    ! Empty tokens - attempting refill...")
        
        # Click the + button (left side of the empty tokens image)
        plus_offset_x = -(size[0] // 2) - 20
        self.template_matcher.click_at_offset(
            location[0], location[1],
            offset_x=plus_offset_x,
            wait_after=1.5
        )
        
        # Look for free tokens option
        time.sleep(0.5)
        found_free, _, _ = self.template_matcher.find_template(
            TEMPLATE_FREE_ATOKENS,
            threshold=0.8
        )
        
        if found_free:
            self.template_matcher.find_and_click(
                TEMPLATE_FREE_ATOKENS,
                threshold=0.8,
                wait_after=2.0
            )
            self.log(f"    ✓ Tokens refilled (free)")
            # Reset scroll position - the list resets to top after refill
            self.scanner.current_scroll_position = 0
            return 'refilled'
        else:
            self.log(f"    ✗ No free tokens - out of tokens")
            # Press Escape to close the popup
            import pyautogui
            pyautogui.press('escape')
            time.sleep(0.5)
            return 'no_tokens'
    
    def wait_for_battle_complete(self, timeout=120, check_interval=3.0):
        """
        Wait for the battle to complete by looking for the "Battle Complete" screen.
        Polls every check_interval seconds until found or timeout.
        
        Args:
            timeout: Maximum seconds to wait (default 120s = 2 minutes)
            check_interval: Seconds between each check (default 3s)
            
        Returns:
            True if Battle Complete was found and clicked
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            success, message = self.template_matcher.find_and_click(
                TEMPLATE_BATTLE_COMPLETE,
                threshold=0.8,
                wait_after=1.0  # Wait after clicking
            )
            
            if success:
                return True
            
            time.sleep(check_interval)
        
        self.log(f"    ✗ Timeout waiting for Battle Complete ({timeout}s)")
        return False
    
    def click_return_arena(self, max_attempts=5, check_interval=1.0):
        """
        Click the "Return Arena" button to go back to opponent list.
        
        Args:
            max_attempts: Maximum number of attempts to find the button
            check_interval: Seconds between attempts
            
        Returns:
            True if button was clicked successfully
        """
        for attempt in range(max_attempts):
            success, message = self.template_matcher.find_and_click(
                TEMPLATE_RETURN_ARENA,
                threshold=0.8,
                wait_after=1.5  # Wait for arena list to load
            )
            
            if success:
                return True
            
            if attempt < max_attempts - 1:
                time.sleep(check_interval)
        
        self.log(f"    ✗ Return Arena button not found")
        return False
    
    def verify_list_unchanged(self, expected_powers_at_position):
        """
        Verify the opponent list hasn't changed (tier bracket refresh)
        
        Args:
            expected_powers_at_position: Set of powers expected at current scroll
            
        Returns:
            True if list is still valid, False if refreshed
        """
        current_powers = self.scanner.get_current_visible_powers()
        
        # Check if at least one expected opponent is still visible
        overlap = current_powers & expected_powers_at_position
        
        if overlap:
            self.log(f"    ✓ List verified (found {len(overlap)} expected opponent(s))")
            return True
        else:
            self.log(f"    ✗ LIST CHANGED - expected powers not found!")
            self.log(f"      Expected: {expected_powers_at_position}")
            self.log(f"      Found: {current_powers}")
            self.list_valid = False
            return False
    
    def attack_next_target(self):
        """
        Attack the next target in the sorted list
        
        Returns:
            'success' - battle initiated
            'skip' - target not found, skipped
            'no_more' - no more targets
            'max_reached' - max battles reached
            'list_invalid' - opponent list changed (needs rescan)
            'no_tokens' - out of arena tokens, need to exit
        """
        if not self.list_valid:
            return 'list_invalid'
        
        if self.current_target_index >= len(self.sorted_targets):
            return 'no_more'
        
        if self.battles_completed >= self.max_battles:
            return 'max_reached'
        
        # Check if we have arena tokens before attempting attack
        token_status = self.ensure_arena_tokens()
        if token_status == 'no_tokens':
            return 'no_tokens'
        
        target = self.sorted_targets[self.current_target_index]
        target_power = target['power']
        target_scroll = target.get('scroll_position', 0)
        target_y_pos = target.get('y_position')  # Use stored Y position
        current_scroll = self.scanner.scroll_count
        
        self.log(f"  [{self.current_target_index+1}/{len(self.sorted_targets)}] Attacking Power {target['power']:,} (scroll {current_scroll}->{target_scroll})")
        
        # Navigate to target
        if not self.navigate_to_target(target):
            self.log(f"    ✗ Failed to navigate to opponent, skipping")
            self.current_target_index += 1
            return 'skip'
        
        # Click opponent's battle button (opens team selection screen)
        # Use stored Y position from initial scan - more reliable than re-scanning
        if not self.click_battle_button(target_power, stored_y_position=target_y_pos):
            self.log(f"    ✗ Failed to click battle button, skipping")
            self.current_target_index += 1
            return 'skip'
        
        # Wait for team selection screen to load
        time.sleep(1.0)
        
        # Click "Start Fight" button to begin battle
        if not self.click_start_fight():
            self.log(f"    ✗ Failed to click Start Fight button")
            self.current_target_index += 1
            return 'skip'
        
        # Wait for battle to complete
        if not self.wait_for_battle_complete():
            self.log(f"    ✗ Battle completion not detected")
            self.current_target_index += 1
            return 'skip'
        
        # Wait 1 second then click Return Arena
        time.sleep(1.0)
        if not self.click_return_arena():
            self.log(f"    ✗ Failed to return to arena")
            self.current_target_index += 1
            return 'skip'
        
        # Game resets to top of list after battle - update scroll tracking
        self.scanner.scroll_count = 0
        
        # Wait for arena list to fully load
        time.sleep(2.0)
        
        self.current_target_index += 1
        self.battles_completed += 1
        self.log(f"    ✓ Battle {self.battles_completed} complete")
        
        return 'success'
    
    def run_attack_phase(self, single_attack=False):
        """
        Run the attack phase
        
        Args:
            single_attack: If True, only attack one target (for testing)
        """
        if not self.sorted_targets:
            self.log("  No opponents to attack!")
            return True
        
        self.log("")
        self.log(f"  Attacking {len(self.sorted_targets)} targets...")
        
        if single_attack:
            # Just attack first target
            result = self.attack_next_target()
            self._log_attack_result(result)
        else:
            # Attack all targets until we hit a stopping condition
            while True:
                # Check for stop request before each attack
                if self.should_stop():
                    self.log(f"    ⚠ STOPPED BY USER")
                    result = 'stopped'
                    break
                
                result = self.attack_next_target()
                
                # Stop conditions
                if result in ('no_more', 'max_reached', 'list_invalid', 'no_tokens'):
                    self._log_attack_result(result)
                    break
                
                # 'success' or 'skip' - continue to next target
                # (battle completion already handled inside attack_next_target)
        
        self._log_phase_complete()
        
        # Store result for caller to check
        self.last_attack_result = result
        
        # Return False if stopped or no tokens (both should exit loop)
        return result not in ('no_tokens', 'stopped')
    
    def check_needs_refresh(self):
        """
        Check if we need to refresh the opponent list.
        Scans the first visible opponent and compares to remaining targets.
        
        Returns:
            True if the first opponent is the same as our last undefeated target
        """
        # If we attacked all targets, no need to refresh
        if self.current_target_index >= len(self.sorted_targets):
            return False
        
        # Get the next target we couldn't defeat (too strong)
        remaining_target = self.sorted_targets[self.current_target_index]
        remaining_power = remaining_target['power']
        
        # Quick scan of first visible opponent
        time.sleep(ARENA_SCAN_DELAY)
        frame = self.window_capture.capture()
        height, width = frame.shape[:2]
        
        # Scan a region where the first opponent's Team Power would be
        from config import ARENA_OCR_REGION
        roi_x = int(width * ARENA_OCR_REGION['x_start'])
        roi_y = int(height * ARENA_OCR_REGION['y_start'])
        roi_w = int(width * ARENA_OCR_REGION['width'])
        # Just scan top portion for first opponent
        roi_h = int(height * 0.25)
        
        roi_frame = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        powers = self.scanner.text_recognizer.find_all_team_powers(roi_frame)
        
        if powers:
            first_power = powers[0]['power']
            return first_power == remaining_power
        return False
    
    def click_refresh_list(self):
        """
        Click the Refresh button to get new opponents.
        Tries Free Refresh first, then Pay Refresh.
        
        Returns:
            True if button was clicked successfully
        """
        # Try Free Refresh first
        success, _ = self.template_matcher.find_and_click(
            TEMPLATE_FREE_REFRESH,
            threshold=0.8,
            wait_after=2.0
        )
        
        if success:
            self.log(f"  Refreshing opponent list (free)...")
            return True
        
        # Try Pay Refresh if free not available
        success, _ = self.template_matcher.find_and_click(
            TEMPLATE_PAY_REFRESH,
            threshold=0.8,
            wait_after=2.0
        )
        
        if success:
            self.log(f"  Refreshing opponent list (paid)...")
            return True
        
        self.log(f"    \u2717 No refresh button found")
        return False
    
    def _log_attack_result(self, result):
        """Log attack result - only log important states"""
        if result == 'no_tokens':
            self.log(f"    ✗ Out of arena tokens")
        elif result == 'list_invalid':
            self.log(f"    ✗ Opponent list changed - rescan needed")
    
    def _log_phase_complete(self):
        """Log attack phase completion"""
        self.log(f"  Attack phase done: {self.battles_completed} battles completed")


class ClassicArenaSequence:
    """
    High-level Classic Arena sequence coordinator.
    Combines OpponentScanner and BattleSequence.
    """
    
    def __init__(self, window_capture, template_matcher, text_recognizer, log_func=None, stop_check=None):
        self.window_capture = window_capture
        self.template_matcher = template_matcher
        self.text_recognizer = text_recognizer
        self.log = log_func or print
        self.stop_check = stop_check  # Function to check if stop was requested
        
        # Import here to avoid circular import
        from sequences.opponent_scanner import OpponentScanner
        
        # Create scanner and battle sequence
        self.scanner = OpponentScanner(window_capture, text_recognizer, log_func)
        self.battle_seq = BattleSequence(window_capture, self.scanner, template_matcher, log_func, stop_check)
        
        # State
        self.opponents = []
    
    def should_stop(self):
        """Check if stop was requested"""
        if self.stop_check and self.stop_check():
            return True
        return False
    
    def run(self, max_battles=None, scan_only=False, test_single_attack=False):
        """
        Run the full Classic Arena sequence in a continuous loop.
        
        Loops: Scan → Attack all → Refresh → Repeat
        Stops only when: Out of tokens (and no free refills)
        
        Args:
            max_battles: Override max battles (per loop, resets each cycle)
            scan_only: If True, only scan opponents (no loop)
            test_single_attack: If True, scan and attack only one target (no loop)
        """
        effective_max_battles = max_battles or ARENA_MAX_BATTLES
        
        # Determine mode
        if scan_only:
            mode_str = "SCAN ONLY"
        elif test_single_attack:
            mode_str = "TEST MODE (single attack)"
        else:
            mode_str = "FULL BATTLE MODE (continuous)"
        
        self.log('')
        self.log('╔════════════════════════════════════════════════════════════════╗')
        self.log('║          CLASSIC ARENA SEQUENCE STARTING                       ║')
        self.log('╚════════════════════════════════════════════════════════════════╝')
        self.log(f'  Mode: {mode_str}')
        self.log(f'  Max battles per cycle: {effective_max_battles}')
        self.log('')
        
        try:
            # Ensure window is captured
            self.log('  Acquiring game window...')
            window_info = self.window_capture.get_window()
            self.log(f'  Window found: position=({window_info[0]}, {window_info[1]}), size={window_info[2]}x{window_info[3]}')
            
            # Track total battles across all cycles
            total_battles = 0
            cycle_count = 0
            
            # === SCAN ONLY MODE ===
            if scan_only:
                self.opponents = self.scanner.run_full_scan()
                if self.opponents:
                    self.battle_seq.prepare_targets(
                        self.opponents,
                        weakest_first=ARENA_ATTACK_WEAKEST_FIRST,
                        max_power=ARENA_MAX_OPPONENT_POWER
                    )
                self.log('')
                self.log('  [SCAN ONLY MODE - Skipping attack phase]')
                return True
            
            # === TEST SINGLE ATTACK MODE ===
            if test_single_attack:
                self.opponents = self.scanner.run_full_scan()
                if not self.opponents:
                    self.log('  ✗ No opponents found!')
                    return False
                self.battle_seq.max_battles = effective_max_battles
                self.battle_seq.prepare_targets(
                    self.opponents,
                    weakest_first=ARENA_ATTACK_WEAKEST_FIRST,
                    max_power=ARENA_MAX_OPPONENT_POWER
                )
                self.battle_seq.run_attack_phase(single_attack=True)
                return True
            
            # === FULL CONTINUOUS BATTLE MODE ===
            while True:
                # Check for stop request at start of each cycle
                if self.should_stop():
                    self.log('')
                    self.log('  ⚠ STOPPED BY USER')
                    break
                
                cycle_count += 1
                self.log('')
                self.log(f'  ┌─────────────────────────────────────────────────┐')
                self.log(f'  │ ARENA CYCLE #{cycle_count}'.ljust(52) + '│')
                self.log(f'  │ Total battles so far: {total_battles}'.ljust(52) + '│')
                self.log(f'  └─────────────────────────────────────────────────┘')
                
                # Phase 1: Scan opponents
                self.opponents = self.scanner.run_full_scan()
                
                if not self.opponents:
                    self.log('')
                    self.log('  ✗ No opponents found - refreshing list...')
                    # Check tokens before refresh
                    token_status = self.battle_seq.ensure_arena_tokens()
                    if token_status == 'no_tokens':
                        break  # Exit loop - out of tokens
                    self.battle_seq.click_refresh_list()
                    continue  # Try again
                
                # Phase 2: Prepare targets
                self.battle_seq.reset()
                self.battle_seq.max_battles = effective_max_battles
                self.battle_seq.prepare_targets(
                    self.opponents,
                    weakest_first=ARENA_ATTACK_WEAKEST_FIRST,
                    max_power=ARENA_MAX_OPPONENT_POWER
                )
                
                # Check if any available targets
                if not self.battle_seq.sorted_targets:
                    self.log('')
                    self.log('  No available targets - refreshing list...')
                    token_status = self.battle_seq.ensure_arena_tokens()
                    if token_status == 'no_tokens':
                        break
                    self.battle_seq.click_refresh_list()
                    continue
                
                # Phase 3: Attack
                has_tokens = self.battle_seq.run_attack_phase(single_attack=False)
                total_battles += self.battle_seq.battles_completed
                
                # Check for stop IMMEDIATELY after attack phase
                if self.should_stop():
                    self.log('')
                    self.log('  ⚠ STOPPED BY USER')
                    break
                
                if not has_tokens:
                    # Out of tokens during attack
                    break
                
                # Phase 4: Check if we need to refresh or continue
                if self.battle_seq.check_needs_refresh():
                    # Strong opponent remains - check tokens and refresh
                    token_status = self.battle_seq.ensure_arena_tokens()
                    if token_status == 'no_tokens':
                        break
                    self.battle_seq.click_refresh_list()
                    # Loop continues - will rescan
                else:
                    # All opponents defeated! But there might be more after refresh
                    # Check tokens and refresh to continue
                    token_status = self.battle_seq.ensure_arena_tokens()
                    if token_status == 'no_tokens':
                        break
                    self.battle_seq.click_refresh_list()
                    # Loop continues
            
            # === OUT OF TOKENS - Navigate back to home ===
            self.log('')
            self.log('╔════════════════════════════════════════════════════════════════╗')
            self.log('║          OUT OF ARENA TOKENS                                   ║')
            self.log(f'║          Total battles completed: {total_battles:<26} ║')
            self.log('╚════════════════════════════════════════════════════════════════╝')
            
            self.log('')
            self.log('  Navigating back to home...')
            self._navigate_home()
            
            self.log('')
            self.log('╔════════════════════════════════════════════════════════════════╗')
            self.log('║          CLASSIC ARENA SEQUENCE COMPLETE                       ║')
            self.log('╚════════════════════════════════════════════════════════════════╝')
            return True
            
        except Exception as e:
            import traceback
            self.log('')
            self.log('  ╔════════════════════════════════════════╗')
            self.log(f'  ║ ✗ ERROR: {str(e)[:30]:<30} ║')
            self.log('  ╚════════════════════════════════════════╝')
            self.log(f'  Traceback:')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
    
    def _navigate_home(self):
        """
        Navigate back to home screen by clicking Back button multiple times
        """
        max_back_clicks = 5
        for i in range(max_back_clicks):
            success, _ = self.template_matcher.find_and_click(
                TEMPLATE_BACK,
                threshold=0.8,
                wait_after=1.5
            )
            if success:
                self.log(f'    ✓ Clicked Back ({i+1})')
            else:
                self.log(f'    Reached home (no more Back buttons)')
                break
