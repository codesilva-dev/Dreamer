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
import arena_debug

from config import (
    ARENA_SCAN_DELAY,
    ARENA_SCROLL_DELAY,
    ARENA_SCROLL_DURATION,
    ARENA_MAX_SCROLL_ATTEMPTS,
    ARENA_OCR_REGION,
    ARENA_LIST_REGION,
    ARENA_BATTLE_BUTTON_X,
    FLUID_SCROLL_DRAG_DURATION,
    FLUID_SCROLL_PIXELS,
    FLUID_SCROLL_START_PERCENT,
    FLUID_SCROLL_X_CENTER,
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
        self._snapshot_dir = None

    def _init_snapshot_dir(self):
        """Create a fresh snapshot directory for power templates."""
        snapshot_root = os.path.join(SCRIPT_DIR, 'debug', 'arena_targets')
        # Clean out old snapshots from previous scan
        if os.path.exists(snapshot_root):
            for f in os.listdir(snapshot_root):
                fp = os.path.join(snapshot_root, f)
                if f.endswith('.png'):
                    try:
                        os.remove(fp)
                    except OSError:
                        pass
        else:
            os.makedirs(snapshot_root, exist_ok=True)
        self._snapshot_dir = snapshot_root

    def _cleanup_snapshots(self):
        """Delete all snapshot templates (call when list refreshes)."""
        # DEBUG MODE: Don't delete snapshots so we can inspect them
        pass
        # if self._snapshot_dir and os.path.exists(self._snapshot_dir):
        #     for f in os.listdir(self._snapshot_dir):
        #         fp = os.path.join(self._snapshot_dir, f)
        #         if f.endswith('.png'):
        #             try:
        #                 os.remove(fp)
        #             except OSError:
        #                 pass

    def _init_debug_dir(self):
        """Create a fresh debug directory for this scan session."""
        debug_root = os.path.join(SCRIPT_DIR, 'debug')
        os.makedirs(debug_root, exist_ok=True)
        # Clear previous arena scan debug frames only (not battle click debug or other files)
        arena_scan_prefixes = ['initial_top', 'scroll', 'level_region']
        for f in os.listdir(debug_root):
            fp = os.path.join(debug_root, f)
            if f.endswith('.png') and any(f.startswith(prefix) for prefix in arena_scan_prefixes):
                try:
                    os.remove(fp)
                except OSError:
                    pass
        self._debug_dir = debug_root
        self._debug_counter = 0
        arena_debug.reset()

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

    def _should_save_snapshot(self, opponent):
        """
        Check if opponent meets filter criteria and should have a snapshot saved.

        Uses the same filter logic as arena_sequence_v2 to avoid saving snapshots
        for opponents we won't target.
        """
        from config import (
            ARENA_MAX_OPPONENT_POWER,
            ARENA_MAX_OPPONENT_LEVEL,
            ARENA_OR_POWER,
        )

        power = opponent['power']
        level = opponent.get('level')

        # No filters configured - save all
        if ARENA_MAX_OPPONENT_POWER <= 0 and ARENA_MAX_OPPONENT_LEVEL <= 0 and ARENA_OR_POWER <= 0:
            return True

        # Check primary condition: (power <= max_power AND level <= max_level)
        passes_primary = True
        if ARENA_MAX_OPPONENT_POWER > 0 and power > ARENA_MAX_OPPONENT_POWER:
            passes_primary = False
        if ARENA_MAX_OPPONENT_LEVEL > 0:
            if level is None or level > ARENA_MAX_OPPONENT_LEVEL:
                passes_primary = False

        # Check OR condition: power <= or_power (regardless of level)
        passes_or = ARENA_OR_POWER > 0 and power <= ARENA_OR_POWER

        return passes_primary or passes_or

    def _save_power_snapshot(self, frame, power_value, y_position):
        """
        Save a snapshot of the power region for template matching.

        Crops a region including the team power text AND the battle button
        for reliable template matching during targeting.

        Args:
            frame: Full game window frame
            power_value: int power value (e.g., 220680)
            y_position: Y coordinate of the power text (in frame coordinates)
        """
        if self._snapshot_dir is None:
            return

        frame_height, frame_width = frame.shape[:2]

        # Get the power OCR region bounds
        roi_x, roi_y, roi_w, roi_h = self.get_fluid_ocr_region(frame)

        # Crop a band around the power text Y position
        # Move up by 55%: was -30 to +60, now shift up by ~50px
        # This captures more of the opponent portrait and team area
        y_start = max(0, y_position - 80)
        y_end = min(frame_height, y_position + 10)

        # Extend horizontally to include the battle button on the right
        # Start from 35% into the OCR region (just before where numbers start)
        # to avoid capturing champion level badges on the left side
        # Extend 80px to the right of OCR region to capture battle button
        number_region_start = int(roi_w * 0.35)
        x_start = roi_x + number_region_start
        x_end = min(frame_width, roi_x + roi_w + 80)  # 80px beyond OCR region

        snapshot = frame[y_start:y_end, x_start:x_end].copy()

        # Save with power value as filename
        filename = f"power_{power_value}.png"
        filepath = os.path.join(self._snapshot_dir, filename)
        cv2.imwrite(filepath, snapshot)

    def _save_opponent_debug_snapshot(self, frame, power_value, y_position, opponent_index, label):
        """
        Save a debug snapshot for every opponent to detect duplicates.

        Uses the same cropping as the target snapshot, but saves with
        a descriptive filename including scan label and opponent index.
        """
        if self._debug_dir is None:
            return

        frame_height, frame_width = frame.shape[:2]
        roi_x, roi_y, roi_w, roi_h = self.get_fluid_ocr_region(frame)

        # Same cropping as power snapshot
        y_start = max(0, y_position - 90)  # 100px total height, moved up 5px
        y_end = min(frame_height, y_position + 10)  # 100px total height, moved up 5px
        number_region_start = int(roi_w * 0.35)
        x_start = roi_x + number_region_start - 130  # Moved 130px left
        x_end = min(frame_width, roi_x + roi_w + 50)  # Reduced width by 30px (was +80, now +50)

        snapshot = frame[y_start:y_end, x_start:x_end].copy()

        # Save with descriptive filename: label_oppN_powerValue.png
        # opponent_index is now the global count (0-9), so add 1 for display (1-10)
        filename = f"{label}_opp{opponent_index + 1}_{power_value}.png"
        filepath = os.path.join(self._debug_dir, filename)
        cv2.imwrite(filepath, snapshot)

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

        # Move to start position (instant)
        pyautogui.moveTo(center_x, start_y)
        self.clicker.natural_delay(0.1)
        pyautogui.mouseDown()
        self.clicker.natural_delay(0.1)
        # Drag to end position (with duration for game to register the drag)
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
        Perform a broad, fast scroll UP using pixel-based distance.
        Same distance as _fluid_scroll_down but in reverse direction.
        """
        left, top, width, height = self.get_window_dimensions()
        center_x = left + int(width * FLUID_SCROLL_X_CENTER)
        start_y = top + int(height * FLUID_SCROLL_START_PERCENT) - FLUID_SCROLL_PIXELS
        end_y = start_y + FLUID_SCROLL_PIXELS  # Move down by exact pixel count

        pyautogui.moveTo(center_x, start_y)
        self.clicker.natural_delay(0.05)
        pyautogui.mouseDown()
        self.clicker.natural_delay(0.05)
        pyautogui.moveTo(center_x, end_y, duration=FLUID_SCROLL_DRAG_DURATION)
        self.clicker.natural_delay(4)  # Hold 0.5s longer for scroll up
        pyautogui.mouseUp()
        self.clicker.natural_delay(0.3)

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

        pyautogui.moveTo(fling_x, start_y)
        self.clicker.natural_delay(0.05)
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
        self.clicker.natural_delay(0.5)
        self._fling_to_top()
        self.clicker.natural_delay(1.0)  # Let inertia settle
        self.log(f"    At top (fling)")

    def _fluid_scroll_down(self):
        """
        Perform a broad, fast scroll down using pixel-based distance.

        Scrolls exactly FLUID_SCROLL_PIXELS downward for consistent,
        accurate list traversal. Waits for the list to settle before returning.
        """
        left, top, width, height = self.get_window_dimensions()
        center_x = left + int(width * FLUID_SCROLL_X_CENTER)
        start_y = top + int(height * FLUID_SCROLL_START_PERCENT)
        end_y = start_y - FLUID_SCROLL_PIXELS  # Move up by exact pixel count

        pyautogui.moveTo(center_x, start_y)
        self.clicker.natural_delay(0.05)
        pyautogui.mouseDown()
        self.clicker.natural_delay(0.05)
        pyautogui.moveTo(center_x, end_y, duration=FLUID_SCROLL_DRAG_DURATION)
        # Hold after drag to prevent inertia/drift — longer hold for broader scroll
        self.clicker.natural_delay(0.7)
        pyautogui.mouseUp()

        # Let the list settle so OCR gets a clean frame
        self.clicker.natural_delay(0.5)

    def _scan_and_save_debug(self, label):
        """
        Capture frame, OCR it using the V2 fluid region, save debug image.
        Uses targeted scanning: find "Power" anchors first, then OCR
        tight bands with character whitelist for accuracy.
        Also scans player levels from the left side of the screen.
        """
        frame = self.window_capture.capture()

        # Calibrated scan (gets both power AND level in one pass)
        roi_x, roi_y, roi_w, roi_h = self.get_fluid_ocr_region(frame)
        roi_frame = frame[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w].copy()

        debug_prefix = f'{label}_' if self._debug_dir else ''
        opponents = self.text_recognizer.find_team_powers_calibrated(
            roi_frame,
            full_frame=frame,
            roi_offset=(roi_x, roi_y),
            debug_dir=self._debug_dir,
            debug_prefix=debug_prefix
        )

        # Build opponent list
        visible = []
        for i, opp in enumerate(opponents):
            # Skip invalid entries (should be dicts)
            if not isinstance(opp, dict):
                continue

            # y_position is already in full frame coordinates (from calibrated OCR)
            y_pos = opp['y_position'] or (roi_y + i * 100 + 50)
            is_available = self.check_battle_available(frame, y_pos)

            opponent = {
                'power': opp['power'],
                'level': opp['level'],
                'y_position': y_pos,
                'available': is_available,
                'raw_text': opp.get('power_text', ''),
            }
            visible.append(opponent)

            # Save power snapshot for template matching during targeting
            # Only save snapshots for opponents that match our filter criteria
            if is_available and opp.get('y_position') is not None:
                if self._should_save_snapshot(opponent):
                    self._save_power_snapshot(frame, opp['power'], y_pos)

            # Also save debug snapshot for EVERY opponent to detect duplicates
            if self._debug_dir and opp.get('y_position') is not None:
                self._save_opponent_debug_snapshot(frame, opp['power'], y_pos, i, label)

        self._save_debug_frame(frame, visible, label=label)
        return visible

    def _capture_scroll_snapshot(self):
        """Capture a snapshot of the current scroll position for bottom detection."""
        frame = self.window_capture.capture()
        height, width = frame.shape[:2]

        # Capture the middle 60% of the screen height (where opponents are visible)
        y1 = int(height * 0.20)
        y2 = int(height * 0.80)
        x1 = int(width * 0.05)
        x2 = int(width * 0.95)

        return frame[y1:y2, x1:x2].copy()

    def _is_at_bottom(self, previous_snapshot):
        """
        Check if we've reached the bottom of the list by comparing the current
        visible area with the previous scroll position.

        Returns True if the screen hasn't scrolled (we're at the bottom).
        """
        if previous_snapshot is None:
            return False

        current_snapshot = self._capture_scroll_snapshot()

        # Template match to see if the visible area is the same
        result = cv2.matchTemplate(current_snapshot, previous_snapshot, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        # High match score (>0.85) means the screen didn't scroll - we're at bottom
        is_bottom = max_val > 0.85
        if is_bottom:
            self.log(f"      ! Bottom detected (scroll match: {max_val:.3f})")

        return is_bottom

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

        # Initialize debug frame saving and snapshot directory
        self._init_debug_dir()
        self._init_snapshot_dir()
        self.log(f"    Debug frames → {self._debug_dir}")

        known_opponent_templates = []  # List of (filename, opponent_dict) tuples
        all_opponents = []

        def _is_duplicate_template(new_snapshot_path):
            """
            Check if this opponent snapshot matches any previously saved opponent.
            Uses template matching to detect duplicates even if OCR reads differ.

            Returns: True if duplicate, False if new opponent
            """
            if not os.path.exists(new_snapshot_path):
                return False

            new_img = cv2.imread(new_snapshot_path)
            if new_img is None:
                return False

            # Compare against all known opponent templates
            for known_path, _ in known_opponent_templates:
                if not os.path.exists(known_path):
                    continue

                known_img = cv2.imread(known_path)
                if known_img is None:
                    continue

                # For same-sized images, use direct comparison instead of template matching
                # (template matching requires template < search image)
                if new_img.shape == known_img.shape:
                    # Calculate mean absolute difference (normalized to 0-1 range)
                    diff = cv2.absdiff(new_img, known_img)
                    mean_diff = diff.mean() / 255.0  # Normalize to 0-1
                    similarity = 1.0 - mean_diff

                    # Log high similarity for debugging (regardless of power value in filename)
                    if similarity >= 0.90:
                        new_name = new_snapshot_path.split(os.sep)[-1]
                        known_name = known_path.split(os.sep)[-1]
                        self.log(f"      [DUP] {new_name} vs {known_name}: {similarity:.3f}")

                    # 90% threshold - catches duplicates with animations, glows, OCR misreads
                    # Same opponent with different visual states typically 90-95% similar
                    # Different opponents (different teams) typically <85% similar
                    if similarity >= 0.92:
                        self.log(f"        → DUPLICATE!")
                        return True
                    continue

                # For different sizes, skip (shouldn't happen with our snapshots)
                if new_img.shape != known_img.shape:
                    continue

                # Calculate similarity using normalized correlation
                result = cv2.matchTemplate(new_img, known_img, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)

                # 92% threshold for template matching too
                if max_val >= 0.92:
                    self.log(f"      [DUP] Template match: {max_val:.3f}")
                    return True

            return False

        def _merge_new(opponents_list, label):
            """Add new opponents to the master list using template matching."""
            new_count = 0
            for idx, opp in enumerate(opponents_list):
                # Build snapshot filename (matches what we saved)
                snapshot_filename = f"{label}_opp{idx + 1}_{opp['power']}.png"
                snapshot_path = os.path.join(self._debug_dir, snapshot_filename)

                # Check if this is a duplicate using template matching
                if _is_duplicate_template(snapshot_path):
                    # Skip this opponent - it's a duplicate
                    continue

                # New opponent - add to list and save template reference
                known_opponent_templates.append((snapshot_path, opp))
                all_opponents.append(opp)
                new_count += 1

            return new_count

        # Phase 1: Capture what's visible at the top
        initial = self._scan_and_save_debug('initial_top')

        if initial:
            power_list = ', '.join(f"{o['power']:,}" for o in initial)
            avail = sum(1 for o in initial if o['available'])
            self.log(f"    Visible: {len(initial)} opponents ({avail} avail) — {power_list}")

        new_at_top = _merge_new(initial, 'initial_top')
        self.log(f"      + {new_at_top} snatched at top")

        # Phase 2: Broad scroll down, OCR after settle, repeat
        consecutive_empty = 0       # Counts scans that returned nothing (OCR failure)
        max_scrolls = ARENA_MAX_SCROLL_ATTEMPTS + 2
        previous_snapshot = None

        for scroll_num in range(max_scrolls):
            # Capture snapshot before scrolling
            previous_snapshot = self._capture_scroll_snapshot()

            self._fluid_scroll_down()

            # Scan current position (even if at bottom, might get better OCR)
            visible = self._scan_and_save_debug(f'scroll{scroll_num + 1}')

            # Check if we're at the bottom (screen didn't move after scroll)
            at_bottom = self._is_at_bottom(previous_snapshot)

            if at_bottom:
                # Still process this scan - it might have better OCR for last opponent
                self.log(f"  [V2] Bottom of list reached (no scroll movement)")
                if visible:
                    consecutive_empty = 0
                    new_count = _merge_new(visible, f'scroll{scroll_num + 1}')
                    if new_count > 0:
                        self.log(f"      + {new_count} new at bottom ({len(visible)} visible)")
                break

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
                new_count = _merge_new(visible, f'scroll{scroll_num + 1}')

                if new_count > 0:
                    self.log(f"      + {new_count} new after scroll {scroll_num + 1} "
                             f"({len(visible)} visible)")
                else:
                    self.log(f"      All duplicates after scroll {scroll_num + 1}")

        # Add scan_index to preserve original scan order for debugging
        for idx, opp in enumerate(all_opponents):
            opp['scan_index'] = idx

        # Sort weakest first for battle order
        all_opponents.sort(key=lambda x: x['power'])

        available = sum(1 for o in all_opponents if o['available'])
        self.log(f"  ✓ Scan complete: Found {len(all_opponents)} opponents ({available} available)")

        return all_opponents
