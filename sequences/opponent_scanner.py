"""
Opponent Scanner - Handles scanning and tracking Arena opponents
Focused on acquiring opponent data with scroll position tracking
"""

import time
import pyautogui
import cv2
import numpy as np

from config import (
    ARENA_SCAN_DELAY,
    ARENA_SCROLL_DELAY,
    ARENA_SCROLL_DURATION,
    ARENA_MAX_SCROLL_ATTEMPTS,
    ARENA_OCR_REGION,
    ARENA_OCR_BOTTOM_BAND,
    ARENA_LIST_REGION,
    ARENA_BATTLE_BUTTON_X,
)


class OpponentScanner:
    """
    Scans and tracks Arena opponents with scroll position tracking.
    
    Key features:
    - Tracks which scroll position each opponent was found at
    - Doesn't count the final "end of list" scroll
    - Returns opponent list sorted by scroll position for efficient traversal
    """
    
    def __init__(self, window_capture, text_recognizer, log_func=None):
        self.window_capture = window_capture
        self.text_recognizer = text_recognizer
        self.log = log_func or print
        
        # Scanning state
        self.opponents = []  # List of {'power', 'y_position', 'scroll_position'}
        self.scroll_count = 0  # Current scroll position (0 = top)
        self.max_scroll_reached = 0  # Highest scroll position with valid opponents
        
        # Deduplication
        self.known_powers = set()
        
    def reset(self):
        """Reset scanner state for a new scan"""
        self.opponents = []
        self.scroll_count = 0
        self.max_scroll_reached = 0
        self.known_powers = set()
    
    def get_window_dimensions(self):
        """Get current window dimensions"""
        if not self.window_capture.window_info:
            self.window_capture.get_window()
        return self.window_capture.window_info
    
    def get_ocr_region(self, frame, use_bottom_band=False):
        """Calculate OCR region in pixels based on frame size"""
        height, width = frame.shape[:2]
        region = ARENA_OCR_BOTTOM_BAND if use_bottom_band else ARENA_OCR_REGION
        
        x = int(width * region['x_start'])
        y = int(height * region['y_start'])
        w = int(width * region['width'])
        h = int(height * region['height'])
        
        return (x, y, w, h)
    
    def _show_overlay_mode(self, mode):
        """Switch overlay to show active scan region"""
        try:
            from debug_overlay import show_full_scan_mode, show_bottom_band_mode
            if self.window_capture.window_info:
                if mode == 'full':
                    show_full_scan_mode(self.window_capture.window_info, ARENA_OCR_REGION)
                elif mode == 'bottom':
                    show_bottom_band_mode(self.window_capture.window_info, ARENA_OCR_BOTTOM_BAND)
        except Exception:
            pass
    
    def _hide_overlay(self):
        """Hide the debug overlay"""
        try:
            from debug_overlay import hide_overlay
            hide_overlay()
        except Exception:
            pass
    
    def _flash_detection(self, y_position, power_value):
        """Flash green indicator on overlay when a power is detected"""
        try:
            from debug_overlay import flash_power_detection
            if self.window_capture.window_info:
                flash_power_detection(self.window_capture.window_info, y_position, power_value, duration=1.5)
        except Exception:
            pass
    
    def check_battle_available(self, frame, y_position):
        """
        Check if the Battle button is available (orange) or defeated (gray).
        Uses pixel color sampling in the Battle button region.
        
        This is SEPARATE from OCR - keeps text recognition generic and reusable.
        
        Args:
            frame: The captured screenshot (BGR format)
            y_position: Y position where Team Power text was found
            
        Returns:
            True if Battle button is orange (available), False if gray (defeated)
        """
        height, width = frame.shape[:2]
        
        # Battle button X position (right side of screen)
        button_x = int(width * ARENA_BATTLE_BUTTON_X)
        
        # Sample a vertical stripe at the button X position
        # This is more robust than a small square because Y estimates can be off
        # Sample from y-80 to y+20 to cover the whole opponent row area
        sample_width = 40  # Horizontal sampling width
        x_start = max(0, button_x - sample_width // 2)
        x_end = min(width, button_x + sample_width // 2)
        
        # Vertical range: cover most of the opponent row height
        y_start = max(0, y_position - 80)
        y_end = min(height, y_position + 20)
        
        # Extract the sample region
        sample_region = frame[y_start:y_end, x_start:x_end]
        
        if sample_region.size == 0:
            self.log(f"      Warning: Empty sample region for availability check")
            return True  # Assume available if we can't check
        
        # Convert to HSV for color analysis
        hsv = cv2.cvtColor(sample_region, cv2.COLOR_BGR2HSV)
        
        # Orange Battle button: Hue ~15-25, high saturation (>150)
        # Victory badge: Hue ~80-100 (greenish from wings), varying saturation
        # Gray elements: Low saturation
        
        # Count pixels that are orange (not just average)
        # Orange hue: 10-35, high saturation: >150
        orange_mask = (
            (hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 35) &  # Orange hue
            (hsv[:, :, 1] > 150)  # High saturation
        )
        orange_pixel_count = np.sum(orange_mask)
        total_pixels = sample_region.shape[0] * sample_region.shape[1]
        orange_ratio = orange_pixel_count / total_pixels if total_pixels > 0 else 0
        
        # If more than 15% of the sample is orange, the button is available
        is_available = orange_ratio > 0.15
        
        return is_available
    
    def scroll_list(self, direction='down'):
        """
        Scroll the opponent list
        
        Args:
            direction: 'down' to see more opponents, 'up' to go back
            
        Returns:
            The new scroll position
        """
        left, top, width, height = self.get_window_dimensions()
        center_x = left + int(width * ARENA_LIST_REGION['x_center'])
        
        if direction == 'down':
            start_y = top + int(height * ARENA_LIST_REGION['y_end'])
            end_y = top + int(height * ARENA_LIST_REGION['y_start'])
        else:
            start_y = top + int(height * ARENA_LIST_REGION['y_start'])
            end_y = top + int(height * ARENA_LIST_REGION['y_end'])
        
        pyautogui.moveTo(center_x, start_y, duration=0.2)
        time.sleep(0.1)
        pyautogui.mouseDown()
        time.sleep(0.1)
        pyautogui.moveTo(center_x, end_y, duration=ARENA_SCROLL_DURATION)
        # Hold mouse down after scroll to stop inertia (phone-like scrolling)
        time.sleep(0.3)
        pyautogui.mouseUp()
        
        time.sleep(ARENA_SCROLL_DELAY)
        
        if direction == 'down':
            self.scroll_count += 1
        else:
            self.scroll_count = max(0, self.scroll_count - 1)
        
        return self.scroll_count
    
    def scroll_to_position(self, target_position):
        """
        Scroll to a specific position in the list
        
        Args:
            target_position: The scroll position to navigate to (0 = top)
            
        Returns:
            True if navigation successful
        """
        current = self.scroll_count
        
        if target_position == current:
            return True
        
        if target_position < current:
            # Need to scroll up
            scrolls_needed = current - target_position
            self.log(f"  Scrolling UP {scrolls_needed} time(s) to position {target_position}...")
            for _ in range(scrolls_needed):
                self.scroll_list(direction='up')
        else:
            # Need to scroll down
            scrolls_needed = target_position - current
            self.log(f"  Scrolling DOWN {scrolls_needed} time(s) to position {target_position}...")
            for _ in range(scrolls_needed):
                self.scroll_list(direction='down')
        
        return self.scroll_count == target_position
    
    def scan_visible_opponents(self, use_bottom_band=False):
        """
        Scan currently visible opponents and extract team power values
        
        Returns:
            List of opponent dicts: {'power', 'y_position', 'scroll_position'}
        """
        time.sleep(ARENA_SCAN_DELAY)
        
        frame = self.window_capture.capture()
        height, width = frame.shape[:2]
        
        roi_x, roi_y, roi_w, roi_h = self.get_ocr_region(frame, use_bottom_band=use_bottom_band)
        roi_frame = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        powers = self.text_recognizer.find_all_team_powers(roi_frame)
        
        visible = []
        for i, p in enumerate(powers):
            y_pos = (p['y_position'] or (i * 100 + 50)) + roi_y
            is_available = self.check_battle_available(frame, y_pos)
            
            opponent = {
                'power': p['power'],
                'y_position': y_pos,
                'scroll_position': self.scroll_count,
                'raw_text': p.get('raw_text', ''),
                'available': is_available
            }
            visible.append(opponent)
            self._flash_detection(y_pos, p['power'])
        
        # Compact log: scroll position, count, powers
        if visible:
            available = sum(1 for o in visible if o['available'])
            power_list = ', '.join(f"{o['power']:,}" for o in visible)
            self.log(f"    Scroll {self.scroll_count}: {len(visible)} found ({available} avail) - {power_list}")
        
        return visible
    
    def add_opponents_with_dedup(self, new_opponents):
        """
        Add newly scanned opponents, filtering duplicates
        
        Returns:
            Number of new opponents added
        """
        added_count = 0
        new_powers = []
        
        for opp in new_opponents:
            power = opp['power']
            
            if power not in self.known_powers:
                self.known_powers.add(power)
                self.opponents.append(opp)
                added_count += 1
                new_powers.append(f"{power:,}")
        
        if added_count > 0:
            self.max_scroll_reached = self.scroll_count
            self.log(f"      + {added_count} new: {', '.join(new_powers)}")
        
        return added_count
    
    def run_full_scan(self):
        """
        Run a complete scan of all opponents
        
        Strategy:
        1. Full scan at top
        2. Scroll + bottom band scan loop
        3. Stop when same opponent detected twice (end of list)
        4. DON'T count the final scroll that hit end of list
        
        Returns:
            List of all opponents found with scroll positions
        """
        self.log("")
        self.log("  Scanning opponent list...")
        
        self.reset()
        
        # Step 1: Full scan at top (scroll_position = 0)
        self._show_overlay_mode('full')
        visible = self.scan_visible_opponents(use_bottom_band=False)
        self.add_opponents_with_dedup(visible)
        
        # Track last scan for end-of-list detection
        last_bottom_powers = set()
        consecutive_empty_scans = 0  # Track OCR failures
        
        # Switch to bottom band mode
        self._show_overlay_mode('bottom')
        
        while self.scroll_count < ARENA_MAX_SCROLL_ATTEMPTS:
            # Scroll down
            self.scroll_list(direction='down')
            
            # Scan bottom band
            visible = self.scan_visible_opponents(use_bottom_band=True)
            current_powers = set(opp['power'] for opp in visible)
            
            # Handle empty scans (OCR failures) - don't treat as end of list
            if len(visible) == 0:
                consecutive_empty_scans += 1
                self.log(f"      ! OCR returned nothing (attempt {consecutive_empty_scans})")
                if consecutive_empty_scans >= 2:
                    self.log(f"      ! Multiple OCR failures - continuing anyway")
                    consecutive_empty_scans = 0
                continue  # Try next scroll without end-detection
            else:
                consecutive_empty_scans = 0
            
            # Check for end of list (same opponent as last scan)
            if last_bottom_powers and current_powers == last_bottom_powers:
                self.log(f"  ✓ End of list reached at scroll {self.scroll_count}")
                self.scroll_count -= 1
                break
            
            # Add any new opponents
            added = self.add_opponents_with_dedup(visible)
            last_bottom_powers = current_powers
            
            # If no NEW opponents (all duplicates), do one confirmation scroll
            if added == 0:
                self.scroll_list(direction='down')
                
                visible = self.scan_visible_opponents(use_bottom_band=True)
                confirm_powers = set(opp['power'] for opp in visible)
                
                if confirm_powers == last_bottom_powers:
                    self.log(f"  ✓ End of list confirmed")
                    self.scroll_count -= 2
                    break
                else:
                    self.scroll_count -= 1
                    self.add_opponents_with_dedup(visible)
                    last_bottom_powers = confirm_powers
        
        # Ensure scroll_count doesn't go negative
        self.scroll_count = max(0, self.scroll_count)
        self.max_scroll_reached = self.scroll_count
        
        # Hide the overlay now that scanning is complete
        self._hide_overlay()
        
        # CRITICAL: Return to top of list for accurate position tracking
        # The confirmation scroll logic can desync tracked vs actual position,
        # so we scroll up MAX_SCROLL_ATTEMPTS times to guarantee we're at top
        self.log(f"  Returning to top of list...")
        for _ in range(ARENA_MAX_SCROLL_ATTEMPTS):
            self.scroll_list(direction='up')
        # Now we're guaranteed to be at top, reset count
        self.scroll_count = 0
        
        available_count = sum(1 for o in self.opponents if o.get('available', True))
        self.log(f"  Scan complete: {len(self.opponents)} total, {available_count} available, max_scroll={self.max_scroll_reached}")
        
        return self.opponents
    
    def get_opponents_sorted_by_power(self, weakest_first=True):
        """Get opponents sorted by power"""
        return sorted(
            self.opponents,
            key=lambda x: x['power'],
            reverse=not weakest_first
        )
    
    def verify_opponent_at_position(self, target_power):
        """
        Verify a specific opponent is visible at current scroll position
        
        Returns:
            True if opponent with target_power is visible, False otherwise
        """
        frame = self.window_capture.capture()
        roi_x, roi_y, roi_w, roi_h = self.get_ocr_region(frame)
        roi_frame = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        powers = self.text_recognizer.find_all_team_powers(roi_frame)
        
        for p in powers:
            if p['power'] == target_power:
                return True
        
        return False
    
    def find_opponent_y_position(self, target_power):
        """
        Find the Y position of an opponent with given power
        
        Returns:
            Y position if found, None otherwise
        """
        frame = self.window_capture.capture()
        roi_x, roi_y, roi_w, roi_h = self.get_ocr_region(frame)
        roi_frame = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        powers = self.text_recognizer.find_all_team_powers(roi_frame)
        
        for p in powers:
            if p['power'] == target_power:
                return (p['y_position'] or 0) + roi_y
        
        return None
    
    def get_current_visible_powers(self):
        """
        Quick scan to get currently visible powers (for verification)
        
        Returns:
            Set of power values currently visible
        """
        time.sleep(ARENA_SCAN_DELAY)
        frame = self.window_capture.capture()
        roi_x, roi_y, roi_w, roi_h = self.get_ocr_region(frame)
        roi_frame = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        powers = self.text_recognizer.find_all_team_powers(roi_frame)
        return set(p['power'] for p in powers)
