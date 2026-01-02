"""
Text Recognition Module for Dreamer
Uses pytesseract OCR to read text from game screenshots
"""

import cv2
import numpy as np
import re

try:
    import pytesseract
except ImportError:
    pytesseract = None
    print("Warning: pytesseract not installed. Text recognition will not work.")


class TextRecognizer:
    def __init__(self, window_capture, log_func=None, debug=True):
        self.window_capture = window_capture
        self.log = log_func or print
        self.debug = debug  # Enable verbose logging
        
        if pytesseract is None:
            raise ImportError("pytesseract is required for text recognition. Install with: pip install pytesseract")
        
        self.log("[TextRecognizer] Initialized")
    
    def _debug_log(self, message):
        """Log only if debug mode is enabled"""
        if self.debug:
            self.log(f"  [OCR] {message}")
    
    def preprocess_for_ocr(self, image, method='default'):
        """Preprocess image to improve OCR accuracy"""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        if method == 'default':
            # No scaling - use original resolution for cleaner OCR
            return gray
            
        elif method == 'threshold':
            # Binary threshold for light text on dark background
            upscaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            _, thresh = cv2.threshold(upscaled, 150, 255, cv2.THRESH_BINARY)
            return thresh
            
        elif method == 'adaptive':
            # Adaptive threshold
            upscaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            thresh = cv2.adaptiveThreshold(upscaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY, 11, 2)
            return thresh
            
        elif method == 'inverted':
            # Invert for dark text on light background
            upscaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            inverted = cv2.bitwise_not(upscaled)
            return inverted
            
        elif method == 'clahe':
            # Contrast Limited Adaptive Histogram Equalization
            upscaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(upscaled)
            return enhanced
        
        return gray
    
    def extract_text(self, image, region=None, config='--psm 6'):
        """
        Extract text from image or region of image
        
        Args:
            image: BGR image (numpy array)
            region: Optional (x, y, w, h) tuple to crop before OCR
            config: Tesseract config string
            
        Returns:
            Extracted text string
        """
        self._debug_log(f"extract_text called with config='{config}'")
        
        if region:
            x, y, w, h = region
            self._debug_log(f"Cropping to region: x={x}, y={y}, w={w}, h={h}")
            image = image[y:y+h, x:x+w]
        
        self._debug_log(f"Image shape: {image.shape}")
        
        # Try multiple preprocessing methods
        methods = ['default', 'threshold', 'clahe']
        
        for method in methods:
            self._debug_log(f"Trying preprocessing method: {method}")
            processed = self.preprocess_for_ocr(image, method)
            text = pytesseract.image_to_string(processed, config=config)
            if text.strip():
                self._debug_log(f"SUCCESS with {method}: '{text.strip()[:100]}...'" if len(text.strip()) > 100 else f"SUCCESS with {method}: '{text.strip()}'")
                return text.strip()
            else:
                self._debug_log(f"No text found with {method}")
        
        self._debug_log("No text extracted from any method")
        return ""
    
    def extract_text_with_positions(self, image, region=None, config='--psm 6'):
        """
        Extract text with bounding box positions
        
        Returns:
            List of dicts with 'text', 'x', 'y', 'w', 'h', 'confidence'
        """
        if region:
            x_offset, y_offset, w, h = region
            image = image[y_offset:y_offset+h, x_offset:x_offset+w]
        else:
            x_offset, y_offset = 0, 0
        
        processed = self.preprocess_for_ocr(image, 'default')
        scale_factor = 1  # No scaling in default preprocessing
        
        data = pytesseract.image_to_data(processed, config=config, output_type=pytesseract.Output.DICT)
        
        results = []
        for i, text in enumerate(data['text']):
            if text.strip() and int(data['conf'][i]) > 0:
                results.append({
                    'text': text.strip(),
                    'x': x_offset + data['left'][i] // scale_factor,
                    'y': y_offset + data['top'][i] // scale_factor,
                    'w': data['width'][i] // scale_factor,
                    'h': data['height'][i] // scale_factor,
                    'confidence': int(data['conf'][i])
                })
        
        return results
    
    def find_text(self, image, search_text, case_sensitive=False):
        """
        Find specific text in image and return its position
        
        Returns:
            (x, y, w, h) of found text or None
        """
        results = self.extract_text_with_positions(image)
        
        for result in results:
            text = result['text']
            target = search_text
            
            if not case_sensitive:
                text = text.lower()
                target = target.lower()
            
            if target in text or text in target:
                return (result['x'], result['y'], result['w'], result['h'])
        
        return None
    
    def parse_team_power(self, text):
        """
        Parse team power from text like "Team Power: 8,309" or "14,508"
        
        Returns:
            Integer power value or None
        """
        # Remove commas and look for number patterns
        text = text.replace(',', '').replace('.', '')
        
        # Pattern for "Team Power: XXXXX" or just numbers
        patterns = [
            r'Team\s*Power[:\s]*(\d+)',
            r'Power[:\s]*(\d+)',
            r'(\d{4,6})',  # 4-6 digit numbers (team power range)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    def find_all_team_powers(self, image):
        """
        Find all team power values in the image with their positions
        
        Returns:
            List of dicts with 'power' (int) and 'y_position' (int)
        """
        # Get positioned text data (for Y position lookup)
        results = self.extract_text_with_positions(image, config='--psm 11')
        
        powers = []
        
        # Look for "Team Power:" followed by a number
        # Build text blocks by grouping nearby text
        full_text = self.extract_text(image, config='--psm 6')
        
        # Find all occurrences of team power pattern
        # Allow periods in numbers since OCR sometimes reads commas as periods (e.g., "8.309" instead of "8,309")
        # Make pattern very flexible - OCR often garbles "Team Power:"
        # Match: "Team Power:", "am Power:", "Power:", "Power.", "Power " followed by number
        pattern = r'(?:[Tt]?e?a?m?\s*)?[Pp]ower[:\.\s]+(\d[\d,\.]+)'
        
        matches_found = list(re.finditer(pattern, full_text, re.IGNORECASE))
        
        # Track which Y positions we've already used
        used_y_positions = set()
        
        # Also track found power values to avoid duplicates from fallback
        found_powers = set()
        
        for match in matches_found:
            # Replace both commas and periods, then parse as int
            power_str = match.group(1).replace(',', '').replace('.', '')
            try:
                power = int(power_str)
                
                # Filter out obvious OCR errors - team power should be at least 1000
                if power < 1000:
                    continue
                
                # Try to find the Y position of this power value
                # First, look for the exact power number in positioned results
                y_pos = None
                
                # Method 1: Look for the exact power value in text
                for result in results:
                    result_text = result['text'].replace(',', '').replace('.', '')
                    if power_str in result_text:
                        candidate_y = result['y']
                        if candidate_y not in used_y_positions:
                            y_pos = candidate_y
                            self._debug_log(f"Found Y={y_pos} from exact match '{result['text']}'")
                            break
                
                # Method 2: Look for "Power" text at unused Y positions
                if y_pos is None:
                    power_results = [r for r in results if 'Power' in r['text'] or 'ower' in r['text']]
                    for result in power_results:
                        candidate_y = result['y']
                        if candidate_y not in used_y_positions:
                            y_pos = candidate_y
                            self._debug_log(f"Found Y={y_pos} from 'Power' text '{result['text']}'")
                            break
                
                # Method 3: Estimate Y based on order (assume ~115px spacing between opponents)
                if y_pos is None:
                    estimated_y = len(powers) * 115 + 50
                    y_pos = estimated_y
                    self._debug_log(f"Estimated Y={y_pos} based on order")
                
                if y_pos is not None:
                    used_y_positions.add(y_pos)
                
                found_powers.add(power)
                powers.append({
                    'power': power,
                    'y_position': y_pos,
                    'raw_text': match.group(0)
                })
            except ValueError:
                continue
        
        # FALLBACK: Scan positioned text elements for standalone numbers that look like power values
        # This catches cases where OCR garbles "Team Power:" but correctly reads the number
        for result in results:
            text = result['text'].replace(',', '').replace('.', '')
            # Look for 4-6 digit numbers (typical team power range: 1,000 - 999,999)
            if re.match(r'^\d{4,6}$', text):
                try:
                    power = int(text)
                    # Valid power range and not already found
                    if 1000 <= power <= 999999 and power not in found_powers:
                        y_pos = result['y']
                        # Check we haven't used a nearby Y position (within 20px)
                        too_close = any(abs(y_pos - used_y) < 20 for used_y in used_y_positions)
                        if not too_close:
                            found_powers.add(power)
                            used_y_positions.add(y_pos)
                            powers.append({
                                'power': power,
                                'y_position': y_pos,
                                'raw_text': f'[fallback] {result["text"]}'
                            })
                except ValueError:
                    continue
        
        return powers


class OpponentScanner:
    """
    Scans the Classic Arena opponent list and extracts opponent data
    """
    
    def __init__(self, window_capture, text_recognizer, log_func=None):
        self.window_capture = window_capture
        self.text_recognizer = text_recognizer
        self.log = log_func or print
        self.opponents = []
        self.scroll_position = 0  # Track scroll state
    
    def scan_visible_opponents(self, frame=None):
        """
        Scan currently visible opponents and extract their team power
        
        Returns:
            List of opponent dicts with 'power', 'y_position', 'screen_y'
        """
        if frame is None:
            frame = self.window_capture.capture()
        
        height, width = frame.shape[:2]
        
        # Focus on the right portion where team power is displayed
        # Based on screenshot: team power is in the right-center area
        # Approximately 60-85% from left, 25-90% from top
        roi_x = int(width * 0.55)
        roi_y = int(height * 0.20)
        roi_w = int(width * 0.35)
        roi_h = int(height * 0.70)
        
        roi = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        self.log(f"Scanning region: x={roi_x}, y={roi_y}, w={roi_w}, h={roi_h}")
        
        # Extract all text with positions from this region
        powers = self.text_recognizer.find_all_team_powers(roi)
        
        # Adjust positions back to full frame coordinates
        visible_opponents = []
        for i, p in enumerate(powers):
            opponent = {
                'power': p['power'],
                'y_position': (p['y_position'] or 0) + roi_y,
                'roi_y': p['y_position'],
                'scroll_index': self.scroll_position + i,
                'raw_text': p.get('raw_text', '')
            }
            visible_opponents.append(opponent)
            self.log(f"  Found opponent: Power={p['power']:,}")
        
        return visible_opponents
    
    def estimate_opponent_row_height(self, opponents):
        """Estimate the height of each opponent row based on Y positions"""
        if len(opponents) < 2:
            return 120  # Default estimate
        
        y_positions = sorted([o['y_position'] for o in opponents if o['y_position']])
        if len(y_positions) < 2:
            return 120
        
        # Calculate average distance between opponents
        distances = [y_positions[i+1] - y_positions[i] for i in range(len(y_positions)-1)]
        return int(sum(distances) / len(distances))
    
    def get_battle_button_position(self, opponent_y, frame_width, frame_height):
        """
        Calculate the approximate position of the Battle button for an opponent
        
        Args:
            opponent_y: Y position of the opponent's team power text
            frame_width: Width of the game window
            frame_height: Height of the game window
            
        Returns:
            (x, y) tuple for Battle button center
        """
        # Battle button is on the far right, roughly aligned with each opponent row
        # Based on screenshot analysis:
        # - Button X is approximately 90% from left
        # - Button Y is roughly same as opponent row center
        
        button_x = int(frame_width * 0.90)
        # The team power text is below the champion portraits, 
        # battle button is vertically centered with the row
        # Adjust Y up a bit from the power text position
        button_y = opponent_y - 30  # Approximate adjustment
        
        return (button_x, button_y)
    
    def add_opponents(self, new_opponents):
        """
        Add new opponents to the list, avoiding duplicates
        Uses power + approximate position to identify duplicates
        """
        for new_opp in new_opponents:
            is_duplicate = False
            
            for existing in self.opponents:
                # Consider it a duplicate if same power and similar scroll position
                if existing['power'] == new_opp['power']:
                    # Could be same opponent - check if positions are close
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                self.opponents.append(new_opp)
                self.log(f"  Added new opponent: Power={new_opp['power']:,}")
            else:
                self.log(f"  Skipped duplicate: Power={new_opp['power']:,}")
    
    def get_sorted_opponents(self, ascending=True):
        """
        Return opponents sorted by team power
        
        Args:
            ascending: If True, weakest first (easier targets)
        """
        return sorted(self.opponents, key=lambda x: x['power'], reverse=not ascending)
    
    def clear(self):
        """Clear the opponent list"""
        self.opponents = []
        self.scroll_position = 0
