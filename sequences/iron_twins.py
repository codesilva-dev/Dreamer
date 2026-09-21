"""
Iron Twins — Navigate to Iron Twins dungeon and fight a specific stage.

Navigation: Home → Battle → Dungeons → Iron Twins → select stage → fight.

Stage selection strategy:
    - Use OCR to find "Stage N" text on the stage list screen.
    - Scroll through the list until the target stage text is visible.
    - Find the PVE battle button at the same Y height and click it.
    - If no battle button at that Y, the stage is locked.
"""

import os
import re
import cv2
import pyautogui

try:
    import pytesseract
except ImportError:
    pytesseract = None

from natural_click import NaturalClick
from macro_recorder import MacroRecorder, MacroPlayer

from config import (
    TEMPLATE_BATTLE, TEMPLATE_DUNGEONS, TEMPLATE_IRON_TWINS,
    TEMPLATE_IT_ICON, TEMPLATE_PVE_BATTLE, TEMPLATE_BACK,
    IRON_TWINS_SCROLL_REGION, IRON_TWINS_SCROLL_DELAY,
    IRON_TWINS_MAX_SCROLL_ATTEMPTS,
    CLICK_DELAY, SCRIPT_DIR,
)
import config


class IronTwinsSequence:
    """Navigate to Iron Twins and fight the configured stage."""

    # Threshold for matching boss icons (identical across all stages)
    ICON_THRESHOLD = 0.8
    # Threshold for matching battle buttons (lower to tolerate minor differences)
    BUTTON_THRESHOLD = 0.7
    # Max Y distance (pixels) for a battle button to be considered
    # "at the same height" as a boss icon
    Y_MATCH_TOLERANCE = 40

    def __init__(self, window_capture, template_matcher, log_func=None,
                 stop_check=None, gear_macro=None):
        self.window_capture = window_capture
        self.template_matcher = template_matcher
        self.log = log_func or print
        self.stop_check = stop_check
        self.gear_macro = gear_macro
        self.clicker = NaturalClick()

    def should_stop(self):
        return self.stop_check and self.stop_check()

    # ── Scrolling helpers ────────────────────────────────────────────

    def _scroll(self, direction):
        """Perform a single scroll gesture in the stage list."""
        left, top, width, height = self.window_capture.window_info
        center_x = left + int(width * IRON_TWINS_SCROLL_REGION['x_center'])

        if direction == 'down':
            start_y = top + int(height * IRON_TWINS_SCROLL_REGION['y_end'])
            end_y = top + int(height * IRON_TWINS_SCROLL_REGION['y_start'])
        else:
            start_y = top + int(height * IRON_TWINS_SCROLL_REGION['y_start'])
            end_y = top + int(height * IRON_TWINS_SCROLL_REGION['y_end'])

        pyautogui.moveTo(center_x, start_y, duration=0.2)
        self.clicker.natural_delay(0.1)
        pyautogui.mouseDown()
        self.clicker.natural_delay(0.1)
        pyautogui.moveTo(center_x, end_y, duration=0.6)
        self.clicker.natural_delay(0.5)
        pyautogui.mouseUp()

        self.clicker.natural_delay(IRON_TWINS_SCROLL_DELAY)

    def _scroll_to_edge(self, direction):
        """Scroll repeatedly until the list stops moving (hit the edge)."""
        last_ys = None

        for i in range(IRON_TWINS_MAX_SCROLL_ATTEMPTS):
            if self.should_stop():
                return

            self._scroll(direction)

            icons = self.template_matcher.find_all_templates(
                TEMPLATE_IT_ICON, threshold=self.ICON_THRESHOLD
            )
            current_ys = tuple(y for _, y in icons)

            if last_ys is not None and current_ys == last_ys:
                self.log(f'  Reached {direction} edge after {i + 1} scroll(s)')
                return

            last_ys = current_ys

        self.log(f'  Max scrolls reached scrolling {direction}')

    # ── Debug helpers ────────────────────────────────────────────────

    DEBUG_DIR = os.path.join(SCRIPT_DIR, 'debug')

    def _save_debug(self, filename, frame, stage_pos=None, buttons=None,
                    target_stage=None):
        """
        Annotate and save a debug screenshot.

        Args:
            filename: Name for the debug image (e.g. 'scroll_0').
            frame: The captured frame (numpy array) to annotate.
            stage_pos: (x, y) position of the found stage text.
            buttons: List of (x, y) button positions to draw.
            target_stage: The stage we're looking for.
        """
        os.makedirs(self.DEBUG_DIR, exist_ok=True)
        annotated = frame.copy()

        if stage_pos:
            sx, sy = stage_pos
            cv2.circle(annotated, (sx, sy), 20, (0, 255, 0), 3)
            cv2.putText(annotated, f'Stage {target_stage}', (sx + 25, sy + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        if buttons:
            for bx, by in buttons:
                cv2.circle(annotated, (bx, by), 15, (0, 0, 255), 3)
                cv2.putText(annotated, 'BTN', (bx - 20, by - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        info = f'target=Stage {target_stage}' if target_stage else ''
        cv2.putText(annotated, info, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        path = os.path.join(self.DEBUG_DIR, f'it_{filename}.png')
        cv2.imwrite(path, annotated)
        self.log(f'  [debug] Saved {path}')

    # ── OCR stage finder ──────────────────────────────────────────────

    def _find_stage_text(self, frame, target_stage):
        """
        Use OCR to find "Stage N" text in the current frame.

        Args:
            frame: Captured game frame (numpy array).
            target_stage: Stage number to search for (e.g. 13).

        Returns:
            (x, y) center position of the stage text, or None if not found.
        """
        if pytesseract is None:
            self.log('  pytesseract not available')
            return None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Use psm 11 (sparse text) to find all text elements with positions
        data = pytesseract.image_to_data(
            gray, config='--psm 11', output_type=pytesseract.Output.DICT
        )

        # Build word groups by line (block_num, par_num, line_num)
        # to reconstruct "Stage 13" from adjacent words
        lines = {}
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            if not text:
                continue
            key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
            if key not in lines:
                lines[key] = []
            lines[key].append({
                'text': text,
                'x': data['left'][i],
                'y': data['top'][i],
                'w': data['width'][i],
                'h': data['height'][i],
                'conf': int(data['conf'][i]),
            })

        target_str = str(target_stage)

        # Search for "Stage N" as adjacent words on the same line
        for key, words in lines.items():
            line_text = ' '.join(w['text'] for w in words)

            # Check for "Stage N" pattern
            match = re.search(
                rf'\bStage\s+{target_str}\b', line_text, re.IGNORECASE
            )
            if match:
                # Find the word containing the stage number for position
                for w in words:
                    if w['text'] == target_str or w['text'].lower() == f'stage':
                        continue
                # Use the first word's position as anchor
                first_word = words[0]
                cx = first_word['x'] + first_word['w'] // 2
                cy = first_word['y'] + first_word['h'] // 2
                self.log(f'  OCR found "Stage {target_stage}" at Y={cy}')
                return (cx, cy)

        # Fallback: look for individual word matches
        # Sometimes OCR reads "Stage13" as one word or "Stage" and "13" separately
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            if not text:
                continue

            # Check for combined "Stage13" or "Stage 13"
            if re.match(rf'^Stage\s*{target_str}$', text, re.IGNORECASE):
                cx = data['left'][i] + data['width'][i] // 2
                cy = data['top'][i] + data['height'][i] // 2
                self.log(f'  OCR found "{text}" at Y={cy}')
                return (cx, cy)

        return None

    # ── Stage selection ──────────────────────────────────────────────

    def _select_stage(self, target_stage):
        """
        Scroll through the stage list and use OCR to find "Stage N" text.
        Once found, locate the PVE battle button at the same Y height
        and click it.

        Returns:
            True if the target button was clicked, False otherwise.
        """
        # Scroll to top first for a consistent starting point
        self.log('  Scrolling to top of stage list...')
        self._scroll_to_edge('up')

        if self.should_stop():
            return False

        for scroll_attempt in range(IRON_TWINS_MAX_SCROLL_ATTEMPTS + 1):
            if self.should_stop():
                return False

            # Capture frame
            frame = self.window_capture.capture()

            # Try to find "Stage N" text via OCR
            stage_pos = self._find_stage_text(frame, target_stage)

            if stage_pos:
                sx, sy = stage_pos
                self.log(f'  Found Stage {target_stage} text at Y={sy}')

                # Find all battle buttons on screen
                buttons = self.template_matcher.find_all_templates(
                    TEMPLATE_PVE_BATTLE, threshold=self.BUTTON_THRESHOLD
                )

                # Save debug with stage position and buttons
                self._save_debug(f'scroll_{scroll_attempt}_found', frame,
                                 stage_pos=stage_pos, buttons=buttons,
                                 target_stage=target_stage)

                # Find the button closest to the stage text's Y
                best_button = None
                best_dist = float('inf')
                for bx, by in buttons:
                    dist = abs(by - sy)
                    if dist < best_dist:
                        best_dist = dist
                        best_button = (bx, by)

                if best_button and best_dist <= self.Y_MATCH_TOLERANCE:
                    bx, by = best_button
                    self.log(f'  Clicking battle button at ({bx}, {by}) '
                             f'(Y offset: {best_dist}px)')
                    self.template_matcher.click_at_offset(
                        bx, by, wait_after=CLICK_DELAY
                    )
                    return True
                else:
                    self.log(f'  Stage {target_stage} is locked — '
                             f'no battle button near Y={sy}')
                    return False

            # Save debug screenshot showing what we see
            self._save_debug(f'scroll_{scroll_attempt}', frame,
                             target_stage=target_stage)

            self.log(f'  Stage {target_stage} not found on screen — scrolling down')
            self._scroll('down')

        self.log(f'  Stage {target_stage} not found after scrolling')
        return False

    # ── Gear-up macro ──────────────────────────────────────────────

    def _run_gear_macro(self):
        """
        Play the gear-up macro if one is configured.

        Returns:
            True if macro ran or none was configured, False on error.
        """
        if not self.gear_macro:
            return True

        self.log(f'  Running gear macro: {self.gear_macro}')

        macro_data = MacroRecorder.load_macro(self.gear_macro)
        if not macro_data:
            self.log(f'  Failed to load macro "{self.gear_macro}" — skipping')
            return True

        click_count = len(macro_data.get('clicks', []))
        if click_count == 0:
            self.log(f'  Macro "{self.gear_macro}" has no clicks — skipping')
            return True

        self.log(f'  Playing {click_count} click(s)...')
        player = MacroPlayer(self.window_capture, log_func=self.log)
        player.play(macro_data, loop=False)
        self.log(f'  Gear macro complete')
        return True

    # ── Main run ─────────────────────────────────────────────────────

    def run(self):
        """
        Run the full Iron Twins sequence.

        Returns:
            True if completed successfully, False on error/abort.
        """
        target_stage = config.IRON_TWINS_STAGE
        self.log('')
        self.log(f'  --- Iron Twins: Stage {target_stage} ---')
        if self.gear_macro:
            self.log(f'  Gear macro: {self.gear_macro}')

        try:
            self.window_capture.get_window()

            # Step 1: Navigate Home → Battle
            self.log('  Looking for Battle button...')
            found, _, _ = self.template_matcher.find_template(TEMPLATE_BATTLE)
            if not found:
                self.log('  Battle button not found — aborting')
                return False

            self.template_matcher.find_and_click(TEMPLATE_BATTLE, wait_after=CLICK_DELAY)
            self.log('  Clicked Battle')

            if self.should_stop():
                return False

            # Step 2: Click Dungeons
            self.clicker.natural_delay(1.0)
            self.log('  Looking for Dungeons...')
            found, _, _ = self.template_matcher.find_template(TEMPLATE_DUNGEONS)
            if not found:
                self.log('  Dungeons not found — aborting')
                return False

            self.template_matcher.find_and_click(TEMPLATE_DUNGEONS, wait_after=CLICK_DELAY)
            self.log('  Clicked Dungeons')

            if self.should_stop():
                return False

            # Step 3: Click Iron Twins
            self.clicker.natural_delay(1.0)
            self.log('  Looking for Iron Twins...')
            found, _, _ = self.template_matcher.find_template(TEMPLATE_IRON_TWINS)
            if not found:
                self.log('  Iron Twins not found — aborting')
                return False

            self.template_matcher.find_and_click(TEMPLATE_IRON_TWINS, wait_after=CLICK_DELAY)
            self.log('  Clicked Iron Twins')

            if self.should_stop():
                return False

            # Step 4: Select the target stage
            self.clicker.natural_delay(1.5)
            if not self._select_stage(target_stage):
                self.log('  Failed to select stage — aborting')
                return False

            self.log(f'  Stage {target_stage} selected')

            if self.should_stop():
                return False

            # Step 5: Run gear-up macro (if configured)
            self.clicker.natural_delay(1.0)
            self._run_gear_macro()

            return True

        except Exception as e:
            import traceback
            self.log(f'  ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')
            return False
