"""
Clan Boss (CB Main) — Navigate to Clan Boss and select a difficulty.

Navigation: Home -> Battle -> CBStages -> CB1 -> scroll to find difficulty -> fight.

The script scrolls the difficulty list (right side of screen) to find the target
difficulty, then checks the leaderboard (left side) for the player's current damage.
Fights until max damage threshold is reached, then cascades to easier difficulties.

Workflow:
1. Navigate to clan boss screen
2. Find and click difficulty (scroll if needed)
3. Check leaderboard for player's damage
4. If damage < threshold → fight
5. After fight, recheck damage
6. If damage ≥ threshold → cascade to next easier difficulty
"""

import re
import cv2
import time
import json
import os
from datetime import datetime
import pyautogui
import numpy as np
from natural_click import NaturalClick
from text_recognition import TextRecognizer

try:
    import pytesseract
except ImportError:
    pytesseract = None

from config import (
    TEMPLATE_BATTLE, TEMPLATE_CB_STAGES, TEMPLATE_CB1, TEMPLATE_BACK,
    TEMPLATE_CB_EASY, TEMPLATE_CB_NORMAL, TEMPLATE_CB_HARD,
    TEMPLATE_CB_BRUTAL, TEMPLATE_CB_NIGHTMARE, TEMPLATE_CB_ULTRA_NIGHTMARE,
    TEMPLATE_CB_RED_SWORD, TEMPLATE_PVE_BATTLE, TEMPLATE_START, TEMPLATE_CB_QB_TRUE,
    TEMPLATE_BATTLE_COMPLETE, TEMPLATE_CONTINUE, TEMPLATE_CB_VIC_SCREEN, TEMPLATE_CB_NO_KEY,
    TEMPLATE_BASTION,
    CLICK_DELAY,
    CB_SCROLL_REGION, CB_LEADERBOARD_SCROLL_REGION, CB_SCROLL_DELAY,
    CB_MAX_SCROLL_ATTEMPTS, CB_MAX_DAMAGE_THRESHOLDS,
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
        self.text_recognizer = TextRecognizer(window_capture, log_func, debug=False)

    def should_stop(self):
        return self.stop_check and self.stop_check()

    def _scroll(self, direction):
        """Perform a single scroll gesture in the difficulty list (right side)."""
        left, top, width, height = self.window_capture.window_info
        center_x = left + int(width * CB_SCROLL_REGION['x_center'])

        if direction == 'down':
            start_y = top + int(height * CB_SCROLL_REGION['y_end'])
            end_y = top + int(height * CB_SCROLL_REGION['y_start'])
        else:  # up
            start_y = top + int(height * CB_SCROLL_REGION['y_start'])
            end_y = top + int(height * CB_SCROLL_REGION['y_end'])

        pyautogui.moveTo(center_x, start_y, duration=0.2)
        self.clicker.natural_delay(0.1)
        pyautogui.mouseDown()
        self.clicker.natural_delay(0.1)
        pyautogui.moveTo(center_x, end_y, duration=0.6)
        self.clicker.natural_delay(0.5)
        pyautogui.mouseUp()

        self.clicker.natural_delay(CB_SCROLL_DELAY)

    def _scroll_to_edge(self, direction, region='difficulty'):
        """
        Scroll repeatedly until list stops moving (reached edge).

        Args:
            direction: 'up' or 'down'
            region: 'difficulty' (right side) or 'leaderboard' (left side)
        """
        scroll_region = CB_SCROLL_REGION if region == 'difficulty' else CB_LEADERBOARD_SCROLL_REGION

        for i in range(CB_MAX_SCROLL_ATTEMPTS):
            if self.should_stop():
                return
            self._scroll(direction, region)

    def _scroll(self, direction, region='difficulty'):
        """
        Perform a single scroll gesture.

        Args:
            direction: 'up' or 'down'
            region: 'difficulty' (right side) or 'leaderboard' (left side)
        """
        scroll_region = CB_SCROLL_REGION if region == 'difficulty' else CB_LEADERBOARD_SCROLL_REGION
        left, top, width, height = self.window_capture.window_info
        center_x = left + int(width * scroll_region['x_center'])

        if direction == 'down':
            start_y = top + int(height * scroll_region['y_end'])
            end_y = top + int(height * scroll_region['y_start'])
        else:  # up
            start_y = top + int(height * scroll_region['y_start'])
            end_y = top + int(height * scroll_region['y_end'])

        pyautogui.moveTo(center_x, start_y, duration=0.2)
        self.clicker.natural_delay(0.1)
        pyautogui.mouseDown()
        self.clicker.natural_delay(0.1)
        pyautogui.moveTo(center_x, end_y, duration=0.6)
        self.clicker.natural_delay(0.5)
        pyautogui.mouseUp()

        self.clicker.natural_delay(CB_SCROLL_DELAY)

    def _find_and_click_difficulty(self, difficulty):
        """
        Search for the difficulty template. Checks current view first,
        then scrolls down, then scrolls up if needed.

        IMPORTANT: Uses stricter matching (0.9 threshold) to avoid matching
        "Nightmare" when looking for "Ultra-Nightmare" or vice versa.

        Args:
            difficulty: The difficulty name (e.g. 'ultranightmare')

        Returns:
            True if found and clicked, False otherwise
        """
        template = self.DIFFICULTY_TEMPLATES.get(difficulty)
        if not template:
            self.log(f'  Unknown difficulty: {difficulty}')
            return False

        # First, check if it's already visible
        self.log(f'  Looking for {difficulty} difficulty...')
        found, _, _ = self.template_matcher.find_template(template, threshold=0.8)
        if found:
            self.template_matcher.find_and_click(
                template, threshold=0.8, wait_after=CLICK_DELAY
            )
            self.log(f'  Clicked {difficulty} difficulty')
            return True

        # Not visible - scroll down to search
        self.log('  Not visible — scrolling down to search')
        for i in range(CB_MAX_SCROLL_ATTEMPTS):
            if self.should_stop():
                return False

            self._scroll('down', region='difficulty')

            found, _, _ = self.template_matcher.find_template(template, threshold=0.8)
            if found:
                self.template_matcher.find_and_click(
                    template, threshold=0.8, wait_after=CLICK_DELAY
                )
                self.log(f'  Clicked {difficulty} difficulty')
                return True

        # Still not found - scroll back up to search the top
        self.log('  Not found scrolling down — scrolling up to search')
        for i in range(CB_MAX_SCROLL_ATTEMPTS):
            if self.should_stop():
                return False

            self._scroll('up', region='difficulty')

            found, _, _ = self.template_matcher.find_template(template, threshold=0.8)
            if found:
                self.template_matcher.find_and_click(
                    template, threshold=0.8, wait_after=CLICK_DELAY
                )
                self.log(f'  Clicked {difficulty} difficulty')
                return True

        self.log(f'  {difficulty} difficulty not found after scrolling both directions')
        return False

    def _scroll_to_leaderboard_top(self):
        """
        Scroll to the top of the leaderboard (until rank 1 is visible).
        """
        self.log('  Scrolling to top of leaderboard...')
        max_scroll_attempts = 10

        for attempt in range(max_scroll_attempts):
            if self.should_stop():
                return False

            # Check if rank 1 is visible
            frame = self.window_capture.capture()
            if frame is None:
                return False

            _, _, width, height = self.window_capture.window_info
            # Check the rank area (far left of leaderboard)
            # Adjusted position: 30px left and 120px up total
            rank_left = max(0, int(width * 0.005) + 20 - 30)  # Net: 10px left from base position
            rank_top = int(height * 0.35) + 20 + 20 - 120   # Net: 60px up (was 40px down, moved up 120px total)
            rank_width = int(width * 0.02)  # Just wide enough for 1-2 digit rank
            rank_height = int(height * 0.06) # Just one rank entry

            # Ensure region is valid
            if rank_left + rank_width > width or rank_top + rank_height > height:
                self.log(f'  [DEBUG] Invalid rank region bounds')
                return False

            rank_region = frame[rank_top:rank_top+rank_height, rank_left:rank_left+rank_width]

            # Check if region is empty
            if rank_region.size == 0:
                self.log(f'  [DEBUG] Empty rank region')
                continue

            # DEBUG: Save rank region (both color and gray)
            import os
            debug_path = os.path.join(os.path.dirname(__file__), '..', 'debug', f'cb_rank_check_{attempt}.png')
            os.makedirs(os.path.dirname(debug_path), exist_ok=True)
            cv2.imwrite(debug_path, rank_region)

            gray = cv2.cvtColor(rank_region, cv2.COLOR_BGR2GRAY)
            debug_gray_path = os.path.join(os.path.dirname(__file__), '..', 'debug', f'cb_rank_check_{attempt}_gray.png')
            cv2.imwrite(debug_gray_path, gray)

            try:
                # Try with single character PSM mode
                text = pytesseract.image_to_string(gray, config='--psm 7 digits')
                self.log(f'  [DEBUG] Rank check {attempt}: OCR text = "{text.strip()}"')
                # Check if the text contains '1' (could be "1" or "10" etc)
                text_clean = text.strip()
                if text_clean and text_clean[0] == '1':
                    self.log('  Rank 1 found - at top of leaderboard')
                    return True
                # If we see rank 2, scroll up one more time to get rank 1
                if text_clean == '2':
                    self.log('  Rank 2 found - scrolling up once more to rank 1')
                    self._scroll('up', region='leaderboard')
                    self.clicker.natural_delay(0.5)
                    # Check again
                    frame = self.window_capture.capture()
                    if frame:
                        rank_region = frame[rank_top:rank_top+rank_height, rank_left:rank_left+rank_width]
                        if rank_region.size > 0:
                            gray = cv2.cvtColor(rank_region, cv2.COLOR_BGR2GRAY)
                            text = pytesseract.image_to_string(gray, config='--psm 7 digits')
                            self.log(f'  [DEBUG] After final scroll: OCR text = "{text.strip()}"')
                            if text.strip() and text.strip()[0] == '1':
                                self.log('  Rank 1 found - at top of leaderboard')
                                return True
                    # Even if we didn't find 1, we're close enough - return True
                    self.log('  Close to top (was at rank 2) - assuming top')
                    return True
            except Exception as e:
                self.log(f'  [DEBUG] Rank check {attempt}: OCR error = {e}')
                pass

            # Scroll up
            self._scroll('up', region='leaderboard')
            self.clicker.natural_delay(0.3)

        self.log('  Could not find rank 1 after scrolling')
        return False

    def _check_player_damage(self, player_name):
        """
        Check the leaderboard (left side) for the player's current damage.
        Uses OCR to find player name, then template matching to find the red sword,
        then OCR to read damage number to the right of the sword.

        Args:
            player_name: The player's in-game name to search for

        Returns:
            int: The player's damage (0 if not found), or None if OCR unavailable
        """
        if pytesseract is None:
            self.log('  pytesseract not available — cannot check damage')
            return None

        self.log(f'  Checking leaderboard for "{player_name}"...')

        # First, check if we're at the top of the leaderboard (rank 1 visible)
        # If not, scroll to top first
        frame = self.window_capture.capture()
        if frame is None:
            self.log('  Failed to capture screen')
            return None

        _, _, width, height = self.window_capture.window_info
        # Check the rank area (far left of leaderboard)
        # Adjusted position: 30px left and 120px up total
        rank_left = max(0, int(width * 0.005) + 20 - 30)  # Net: 10px left from base position
        rank_top = int(height * 0.35) + 20 + 20 - 120   # Net: 60px up (was 40px down, moved up 120px total)
        rank_width = int(width * 0.02)  # Just wide enough for 1-2 digit rank
        rank_height = int(height * 0.06) # Just one rank entry

        # Ensure region is valid
        if rank_left + rank_width > width or rank_top + rank_height > height:
            self.log('  [DEBUG] Invalid rank region bounds in initial check')
            at_top = False
        else:
            rank_region = frame[rank_top:rank_top+rank_height, rank_left:rank_left+rank_width]

            if rank_region.size == 0:
                at_top = False
            else:
                gray = cv2.cvtColor(rank_region, cv2.COLOR_BGR2GRAY)

                at_top = False
                try:
                    text = pytesseract.image_to_string(gray, config='--psm 7 digits')
                    text_clean = text.strip()
                    if text_clean and text_clean[0] == '1':
                        self.log('  Already at top of leaderboard (rank 1 visible)')
                        at_top = True
                except Exception:
                    pass

        if not at_top:
            self.log('  Not at top of leaderboard - scrolling to rank 1')
            if not self._scroll_to_leaderboard_top():
                self.log('  Failed to scroll to top')

        # Now search through leaderboard, checking current view first then scrolling down
        last_bottom_text = None

        for scroll_attempt in range(CB_MAX_SCROLL_ATTEMPTS + 1):
            if self.should_stop():
                return None

            # Capture current screen
            frame = self.window_capture.capture()
            if frame is None:
                self.log('  Failed to capture screen')
                return None

            # Extract leaderboard region - narrow column where player names appear
            # Names are in a vertical column on the left side, below rank numbers
            _, _, width, height = self.window_capture.window_info
            lb_left = int(width * 0.08) - 10  # Move 10px left to capture full names/sword
            lb_top = int(height * 0.30)   # Skip header/title area
            lb_width = int(width * 0.15)  # 25% narrower (was 0.20, now 0.15)
            lb_height = int(height * 0.60) # Slightly shorter to avoid bottom UI

            leaderboard_region = frame[lb_top:lb_top+lb_height, lb_left:lb_left+lb_width]

            # DEBUG: Save the leaderboard region being scanned for each scroll
            import os
            debug_path = os.path.join(os.path.dirname(__file__), '..', 'debug', f'cb_leaderboard_scan_{scroll_attempt}.png')
            os.makedirs(os.path.dirname(debug_path), exist_ok=True)
            cv2.imwrite(debug_path, leaderboard_region)
            self.log(f'  [DEBUG] Scan {scroll_attempt}: Saved to {debug_path}')

            # Step 1: Use OCR to find player name
            gray = cv2.cvtColor(leaderboard_region, cv2.COLOR_BGR2GRAY)
            try:
                data = pytesseract.image_to_data(
                    gray, config='--psm 6', output_type=pytesseract.Output.DICT
                )

                # DEBUG: Log all OCR text found in each scan
                self.log(f'  [DEBUG] Scan {scroll_attempt} OCR results:')
                for i, txt in enumerate(data['text']):
                    if txt.strip() and len(txt.strip()) >= 4:  # Only log meaningful text
                        self.log(f'    "{txt.strip()}"')

            except Exception as e:
                self.log(f'  OCR error: {e}')
                return None

            # Search for player name in OCR results
            # Strategy: Look for any word from the name (with fuzzy matching for OCR errors)
            # then verify by checking nearby text
            player_found_y = None
            name_words = player_name.lower().split()

            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                if not text or len(text) < 4:
                    continue

                text_lower = text.lower()

                # Check if ANY word from player name is similar to this OCR text
                # Use simple character-based similarity (allows for OCR errors like V->W)
                for word in name_words:
                    if len(word) < 4:
                        continue

                    # Simple fuzzy match: check if at least 75% of characters match
                    matching_chars = sum(1 for a, b in zip(word[:len(text_lower)], text_lower) if a == b)
                    similarity = matching_chars / max(len(word), len(text_lower))

                    if similarity >= 0.5 or word in text_lower:
                        # Found a potential match - collect nearby text
                        y_pos = data['top'][i]
                        nearby_texts = []

                        # Collect text within ±40 pixels vertically
                        for j in range(len(data['text'])):
                            if abs(data['top'][j] - y_pos) <= 40:
                                nearby_texts.append(data['text'][j].strip())

                        # Check if nearby text looks like the player name
                        combined = ' '.join(nearby_texts).lower()

                        # Check if ALL words from player name appear in nearby text (fuzzy)
                        words_found = 0
                        for check_word in name_words:
                            for nearby_word in combined.split():
                                if len(nearby_word) >= 4 and len(check_word) >= 4:
                                    matching = sum(1 for a, b in zip(check_word[:len(nearby_word)], nearby_word) if a == b)
                                    sim = matching / max(len(check_word), len(nearby_word))
                                    if sim >= 0.5:
                                        words_found += 1
                                        break

                        if words_found >= len(name_words):
                            player_found_y = data['top'][i] + data['height'][i] // 2
                            self.log(f'  Found potential match near "{text}" (combined: "{combined}") at Y={player_found_y}')
                            break

                if player_found_y is not None:
                    break

            if player_found_y is not None:
                # Step 2: Look for red sword template near the player's Y position
                # The sword is underneath the name (under first 2 letters), so search
                # from the name Y position down to +80 pixels below
                search_top = max(0, player_found_y - 10)  # Start slightly above name
                search_bottom = min(lb_height, player_found_y + 80)  # Search further down
                search_region = leaderboard_region[search_top:search_bottom, :]

                # DEBUG: Save the sword search region
                sword_search_debug = os.path.join(os.path.dirname(__file__), '..', 'debug', f'cb_sword_search_region.png')
                cv2.imwrite(sword_search_debug, search_region)
                self.log(f'  [DEBUG] Saved sword search region to {sword_search_debug}')

                # Find all red sword icons in this region
                import cv2 as cv2_module
                sword_template = cv2_module.imread(TEMPLATE_CB_RED_SWORD)
                if sword_template is None:
                    self.log('  CBRedSword.png template not found — cannot check damage')
                    return None

                # DEBUG: Save the template being used
                template_debug = os.path.join(os.path.dirname(__file__), '..', 'debug', f'cb_sword_template_loaded.png')
                cv2.imwrite(template_debug, sword_template)

                self.log(f'  [DEBUG] Sword template size: {sword_template.shape}, Search region size: {search_region.shape}')
                self.log(f'  [DEBUG] Template dtype: {sword_template.dtype}, Search region dtype: {search_region.dtype}')
                self.log(f'  [DEBUG] Template path: {TEMPLATE_CB_RED_SWORD}')

                # Try template matching at multiple scales
                best_match = 0
                best_loc = None
                best_scale = 1.0

                for scale in [0.8, 0.9, 1.0, 1.1, 1.2]:
                    scaled_template = cv2_module.resize(sword_template, None, fx=scale, fy=scale)

                    # Skip if template is larger than search region
                    if scaled_template.shape[0] > search_region.shape[0] or scaled_template.shape[1] > search_region.shape[1]:
                        continue

                    result = cv2_module.matchTemplate(search_region, scaled_template, cv2_module.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2_module.minMaxLoc(result)

                    self.log(f'  [DEBUG] Scale {scale}: confidence {max_val:.3f}')

                    if max_val > best_match:
                        best_match = max_val
                        best_loc = max_loc
                        best_scale = scale

                threshold = 0.6  # Lowered threshold
                self.log(f'  [DEBUG] Best match: {best_match:.3f} at scale {best_scale} (threshold: {threshold})')

                if best_match >= threshold:
                    sword_x, sword_y = best_loc
                    sword_width = int(sword_template.shape[1] * best_scale)

                    # Step 3: OCR the area to the right of the sword
                    # Extract region: from sword right edge, extending to capture damage number
                    # Start a bit to the LEFT of sword to capture the full first digit
                    damage_left = sword_x - 15  # Start 15px before sword to catch leading digit
                    damage_top = sword_y - 5   # Start slightly above
                    damage_width = 180  # Wider to ensure we get full number
                    damage_height = sword_template.shape[0] + 10  # Taller

                    # Ensure damage region is within bounds
                    damage_left = max(0, damage_left)
                    if damage_left + damage_width <= search_region.shape[1] and damage_top >= 0:
                        damage_region = search_region[
                            damage_top:damage_top+damage_height,
                            damage_left:damage_left+damage_width
                        ]

                        # Use TextRecognizer for more accurate OCR (same as arena scanner)
                        try:
                            # Capture full frame and extract damage text
                            full_frame = self.window_capture.capture()

                            # Define region relative to full frame
                            region = (
                                lb_left + damage_left,
                                lb_top + search_top + damage_top,
                                damage_width,
                                damage_height
                            )

                            # Use text_recognizer to extract damage number
                            damage_text = self.text_recognizer.extract_text(
                                full_frame, region=region, config='--psm 7'
                            )

                            self.log(f'  [DEBUG] Raw damage OCR: "{damage_text}"')

                            # Parse damage from text
                            damage_match = re.search(r'([\d,]+(?:\.\d+)?[MKmk]?)', damage_text)
                            if damage_match:
                                damage_str = damage_match.group(1)
                                damage = self._parse_damage(damage_str)
                                if damage > 0:
                                    self.log(f'  Found {player_name}: {damage:,} damage')
                                    return damage
                                else:
                                    self.log(f'  Found {player_name} but failed to parse damage: {damage_text}')
                                    return 0
                            else:
                                self.log(f'  Found {player_name} but no damage number detected: {damage_text}')
                                return 0
                        except Exception as e:
                            self.log(f'  Error reading damage: {e}')
                            return 0
                    else:
                        self.log(f'  Found {player_name} but damage region out of bounds')
                        return 0
                else:
                    self.log(f'  Found {player_name} but red sword icon not found nearby')
                    return 0

            # Player not found in this view - scroll down to continue searching
            # This code is INSIDE the for loop, so it continues searching
            self.log(f'  Player not found in current view - scrolling down...')
            self._scroll('down', region='leaderboard')
            # Loop continues to next scroll_attempt

        # If we exit the loop without finding the player, return 0
        self.log(f'  Player "{player_name}" not found after {CB_MAX_SCROLL_ATTEMPTS + 1} scans')
        return 0  # Assume player hasn't fought yet

    def _parse_damage(self, damage_str):
        """
        Parse damage string like "9,234,567" or "9.23M" into integer.

        Args:
            damage_str: Damage string from OCR

        Returns:
            int: Parsed damage value
        """
        damage_str = damage_str.strip().replace(',', '')

        # Handle M/K suffixes (stop at M, don't include anything after it)
        multiplier = 1
        if 'M' in damage_str or 'm' in damage_str:
            multiplier = 1_000_000
            # Find M and take everything before it
            idx = damage_str.lower().find('m')
            damage_str = damage_str[:idx]
        elif 'K' in damage_str or 'k' in damage_str:
            multiplier = 1_000
            # Find K and take everything before it
            idx = damage_str.lower().find('k')
            damage_str = damage_str[:idx]

        try:
            damage = float(damage_str) * multiplier
            return int(damage)
        except ValueError:
            return 0

    def _read_victory_damage(self):
        """
        Read damage dealt from the victory screen using the saved window region.

        Returns:
            int: Damage value, or None if couldn't read
        """
        # Load window region
        windows_file = 'windows.json'
        if not os.path.exists(windows_file):
            self.log('  windows.json not found - cannot read victory damage')
            return None

        with open(windows_file, 'r') as f:
            windows = json.load(f)

        if 'DamgeDealt' not in windows:
            self.log('  DamgeDealt region not found in windows.json')
            return None

        # Get relative coordinates
        rel = windows['DamgeDealt']['relative']
        _, _, win_width, win_height = self.window_capture.window_info

        x = int(win_width * rel['x'])
        y = int(win_height * rel['y'])
        width = int(win_width * rel['width'])
        height = int(win_height * rel['height'])

        # Capture frame and extract region
        frame = self.window_capture.capture()
        if frame is None:
            return None

        # Use TextRecognizer for accurate OCR
        region = (x, y, width, height)
        damage_text = self.text_recognizer.extract_text(frame, region=region, config='--psm 7')

        self.log(f'  [DEBUG] Victory damage OCR: "{damage_text}"')

        # Parse damage (should stop at M as requested)
        damage_match = re.search(r'([\d,]+(?:\.\d+)?[MKmk]?)', damage_text)
        if damage_match:
            damage_str = damage_match.group(1)
            damage = self._parse_damage(damage_str)
            self.log(f'  Victory damage: {damage:,}')
            return damage
        else:
            self.log(f'  Could not parse victory damage from: {damage_text}')
            return None

    def _load_damage_tracker(self):
        """Load today's damage tracking data."""
        tracker_file = 'clan_boss_tracker.json'
        if not os.path.exists(tracker_file):
            return {}

        with open(tracker_file, 'r') as f:
            data = json.load(f)

        # Check if data is from today
        today = datetime.now().strftime('%Y-%m-%d')
        if data.get('date') == today:
            return data.get('difficulties', {})
        else:
            # Old data, start fresh
            return {}

    def _save_damage_tracker(self, difficulties_data):
        """Save today's damage tracking data."""
        tracker_file = 'clan_boss_tracker.json'
        today = datetime.now().strftime('%Y-%m-%d')

        data = {
            'date': today,
            'difficulties': difficulties_data
        }

        with open(tracker_file, 'w') as f:
            json.dump(data, f, indent=2)

        self.log(f'  Damage tracker updated: {tracker_file}')

    def _read_key_refresh_time(self):
        """
        Read the key refresh time from the CB_KeyRefresh region.
        Assumes the refresh UI is already showing (after clicking 0/2 indicator).

        Returns:
            int: Minutes until next key, or None if couldn't read
        """
        # Load window region for key refresh time
        windows_file = 'windows.json'
        if not os.path.exists(windows_file):
            self.log('  windows.json not found - cannot read key refresh time')
            return None

        with open(windows_file, 'r') as f:
            windows = json.load(f)

        if 'CB_KeyRefresh' not in windows:
            self.log('  CB_KeyRefresh region not found in windows.json')
            return None

        # Get relative coordinates
        rel = windows['CB_KeyRefresh']['relative']
        _, _, win_width, win_height = self.window_capture.window_info

        x = int(win_width * rel['x'])
        y = int(win_height * rel['y'])
        width = int(win_width * rel['width'])
        height = int(win_height * rel['height'])

        # Capture frame and extract region
        frame = self.window_capture.capture()
        if frame is None:
            return None

        # Extract refresh region and save debug
        refresh_region = frame[y:y+height, x:x+width]
        debug_path = os.path.join(os.path.dirname(__file__), '..', 'debug', 'cb_key_refresh.png')
        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
        cv2.imwrite(debug_path, refresh_region)

        # Try different OCR approaches
        if pytesseract is None:
            self.log('  pytesseract not available')
            return None

        # Filter for white text only
        # White text should have high values in all BGR channels
        lower_white = np.array([200, 200, 200])  # BGR format
        upper_white = np.array([255, 255, 255])
        white_mask = cv2.inRange(refresh_region, lower_white, upper_white)

        # Apply mask to create white text on black background
        white_only = cv2.bitwise_and(refresh_region, refresh_region, mask=white_mask)

        # Convert to grayscale
        gray = cv2.cvtColor(white_only, cv2.COLOR_BGR2GRAY)

        # Upscale 2x for better OCR
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        # Save filtered debug image
        filtered_debug_path = os.path.join(os.path.dirname(__file__), '..', 'debug', 'cb_key_refresh_filtered.png')
        cv2.imwrite(filtered_debug_path, gray)

        # Try with different configs
        configs = [
            '--psm 7',  # Single line
            '--psm 8',  # Single word
            '--psm 6',  # Block of text
        ]

        best_text = None
        for config in configs:
            try:
                text = pytesseract.image_to_string(gray, config=config).strip()
                self.log(f'  [DEBUG] Key refresh OCR ({config}): "{text}"')

                # Clean common OCR mistakes for time format
                # Replace common misreads before the 'h' or 'm'
                cleaned = text
                # Fix "Sh" → "5h" (S at start often misread 5)
                cleaned = re.sub(r'\bS([hm])', r'5\1', cleaned, flags=re.IGNORECASE)
                # Fix "O" → "0"
                cleaned = re.sub(r'\bO([hm])', r'0\1', cleaned, flags=re.IGNORECASE)
                # Fix "l" or "I" → "1"
                cleaned = re.sub(r'\b[lI]([hm])', r'1\1', cleaned)

                if cleaned != text:
                    self.log(f'  [DEBUG] Cleaned OCR: "{cleaned}"')

                # Check if this looks like a valid time format
                if re.search(r'\d+[hm]', cleaned):
                    best_text = cleaned
                    break
            except Exception as e:
                self.log(f'  [DEBUG] OCR error with {config}: {e}')

        if not best_text:
            self.log('  Could not extract time from refresh region')
            return None

        # Parse time format like "1h 54m" or "54m" or "1h"
        # Be more strict with regex to avoid false matches
        total_minutes = 0

        # Look for pattern like "Xh Ym" or "Xh" or "Ym"
        hour_match = re.search(r'(\d+)\s*h', best_text, re.IGNORECASE)
        if hour_match:
            hours = int(hour_match.group(1))
            # Sanity check - hours should be reasonable (0-24)
            if 0 <= hours <= 24:
                total_minutes += hours * 60
                self.log(f'  [DEBUG] Parsed hours: {hours}')

        min_match = re.search(r'(\d+)\s*m', best_text, re.IGNORECASE)
        if min_match:
            minutes = int(min_match.group(1))
            # Sanity check - minutes should be 0-59
            if 0 <= minutes < 60:
                total_minutes += minutes
                self.log(f'  [DEBUG] Parsed minutes: {minutes}')

        return total_minutes if total_minutes > 0 else None

    def _save_key_refresh_info(self, minutes_until_refresh):
        """Save key refresh information for the daily loop."""
        from datetime import datetime, timedelta

        refresh_time = datetime.now() + timedelta(minutes=minutes_until_refresh)

        refresh_data = {
            'last_checked': datetime.now().isoformat(),
            'minutes_until_refresh': minutes_until_refresh,
            'refresh_time': refresh_time.isoformat()
        }

        refresh_file = 'clan_boss_key_refresh.json'
        with open(refresh_file, 'w') as f:
            json.dump(refresh_data, f, indent=2)

        self.log(f'  Key refresh: {minutes_until_refresh} min ({refresh_time.strftime("%I:%M %p")})')

    def _check_keys_available(self):
        """
        Check if clan boss keys are available.
        Uses the CBNoKeyRegion to look for CBNoKey template.
        If no keys, clicks the 0/2 indicator and reads refresh time.

        Returns:
            bool: True if keys available, False if no keys
        """
        # Load window region for key check
        windows_file = 'windows.json'
        if not os.path.exists(windows_file):
            self.log('  windows.json not found - cannot check keys')
            return True

        with open(windows_file, 'r') as f:
            windows = json.load(f)

        if 'CBNoKeyRegion' not in windows:
            self.log('  CBNoKeyRegion not found in windows.json')
            return True

        # Get relative coordinates
        rel = windows['CBNoKeyRegion']['relative']
        _, _, win_width, win_height = self.window_capture.window_info

        x = int(win_width * rel['x'])
        y = int(win_height * rel['y'])
        width = int(win_width * rel['width'])
        height = int(win_height * rel['height'])

        # Capture frame and extract region
        frame = self.window_capture.capture()
        if frame is None:
            return True

        # Extract the key region
        key_region = frame[y:y+height, x:x+width]

        # Save debug image
        debug_path = os.path.join(os.path.dirname(__file__), '..', 'debug', 'cb_key_check.png')
        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
        cv2.imwrite(debug_path, key_region)

        # Check if CBNoKey template is found in this region
        # We need to check the template against the extracted region
        template = cv2.imread(TEMPLATE_CB_NO_KEY)
        if template is None:
            self.log('  CBNoKey template not found')
            return True

        # Convert to grayscale for matching
        gray_region = cv2.cvtColor(key_region, cv2.COLOR_BGR2GRAY)
        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        # Try matching at different scales
        for scale in [1.0, 0.9, 1.1, 0.8, 1.2]:
            scaled_template = cv2.resize(gray_template, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

            if (scaled_template.shape[0] > gray_region.shape[0] or
                scaled_template.shape[1] > gray_region.shape[1]):
                continue

            result = cv2.matchTemplate(gray_region, scaled_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= 0.7:
                self.log(f'  No keys detected (confidence: {max_val:.3f})')

                # Click on the 0/2 indicator to show refresh time
                self.log('  Clicking 0/2 indicator to check refresh time...')
                # Need to use window position + region position for absolute screen coords
                left, top, _, _ = self.window_capture.window_info
                click_x = left + x + (width // 2)
                click_y = top + y + (height // 2)
                self.clicker.click(click_x, click_y)
                time.sleep(1)  # Wait 1 second for dropdown to appear

                # Read the refresh time
                minutes = self._read_key_refresh_time()
                if minutes:
                    self._save_key_refresh_info(minutes)
                else:
                    self.log('  Could not read key refresh time')

                # Click somewhere else to dismiss the refresh UI
                left, top, width_full, height_full = self.window_capture.window_info
                self.clicker.click(left + int(width_full * 0.5), top + int(height_full * 0.5))
                self.clicker.natural_delay(0.5)

                return False

        self.log('  Keys available')
        return True

    def _navigate_to_stages(self):
        """Navigate from home to Clan Boss difficulty selection: Battle → CB Stages → CB1."""
        self.log('  Navigating to Clan Boss stages...')

        # Click Battle button
        self.log('  Clicking Battle button...')
        if not self.template_matcher.find_and_click(TEMPLATE_BATTLE, threshold=0.7):
            self.log('  Battle button not found')
            return False

        self.clicker.natural_delay(2.0)

        # Click CB Stages button
        self.log('  Clicking CB Stages button...')
        if not self.template_matcher.find_and_click(TEMPLATE_CB_STAGES, threshold=0.7):
            self.log('  CB Stages button not found')
            return False

        self.clicker.natural_delay(2.0)

        # Click CB1 to enter difficulty selection
        self.log('  Clicking CB1...')
        if not self.template_matcher.find_and_click(TEMPLATE_CB1, threshold=0.7):
            self.log('  CB1 button not found')
            return False

        self.clicker.natural_delay(2.0)
        self.log('  Successfully navigated to difficulty selection')
        return True

    def _navigate_to_home(self):
        """Navigate back to home screen by clicking Back while it's visible."""
        self.log('  Navigating to home...')
        max_attempts = 10

        for attempt in range(max_attempts):
            # Check if Back button is still visible
            found_back, _, _ = self.template_matcher.find_template(TEMPLATE_BACK, threshold=0.7)
            if not found_back:
                self.log('  Back button no longer visible - at home')
                return True

            self.log(f'  Clicking Back ({attempt + 1})...')
            if not self.template_matcher.find_and_click(TEMPLATE_BACK, threshold=0.7):
                self.log('  Back button not found - may already be at home')
                return True

            self.clicker.natural_delay(1.5)

        self.log('  Reached max attempts - assuming at home')
        return True

    def _do_battle(self):
        """
        Click battle button, check if quick battle, wait for battle to complete, read damage.

        Returns:
            int: Damage dealt, or None if battle failed
        """
        self.log('  Clicking PVE Battle button...')

        # Click PVE Battle button
        if not self.template_matcher.find_and_click(TEMPLATE_PVE_BATTLE, threshold=0.7):
            self.log('  PVE Battle button not found')
            return False

        self.clicker.natural_delay(2.0)

        # Check if Quick Battle is enabled (CB_QB_True checkbox)
        is_quick_battle, _, _ = self.template_matcher.find_template(TEMPLATE_CB_QB_TRUE, threshold=0.7)
        if is_quick_battle:
            self.log('  Quick Battle detected (checkbox enabled)')
        else:
            self.log('  Normal battle (checkbox not enabled)')

        # Click Start button
        self.log('  Clicking Start button...')
        if not self.template_matcher.find_and_click(TEMPLATE_START, threshold=0.7):
            self.log('  Start button not found')
            return False

        self.clicker.natural_delay(2.0)

        # Wait for battle to complete (looking for "Battle Complete" template)
        self.log('  Waiting for battle to complete...')
        max_wait_time = 300  # 5 minutes max
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            if self.should_stop():
                return False

            # Check if battle is complete
            found_complete, _, _ = self.template_matcher.find_template(TEMPLATE_BATTLE_COMPLETE, threshold=0.7)
            if found_complete:
                self.log('  Battle complete!')
                self.clicker.natural_delay(1.0)

                # Wait for victory screen to appear
                self.clicker.natural_delay(2.0)

                # Read damage from victory screen
                damage_dealt = self._read_victory_damage()
                if damage_dealt is None:
                    self.log('  Warning: Could not read damage from victory screen')
                    damage_dealt = 0

                # Click Continue button to dismiss victory screen
                self.log('  Clicking Continue button...')
                if not self.template_matcher.find_and_click(TEMPLATE_CONTINUE, threshold=0.7):
                    self.log('  Continue button not found - clicking center')
                    _, _, width, height = self.window_capture.window_info
                    center_x = width // 2
                    center_y = int(height * 0.7)
                    self.clicker.click(center_x, center_y)

                self.clicker.natural_delay(2.0)
                return damage_dealt

            # Wait a bit before checking again
            time.sleep(2)

        self.log('  Battle did not complete within timeout')
        return False

    def run(self):
        """
        Run the Clan Boss sequence with cascading difficulties.
        Navigates from home: Battle → CB Stages → select difficulty → fight.

        Returns:
            dict with 'success' key on success, False on error/abort.
        """
        starting_difficulty = config.CB_DIFFICULTY
        self.log('')
        self.log(f'  --- Clan Boss: Starting at {starting_difficulty} ---')

        try:
            self.window_capture.get_window()

            # Navigate to CB Stages screen
            if not self._navigate_to_stages():
                self.log('  Failed to navigate to CB Stages - aborting')
                return False

            # Check for keys on the stages screen first
            self.log('  Checking for keys on stages screen...')
            if not self._check_keys_available():
                self.log('  No keys available on stages screen - navigating back to home')
                # Click Back while it's still visible (max 10 attempts as safety)
                max_back_clicks = 10
                for i in range(max_back_clicks):
                    found_back, _, _ = self.template_matcher.find_template(TEMPLATE_BACK, threshold=0.7)
                    if not found_back:
                        self.log('  Back button no longer visible - at home')
                        break

                    self.log(f'  Clicking Back ({i+1})...')
                    self.template_matcher.find_and_click(TEMPLATE_BACK, threshold=0.7)
                    self.clicker.natural_delay(1.5)

                return {'success': True, 'reason': 'no_keys_on_stages', 'battles': 0}

            # Get list of difficulties to try (starting from selected, cascading to easier)
            difficulties = config.CB_DIFFICULTIES
            start_index = difficulties.index(starting_difficulty)
            difficulties_to_try = difficulties[start_index:]  # From selected to easiest

            self.log(f'  Will cascade through: {" -> ".join(difficulties_to_try)}')

            total_battles = 0
            max_keys = 2  # Maximum keys available

            # Loop through each difficulty level
            for difficulty in difficulties_to_try:
                if self.should_stop():
                    return False

                if total_battles >= max_keys:
                    self.log(f'  Out of keys ({total_battles}/{max_keys} used)')
                    break

                self.log('')
                self.log(f'  === Attempting {difficulty} ===')

                # Step 1: Find and click the selected difficulty (scroll if needed)
                if not self._find_and_click_difficulty(difficulty):
                    self.log(f'  Failed to find {difficulty} difficulty — skipping')
                    continue

                if self.should_stop():
                    return False

                # Step 1.5: Check if keys are available
                self.clicker.natural_delay(1.0)
                if not self._check_keys_available():
                    self.log('  No keys available - navigating to home')
                    self._navigate_to_home()
                    return {'success': False, 'reason': 'no_keys', 'battles': total_battles}

                # Step 2: Check player's current damage on leaderboard
                self.clicker.natural_delay(1.5)
                player_name = config.CB_PLAYER_NAME
                current_damage = self._check_player_damage(player_name)

                if current_damage is None:
                    self.log('  Cannot check damage without OCR — skipping this difficulty')
                    continue

                # Get damage threshold for this difficulty
                threshold = CB_MAX_DAMAGE_THRESHOLDS.get(difficulty, 0)
                self.log(f'  Current damage: {current_damage:,} / {threshold:,}')

                # Step 3: Battle loop for this difficulty
                while current_damage < threshold and total_battles < max_keys:
                    if self.should_stop():
                        return False

                    damage_needed = threshold - current_damage
                    self.log(f'  Need {damage_needed:,} more damage for max reward')
                    self.log(f'  Keys remaining: {max_keys - total_battles}')

                    # Do battle and get damage dealt
                    battle_damage = self._do_battle()
                    if battle_damage is None:
                        self.log('  Battle failed — aborting')
                        return False

                    total_battles += 1
                    self.log(f'  Battles completed: {total_battles}/{max_keys}')

                    # Add this battle's damage to current total
                    current_damage += battle_damage
                    self.log(f'  Updated damage: {current_damage:,} / {threshold:,}')

                    # Check keys after battle
                    if not self._check_keys_available():
                        self.log('  No keys remaining after battle - clicking Bastion')
                        if self.template_matcher.find_and_click(TEMPLATE_BASTION, threshold=0.7):
                            self.log('  Clicked Bastion - exiting Clan Boss')
                        else:
                            self.log('  Bastion not found - navigating to home')
                            self._navigate_to_home()
                        return {'success': True, 'reason': 'no_keys', 'battles': total_battles}

                    # Check if we met the threshold
                    if current_damage >= threshold:
                        self.log(f'  Max reward threshold reached!')
                        # Click Back button to return to difficulty selection
                        self.log('  Clicking Back button...')
                        if not self.template_matcher.find_and_click(TEMPLATE_BACK, threshold=0.7):
                            self.log('  Back button not found')
                        self.clicker.natural_delay(2.0)
                        break  # Move to next difficulty
                    else:
                        # Threshold not met, check if we have keys to fight again
                        self.log(f'  Threshold not met - checking for more keys')

                        # Click CB1 button to prepare for another battle (or return to selection screen)
                        self.log('  Clicking CB1 button...')
                        if not self.template_matcher.find_and_click(TEMPLATE_CB1, threshold=0.7):
                            self.log('  CB1 button not found')
                            break
                        self.clicker.natural_delay(1.5)

                        # The key check will happen at the start of next loop iteration

                # Check if we reached max reward for this difficulty
                if current_damage >= threshold:
                    self.log(f'  Max reward reached for {difficulty}!')
                    # Continue to next (easier) difficulty
                else:
                    self.log(f'  Did not reach max reward for {difficulty}')
                    # Still continue to try easier difficulties with remaining keys

            self.log('')
            self.log(f'  Clan Boss complete: {total_battles} battles fought')
            return {'success': True, 'battles': total_battles}

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
