"""
Arena Scanner V2 — Vision-based opponent list scanning.

Builds a flat opponent list by scrolling and OCR-ing the full visible area.
No scroll position tracking — just power values + availability, deduplicated.
"""

import cv2
import numpy as np
import os
import time
import pyautogui
from natural_click import NaturalClick

from config import (
    ARENA_SCAN_DELAY,
    ARENA_SCROLL_DELAY,
    ARENA_SCROLL_DURATION,
    ARENA_MAX_SCROLL_ATTEMPTS,
    ARENA_OCR_REGION,
    ARENA_LIST_REGION,
    ARENA_BATTLE_BUTTON_X,
    FLUID_SCROLL_DRAG_DURATION,
    FLUID_SCROLL_REGION,
    FLUID_OCR_REGION,
    FLUID_LEVEL_REGION,
    SCRIPT_DIR,
)


class ArenaListScanner:
    """
    Scans the arena opponent list by freely scrolling and reading.

    Strategy: scan full visible area at each position, scroll down,
    repeat until only duplicates are seen. No position tracking needed.
    """

    def __init__(self, window_capture, text_recognizer, log_func=None):
        self.window_capture = window_capture
        self.text_recognizer = text_recognizer
        self.log = log_func or print
        self.clicker = NaturalClick()
        self._debug_dir = None
        self._debug_counter = 0

    def _init_debug_dir(self):
        """Create a fresh debug directory for this scan session."""
        debug_root = os.path.join(SCRIPT_DIR, 'debug')
        os.makedirs(debug_root, exist_ok=True)
        # Clear previous debug frames
        for f in os.listdir(debug_root):
            fp = os.path.join(debug_root, f)
            if f.endswith('.png'):
                try:
                    os.remove(fp)
                except OSError:
                    pass
        self._debug_dir = debug_root
        self._debug_counter = 0

    def _save_debug_frame(self, frame, powers, label='capture'):
        """
        Save an annotated debug frame showing the OCR region and detected powers.

        Draws:
        - Green rectangle around the OCR region
        - Red dots + text labels at each detected power's Y position
        - Frame counter and label in top-left corner
        """
        if self._debug_dir is None:
            return

        self._debug_counter += 1
        annotated = frame.copy()
        height, width = annotated.shape[:2]

        # Draw V2 fluid OCR region rectangle
        roi_x, roi_y, roi_w, roi_h = self.get_fluid_ocr_region(frame)
        cv2.rectangle(annotated, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h),
                      (0, 255, 0), 2)

        # Draw detected powers
        for p in powers:
            y_pos = p.get('y_position', 0)
            power_val = p.get('power', 0)
            available = p.get('available', True)

            # Red dot at the detected Y position, within OCR region X
            dot_x = roi_x + roi_w // 2
            color = (0, 200, 0) if available else (0, 0, 200)
            cv2.circle(annotated, (dot_x, y_pos), 6, color, -1)

            # Power text label
            label_text = f"{power_val:,}"
            cv2.putText(annotated, label_text, (dot_x + 12, y_pos + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # Frame counter label
        counter_text = f"#{self._debug_counter} [{label}]"
        cv2.putText(annotated, counter_text, (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        filename = f"{self._debug_counter:03d}_{label}.png"
        filepath = os.path.join(self._debug_dir, filename)
        cv2.imwrite(filepath, annotated)

    def get_window_dimensions(self):
        """Get current window rect (left, top, width, height)."""
        if not self.window_capture.window_info:
            self.window_capture.get_window()
        return self.window_capture.window_info

    # ── List-change detection (2nd opponent snapshot) ────────────────

    # Snapshot region: 2nd opponent row, left side only (portrait + name).
    # Row 1 is at ~28-44% Y, Row 2 is at ~44-58% Y.
    # Using row 2 avoids notification banners that appear over row 1.
    _SNAPSHOT_Y_START = 0.44
    _SNAPSHOT_Y_END = 0.58
    _SNAPSHOT_X_START = 0.05
    _SNAPSHOT_X_END = 0.40

    def snapshot_first_opponent(self):
        """
        Capture a portrait snapshot of the 2nd opponent row for
        list-change detection.

        Uses the 2nd row instead of the 1st to avoid game notification
        banners ("Daily Challenge complete", quest popups, etc.) that
        appear over the top of the list and would corrupt the snapshot.

        Must be called when the list is scrolled to the top.
        """
        frame = self.window_capture.capture()
        height, width = frame.shape[:2]

        y1 = int(height * self._SNAPSHOT_Y_START)
        y2 = int(height * self._SNAPSHOT_Y_END)
        x1 = int(width * self._SNAPSHOT_X_START)
        x2 = int(width * self._SNAPSHOT_X_END)

        self._opponent_snapshot = frame[y1:y2, x1:x2].copy()
        self._snapshot_check_count = 0
        self.log(f"    Snapshot 2nd opponent ({x2-x1}x{y2-y1}px)")

        # Save reference for debugging
        snapshot_dir = os.path.join(SCRIPT_DIR, 'logs', 'snapshots')
        os.makedirs(snapshot_dir, exist_ok=True)
        cv2.imwrite(os.path.join(snapshot_dir, 'reference.png'),
                    self._opponent_snapshot)

    def is_list_unchanged(self):
        """
        Check if the 2nd opponent still matches the stored snapshot.

        Uses template matching on the portrait/name region of the 2nd
        opponent row. This region is below the notification banner zone,
        so popups don't cause false positives.

        Must be called when the list is scrolled to the top.

        Returns:
            True if the list appears unchanged, False if it has refreshed.
        """
        if not hasattr(self, '_opponent_snapshot') or self._opponent_snapshot is None:
            return True  # No snapshot to compare against

        frame = self.window_capture.capture()
        height, width = frame.shape[:2]

        y1 = int(height * self._SNAPSHOT_Y_START)
        y2 = int(height * self._SNAPSHOT_Y_END)
        x1 = int(width * self._SNAPSHOT_X_START)
        x2 = int(width * self._SNAPSHOT_X_END)

        current = frame[y1:y2, x1:x2].copy()

        result = cv2.matchTemplate(current, self._opponent_snapshot,
                                   cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        self._snapshot_check_count += 1
        self.log(f"    List check #{self._snapshot_check_count}: match={max_val:.4f}")

        # Save comparison image for debugging
        snapshot_dir = os.path.join(SCRIPT_DIR, 'logs', 'snapshots')
        os.makedirs(snapshot_dir, exist_ok=True)
        cv2.imwrite(os.path.join(snapshot_dir, f'check_{self._snapshot_check_count}.png'),
                    current)

        # Same opponent: ~0.75+ (may be subdued/grayed after defeat)
        # Different opponent (list refresh): ~0.3-0.5
        unchanged = max_val > 0.60
        if not unchanged:
            self.log(f"    ! List changed (match: {max_val:.4f})")
        return unchanged

    def get_ocr_region(self, frame):
        """Calculate full OCR region in pixels from config percentages."""
        height, width = frame.shape[:2]
        x = int(width * ARENA_OCR_REGION['x_start'])
        y = int(height * ARENA_OCR_REGION['y_start'])
        w = int(width * ARENA_OCR_REGION['width'])
        h = int(height * ARENA_OCR_REGION['height'])
        return (x, y, w, h)

    def get_fluid_ocr_region(self, frame):
        """Calculate V2 fluid OCR region — taller than v1 to catch all opponents."""
        height, width = frame.shape[:2]
        x = int(width * FLUID_OCR_REGION['x_start'])
        y = int(height * FLUID_OCR_REGION['y_start'])
        w = int(width * FLUID_OCR_REGION['width'])
        h = int(height * FLUID_OCR_REGION['height'])
        return (x, y, w, h)

    def get_fluid_level_region(self, frame):
        """Calculate V2 fluid level region for player level scanning."""
        height, width = frame.shape[:2]
        x = int(width * FLUID_LEVEL_REGION['x_start'])
        y = int(height * FLUID_LEVEL_REGION['y_start'])
        w = int(width * FLUID_LEVEL_REGION['width'])
        h = int(height * FLUID_LEVEL_REGION['height'])
        return (x, y, w, h)

    def _match_level_to_power(self, power_entry, levels, power_roi_y, level_roi_y):
        """
        Match a level reading to a power reading by Y proximity.

        Both ROIs share the same y_start/height, so y_position values
        are directly comparable. Uses 60px tolerance.

        Returns:
            int level if matched, None otherwise.
        """
        if not levels:
            return None

        power_frame_y = (power_entry['y_position'] or 0) + power_roi_y

        best_match = None
        best_distance = float('inf')

        for lvl in levels:
            level_frame_y = (lvl['y_position'] or 0) + level_roi_y
            distance = abs(power_frame_y - level_frame_y)

            if distance < best_distance and distance < 60:
                best_distance = distance
                best_match = lvl['level']

        return best_match

    def check_battle_available(self, frame, y_position):
        """
        Check if the Battle button is orange (available) or gray (defeated).

        Samples HSV color in the battle button region. Returns True if the
        button is orange (available to fight).
        """
        height, width = frame.shape[:2]
        button_x = int(width * ARENA_BATTLE_BUTTON_X)

        sample_width = 40
        x_start = max(0, button_x - sample_width // 2)
        x_end = min(width, button_x + sample_width // 2)
        y_start = max(0, y_position - 80)
        y_end = min(height, y_position + 20)

        sample_region = frame[y_start:y_end, x_start:x_end].copy()
        if sample_region.size == 0:
            return True  # Assume available if region empty

        hsv = cv2.cvtColor(sample_region, cv2.COLOR_BGR2HSV)
        orange_mask = (
            (hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 35) &
            (hsv[:, :, 1] > 150)
        )
        orange_ratio = np.sum(orange_mask) / (sample_region.shape[0] * sample_region.shape[1])
        return orange_ratio > 0.15

    def scan_visible(self):
        """
        OCR the full visible area and return opponent data.

        Returns:
            List of dicts: [{power, y_position, available, raw_text}]
        """
        self.clicker.natural_delay(ARENA_SCAN_DELAY)

        frame = self.window_capture.capture()
        roi_x, roi_y, roi_w, roi_h = self.get_ocr_region(frame)
        roi_frame = frame[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w].copy()

        powers = self.text_recognizer.find_all_team_powers(roi_frame)

        visible = []
        for i, p in enumerate(powers):
            y_pos = (p['y_position'] or (i * 100 + 50)) + roi_y
            is_available = self.check_battle_available(frame, y_pos)

            visible.append({
                'power': p['power'],
                'y_position': y_pos,
                'available': is_available,
                'raw_text': p.get('raw_text', ''),
            })

        if visible:
            power_list = ', '.join(f"{o['power']:,}" for o in visible)
            avail = sum(1 for o in visible if o['available'])
            self.log(f"    Visible: {len(visible)} opponents ({avail} avail) — {power_list}")

        return visible

    def scroll_down(self):
        """Scroll the opponent list down one step."""
        self._scroll('down')

    def scroll_up(self):
        """Scroll the opponent list up one step."""
        self._scroll('up')

    def _scroll(self, direction):
        """Perform a single scroll gesture."""
        left, top, width, height = self.get_window_dimensions()
        center_x = left + int(width * ARENA_LIST_REGION['x_center'])

        if direction == 'down':
            start_y = top + int(height * ARENA_LIST_REGION['y_end'])
            end_y = top + int(height * ARENA_LIST_REGION['y_start'])
        else:
            start_y = top + int(height * ARENA_LIST_REGION['y_start'])
            end_y = top + int(height * ARENA_LIST_REGION['y_end'])

        pyautogui.moveTo(center_x, start_y, duration=0.2)
        self.clicker.natural_delay(0.1)
        pyautogui.mouseDown()
        self.clicker.natural_delay(0.1)
        pyautogui.moveTo(center_x, end_y, duration=ARENA_SCROLL_DURATION)
        # Hold after drag to prevent inertia/fling
        self.clicker.natural_delay(0.5)
        pyautogui.mouseUp()

        self.clicker.natural_delay(ARENA_SCROLL_DELAY)

    def _quick_scan_powers(self):
        """Quick OCR to get the set of currently visible power values."""
        self.clicker.natural_delay(ARENA_SCAN_DELAY)
        frame = self.window_capture.capture()
        roi_x, roi_y, roi_w, roi_h = self.get_fluid_ocr_region(frame)
        roi_frame = frame[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w].copy()
        powers = self.text_recognizer.find_team_powers_hsv(roi_frame)
        return set(p['power'] for p in powers)

    def scroll_to_top(self):
        """Scroll up until the list stops changing (already at top)."""
        last_powers = self._quick_scan_powers()

        for i in range(ARENA_MAX_SCROLL_ATTEMPTS):
            self.scroll_up()
            current_powers = self._quick_scan_powers()

            if current_powers and current_powers == last_powers:
                self.log(f"    At top of list (confirmed after {i + 1} scroll(s))")
                return

            last_powers = current_powers

        self.log(f"    At top of list (max scrolls reached)")

    def run_full_scan(self):
        """
        Scan the full opponent list by scrolling and OCR-ing.

        Returns:
            Sorted list of unique opponents [{power, available}],
            weakest first.
        """
        self.log("")
        self.log("  [V2] Scanning opponent list...")

        known_powers = set()
        all_opponents = []

        def _is_known(power):
            """Fuzzy match: ±500 tolerance for minor OCR digit errors.
            Catches variants like 300,750 vs 300,500 (same opponent, digit
            misread) without merging genuinely different opponents."""
            for kp in known_powers:
                if abs(power - kp) <= 500:
                    return True
            return False

        # Scan at current position (should be top of list)
        visible = self.scan_visible()
        for opp in visible:
            if not _is_known(opp['power']):
                known_powers.add(opp['power'])
                all_opponents.append(opp)

        new_at_top = len(all_opponents)
        self.log(f"      + {new_at_top} new at top")

        consecutive_all_dupes = 0
        consecutive_empty = 0
        max_empty_retries = 2

        for scroll_num in range(ARENA_MAX_SCROLL_ATTEMPTS):
            self.scroll_down()
            visible = self.scan_visible()

            # Handle empty scans (OCR failure)
            if len(visible) == 0:
                consecutive_empty += 1
                self.log(f"      ! OCR empty (attempt {consecutive_empty}/{max_empty_retries})")
                if consecutive_empty <= max_empty_retries:
                    # Retry: scroll back and forward
                    self.scroll_up()
                    continue
                else:
                    self.log(f"      ! Giving up after {max_empty_retries} OCR failures")
                    consecutive_empty = 0
                    continue
            else:
                consecutive_empty = 0

            # Deduplicate with fuzzy matching
            new_count = 0
            for opp in visible:
                if not _is_known(opp['power']):
                    known_powers.add(opp['power'])
                    all_opponents.append(opp)
                    new_count += 1

            if new_count > 0:
                consecutive_all_dupes = 0
                self.log(f"      + {new_count} new after scroll {scroll_num + 1}")
            else:
                consecutive_all_dupes += 1
                self.log(f"      All duplicates (x{consecutive_all_dupes})")

                if consecutive_all_dupes >= 2:
                    self.log(f"  [V2] End of list reached")
                    break

        # Sort weakest first
        all_opponents.sort(key=lambda x: x['power'])

        available = sum(1 for o in all_opponents if o['available'])
        self.log(f"  [V2] Scan complete: {len(all_opponents)} total, {available} available")

        if all_opponents:
            powers_str = ', '.join(f"{o['power']:,}" for o in all_opponents)
            self.log(f"    Sorted: {powers_str}")

        return all_opponents

    # ── Fluid scan (broad scroll + settle + OCR) ───────────────────

    def _fluid_scroll_up(self):
        """
        Perform a broad, fast scroll UP using FLUID_SCROLL_REGION.
        Same distance as _fluid_scroll_down but in reverse direction.
        """
        left, top, width, height = self.get_window_dimensions()
        center_x = left + int(width * FLUID_SCROLL_REGION['x_center'])
        # Reverse: start at top of region, drag down to bottom
        start_y = top + int(height * FLUID_SCROLL_REGION['y_start'])
        end_y = top + int(height * FLUID_SCROLL_REGION['y_end'])

        pyautogui.moveTo(center_x, start_y, duration=0.15)
        time.sleep(0.05)
        pyautogui.mouseDown()
        time.sleep(0.05)
        pyautogui.moveTo(center_x, end_y, duration=FLUID_SCROLL_DRAG_DURATION)
        time.sleep(0.7)
        pyautogui.mouseUp()
        time.sleep(0.3)

    def _fling_to_top(self):
        """
        Fast downward drag to fling the list to the top.

        Releases the mouse mid-drag while the cursor is still moving,
        so the game sees high velocity at release and applies inertia.
        Cursor continues past the release point to maintain momentum.
        """
        left, top, width, height = self.get_window_dimensions()
        fling_x = left + int(width * 0.513)
        start_y = top + int(height * 0.367)
        release_y = top + int(height * 0.80)
        overshoot_y = top + int(height * 1.10)

        pyautogui.moveTo(fling_x, start_y, duration=0.1)
        time.sleep(0.05)
        pyautogui.mouseDown()
        # 0.25s — fast enough for strong flick, slow enough for game to track
        pyautogui.moveTo(fling_x, release_y, duration=0.25)
        pyautogui.mouseUp()


    def scroll_to_top_fast(self):
        """
        Fling to top of the list. Does two fast flings to ensure
        the list reaches the top even from a deep scroll position.
        """
        self._fling_to_top()
        time.sleep(0.5)
        self._fling_to_top()
        time.sleep(1.0)  # Let inertia settle
        self.log(f"    At top (fling)")

    def _fluid_scroll_down(self):
        """
        Perform a broad, fast scroll down using FLUID_SCROLL_REGION.

        Covers ~45% of window height per scroll vs ~20% for the regular
        scroll. Waits for the list to settle before returning.
        """
        left, top, width, height = self.get_window_dimensions()
        center_x = left + int(width * FLUID_SCROLL_REGION['x_center'])
        start_y = top + int(height * FLUID_SCROLL_REGION['y_end'])
        end_y = top + int(height * FLUID_SCROLL_REGION['y_start'])

        pyautogui.moveTo(center_x, start_y, duration=0.15)
        time.sleep(0.05)
        pyautogui.mouseDown()
        time.sleep(0.05)
        pyautogui.moveTo(center_x, end_y, duration=FLUID_SCROLL_DRAG_DURATION)
        # Hold after drag to prevent inertia/drift — longer hold for broader scroll
        time.sleep(0.7)
        pyautogui.mouseUp()

        # Let the list settle so OCR gets a clean frame
        time.sleep(0.5)

    def _scan_and_save_debug(self, label):
        """
        Capture frame, OCR it using the V2 fluid region, save debug image.
        Uses targeted scanning: find "Power" anchors first, then OCR
        tight bands with character whitelist for accuracy.
        Also scans player levels from the left side of the screen.
        """
        frame = self.window_capture.capture()

        # Power scan (right side)
        roi_x, roi_y, roi_w, roi_h = self.get_fluid_ocr_region(frame)
        roi_frame = frame[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w].copy()

        debug_prefix = f'{label}_' if self._debug_dir else ''
        powers = self.text_recognizer.find_team_powers_hsv(
            roi_frame, debug_dir=self._debug_dir, debug_prefix=debug_prefix
        )

        # Level scan (left side)
        lvl_x, lvl_y, lvl_w, lvl_h = self.get_fluid_level_region(frame)
        lvl_frame = frame[lvl_y:lvl_y + lvl_h, lvl_x:lvl_x + lvl_w].copy()

        # Pass power Y positions as hints for the level scanner.
        # Power Y is relative to the power ROI; level Y is relative to the
        # level ROI. Both ROIs share the same y_start and height, so the
        # Y positions map directly.
        power_y_hints = [p['y_position'] for p in powers if p.get('y_position') is not None]

        levels = self.text_recognizer.find_player_levels_hsv(
            lvl_frame, debug_dir=self._debug_dir, debug_prefix=debug_prefix,
            power_y_hints=power_y_hints
        )

        # Save level region crop for debugging
        if self._debug_dir:
            cv2.imwrite(os.path.join(self._debug_dir, f'level_region_{label}.png'),
                        lvl_frame)

        # Build opponent list with level matching
        visible = []
        for i, p in enumerate(powers):
            y_pos = (p['y_position'] or (i * 100 + 50)) + roi_y
            is_available = self.check_battle_available(frame, y_pos)
            matched_level = self._match_level_to_power(p, levels, roi_y, lvl_y)

            visible.append({
                'power': p['power'],
                'level': matched_level,
                'y_position': y_pos,
                'available': is_available,
                'raw_text': p.get('raw_text', ''),
            })

        self._save_debug_frame(frame, visible, label=label)
        return visible

    def run_fluid_scan(self):
        """
        Scan the full opponent list using broad scrolls.

        Uses wider scroll gestures (FLUID_SCROLL_REGION) to cover the
        list in fewer scrolls — typically 2-3 instead of 5-6. OCR runs
        only after each scroll settles for clean, reliable reads.

        Debug frames are saved to the debug/ folder for visual verification.

        Returns:
            Sorted list of unique opponents [{power, available}],
            weakest first.
        """
        self.log("")
        self.log("  [V2] Fluid scanning opponent list...")

        # Initialize debug frame saving
        self._init_debug_dir()
        self.log(f"    Debug frames → {self._debug_dir}")

        known_powers = set()
        all_opponents = []

        def _is_known(power):
            """Fuzzy match: ±500 tolerance for minor OCR digit errors.
            Catches variants like 300,750 vs 300,500 (same opponent, digit
            misread) without merging genuinely different opponents."""
            for kp in known_powers:
                if abs(power - kp) <= 500:
                    return True
            return False

        def _merge_new(opponents_list):
            """Add new opponents to the master list, return count of new."""
            new_count = 0
            for opp in opponents_list:
                if not _is_known(opp['power']):
                    known_powers.add(opp['power'])
                    all_opponents.append(opp)
                    new_count += 1
            return new_count

        # Phase 1: Capture what's visible at the top
        initial = self._scan_and_save_debug('initial_top')

        if initial:
            power_list = ', '.join(f"{o['power']:,}" for o in initial)
            avail = sum(1 for o in initial if o['available'])
            self.log(f"    Visible: {len(initial)} opponents ({avail} avail) — {power_list}")

        new_at_top = _merge_new(initial)
        self.log(f"      + {new_at_top} snatched at top")

        # Phase 2: Broad scroll down, OCR after settle, repeat
        consecutive_dupes = 0       # Only counts scans that SAW opponents but found no new
        consecutive_empty = 0       # Counts scans that returned nothing (OCR failure)
        max_scrolls = ARENA_MAX_SCROLL_ATTEMPTS + 2

        for scroll_num in range(max_scrolls):
            self._fluid_scroll_down()

            visible = self._scan_and_save_debug(f'scroll{scroll_num + 1}')

            if not visible:
                consecutive_empty += 1
                self.log(f"      ! OCR empty after scroll {scroll_num + 1} "
                         f"(x{consecutive_empty})")
                # Don't count empty as "duplicate" — it's an OCR failure.
                # But if we get 3 empties in a row, something is wrong.
                if consecutive_empty >= 3:
                    self.log(f"  [V2] Too many empty scans, stopping")
                    break
                continue
            else:
                consecutive_empty = 0
                new_count = _merge_new(visible)

                if new_count > 0:
                    consecutive_dupes = 0
                    self.log(f"      + {new_count} new after scroll {scroll_num + 1} "
                             f"({len(visible)} visible)")
                else:
                    consecutive_dupes += 1
                    self.log(f"      All duplicates (x{consecutive_dupes})")

            if consecutive_dupes >= 1:
                self.log(f"  [V2] End of list reached")
                break

        # Sort weakest first
        all_opponents.sort(key=lambda x: x['power'])

        available = sum(1 for o in all_opponents if o['available'])
        self.log(f"  [V2] Fluid scan complete: {len(all_opponents)} total, {available} available")

        if all_opponents:
            powers_str = ', '.join(
                f"{o['power']:,}" + (f" (L{o['level']})" if o.get('level') else "")
                for o in all_opponents
            )
            self.log(f"    Sorted: {powers_str}")

        return all_opponents
