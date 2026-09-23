"""
Text Recognition Module for Dreamer
Uses pytesseract OCR to read text from game screenshots
"""

import cv2
import numpy as np
import re
from collections import Counter

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
    
    def _parse_power_string(self, raw_value):
        """
        Parse a power value string that may contain K/k suffix.

        Handles formats like:
            "222.94K" -> 222940
            "8,309"   -> 8309
            "14.508"  -> 14508  (OCR reads comma as period)
            "1,234K"  -> 1234000

        Returns:
            Integer power value or None
        """
        s = raw_value.strip()

        # Check for K/k suffix (thousands multiplier)
        has_k = s.upper().endswith('K')
        if has_k:
            s = s[:-1].strip()

        # Remove commas (thousands separators)
        s = s.replace(',', '')

        if has_k:
            # With K suffix, the decimal point is meaningful: "222.94K" = 222.94 * 1000
            try:
                return int(float(s) * 1000)
            except ValueError:
                return None
        else:
            # Without K suffix, periods are likely OCR misreads of commas: "8.309" = "8,309" = 8309
            s = s.replace('.', '')
            try:
                return int(s)
            except ValueError:
                return None

    def parse_team_power(self, text):
        """
        Parse team power from text like "Team Power: 8,309" or "222.94K"

        Returns:
            Integer power value or None
        """
        # Pattern for "Team Power: XXXXX" or just numbers, with optional K suffix
        patterns = [
            r'Team\s*Power[:\s]*([\d,\.]+[Kk]?)',
            r'Power[:\s]*([\d,\.]+[Kk]?)',
            r'([\d,\.]{4,}[Kk])',   # Numbers with K suffix
            r'(\d[\d,\.]{3,})',      # 4+ digit numbers (team power range)
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result = self._parse_power_string(match.group(1))
                if result is not None:
                    return result

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
        # Also capture optional K/k suffix for thousands (e.g., "222.94K")
        pattern = r'(?:[Tt]?e?a?m?\s*)?[Pp]ower[:\.\s]+(\d[\d,\.]+[Kk]?)'

        matches_found = list(re.finditer(pattern, full_text, re.IGNORECASE))
        
        # Track which Y positions we've already used
        used_y_positions = set()
        
        # Also track found power values to avoid duplicates from fallback
        found_powers = set()
        
        for match in matches_found:
            raw_value = match.group(1)
            power = self._parse_power_string(raw_value)

            if power is None:
                continue

            try:
                # Filter out obvious OCR errors - arena team power is always 10K+
                if power < 10000:
                    continue
                
                # Try to find the Y position of this power value
                # First, look for the exact power number in positioned results
                y_pos = None
                
                # Method 1: Look for the raw power value in positioned text
                # Use the raw captured value (stripped of K) to match OCR fragments
                search_str = raw_value.rstrip('Kk').replace(',', '').replace('.', '')
                for result in results:
                    result_text = result['text'].replace(',', '').replace('.', '').rstrip('Kk')
                    if search_str in result_text or result_text in search_str:
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
            raw_text = result['text'].strip()
            # Match standalone numbers with optional K suffix
            if re.match(r'^[\d,\.]+[Kk]?$', raw_text):
                power = self._parse_power_string(raw_text)
                if power is not None and 10000 <= power <= 999999 and power not in found_powers:
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
        
        return powers

    def find_team_powers_targeted(self, image, debug_dir=None):
        """
        Find team power values using a two-pass targeted approach.

        Pass 1: Locate all "Power" text positions using sparse text detection.
        Pass 2: For each "Power" hit, crop a tight band to the right and OCR
                 just the number with a character whitelist (digits, K, period,
                 comma only). Uses --psm 7 (single text line) for accuracy.

        This is more reliable than find_all_team_powers because:
        - Whitelist prevents phantom reads from UI chrome
        - Tight crops eliminate visual noise from portraits/buttons
        - Single-line mode gives Tesseract strong layout hints

        Args:
            image: BGR image (the OCR region crop)
            debug_dir: If set, save anchor crops and annotated image here

        Returns:
            List of dicts with 'power' (int) and 'y_position' (int)
        """
        height, width = image.shape[:2]

        # Pass 1: Find all text elements, looking for "Power" anchors
        self._debug_log("Targeted scan: locating 'Power' anchors...")
        processed = self.preprocess_for_ocr(image, 'default')
        data = pytesseract.image_to_data(
            processed, config='--psm 11', output_type=pytesseract.Output.DICT
        )

        # Collect "Power" anchor positions
        anchors = []
        for i, text in enumerate(data['text']):
            stripped = text.strip()
            if not stripped:
                continue
            # Match "Power" or OCR variants like "ower", "Powe", "ipower"
            if re.search(r'[Pp]ow|ower', stripped, re.IGNORECASE):
                anchors.append({
                    'x': data['left'][i],
                    'y': data['top'][i],
                    'w': data['width'][i],
                    'h': data['height'][i],
                    'text': stripped,
                })

        self._debug_log(f"  Found {len(anchors)} 'Power' anchors")

        if not anchors:
            return []

        # Deduplicate anchors that are very close vertically (within 15px)
        anchors.sort(key=lambda a: a['y'])
        unique_anchors = [anchors[0]]
        for a in anchors[1:]:
            if abs(a['y'] - unique_anchors[-1]['y']) > 15:
                unique_anchors.append(a)
        anchors = unique_anchors

        # Pass 2: For each anchor, crop a tight band to the right and OCR the number
        powers = []
        used_y_positions = set()

        # Whitelist config: only digits, period, comma, K
        whitelist_config = '--psm 7 -c tessedit_char_whitelist=0123456789.,K'

        # Debug: prepare annotated image showing anchors + crops
        if debug_dir:
            import os
            debug_annotated = image.copy()
            crop_index = 0

        for anchor_idx, anchor in enumerate(anchors):
            # The number appears right after "Power:" text.
            # Use a fixed skip from the anchor's LEFT edge rather than
            # relying on bounding box width — box width varies wildly
            # when OCR garbles the text (e.g. '"Power' has inflated width).
            #
            # Crop vertically tight to the anchor's own height — this
            # prevents champion portrait badges above the text from
            # leaking into the crop and confusing OCR.
            #
            # Try multiple crop start positions to catch the leading digit
            # regardless of anchor x accuracy.
            result_text = None
            result_crop_info = None

            # Use anchor height + small padding for a tight vertical crop.
            # anchor['y'] is the top of "Power" text; the number is at
            # the same baseline. Pad 2px above, 4px below.
            text_h = max(anchor['h'], 14)  # At least 14px tall

            for skip_from_left in [50, 60, 70]:
                crop_x = max(0, anchor['x'] + skip_from_left)
                crop_y = max(0, anchor['y'] - 2)
                crop_w = min(180, width - crop_x)
                crop_h = min(text_h + 6, height - crop_y)

                if crop_w < 20 or crop_h < 10:
                    continue

                crop = image[crop_y:crop_y + crop_h, crop_x:crop_x + crop_w]

                # Isolate white text from colorful backgrounds.
                # Power numbers are white/near-white text. Champion portrait
                # badges (gold, purple, pink) also have high brightness but
                # are highly saturated (colorful).
                #
                # HSV filter: keep pixels that are bright (V > 180) AND
                # not colorful (S < 80). This isolates white/gray text
                # while killing gold badges (high S), purple borders
                # (high S), and dark backgrounds (low V).
                if len(crop.shape) == 3:
                    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                    white_mask = (hsv[:, :, 2] > 180) & (hsv[:, :, 1] < 80)
                    thresh_crop = np.where(white_mask, 255, 0).astype(np.uint8)
                else:
                    _, thresh_crop = cv2.threshold(crop, 180, 255, cv2.THRESH_BINARY)
                thresh_crop = cv2.resize(thresh_crop, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)

                raw_text = pytesseract.image_to_string(
                    thresh_crop, config=whitelist_config
                ).strip()

                # Strip leading periods/commas — colon often reads as "."
                raw_text = raw_text.lstrip('., ')

                # Debug: save each crop attempt (color + thresholded)
                if debug_dir:
                    crop_index += 1
                    status = 'hit' if (raw_text and re.match(r'\d', raw_text)) else 'miss'
                    crop_path = os.path.join(
                        debug_dir,
                        f"crop_{anchor_idx + 1}_{status}_skip{skip_from_left}.png"
                    )
                    thresh_path = os.path.join(
                        debug_dir,
                        f"crop_{anchor_idx + 1}_{status}_skip{skip_from_left}_thresh.png"
                    )
                    cv2.imwrite(crop_path, crop)
                    cv2.imwrite(thresh_path, thresh_crop)

                if raw_text and re.match(r'\d', raw_text):
                    result_text = raw_text
                    result_crop_info = f"({crop_x},{crop_y} {crop_w}x{crop_h})"
                    break

            # Debug: draw anchor box + crop region on annotated image
            if debug_dir:
                # Blue box = anchor bounding box ("Power" text)
                cv2.rectangle(debug_annotated,
                              (anchor['x'], anchor['y']),
                              (anchor['x'] + anchor['w'], anchor['y'] + anchor['h']),
                              (255, 0, 0), 1)
                # Green box = crop region (where we look for the number)
                if result_crop_info:
                    cv2.rectangle(debug_annotated,
                                  (crop_x, crop_y),
                                  (crop_x + crop_w, crop_y + crop_h),
                                  (0, 255, 0), 2)
                else:
                    # Red box = failed crop (last attempt position)
                    cv2.rectangle(debug_annotated,
                                  (crop_x, crop_y),
                                  (crop_x + crop_w, crop_y + crop_h),
                                  (0, 0, 255), 2)
                # Label
                label = result_text or 'EMPTY'
                cv2.putText(debug_annotated, label,
                            (crop_x, crop_y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            self._debug_log(f"  Anchor '{anchor['text']}' Y={anchor['y']} ->"
                            f"crop {result_crop_info or 'N/A'} ->'{result_text or ''}'")

            if not result_text:
                continue

            # Extract the number — accept only well-formed power formats:
            #   "222.94K"  — decimal with K suffix
            #   "16,511"   — comma as thousands separator (3 digits after)
            #   "300.75K"  — decimal with K suffix
            #   "131110"   — plain digits
            # Reject malformed like "268,40" (only 2 digits after comma = OCR error)
            match = re.match(r'^([\d,\.]+[K]?)', result_text)
            if not match:
                continue

            raw_power = match.group(1)

            # Validate comma usage: if commas present without K suffix,
            # each comma must be followed by exactly 3 digits (proper separator)
            if ',' in raw_power and not raw_power.upper().endswith('K'):
                if not re.match(r'^\d{1,3}(,\d{3})+$', raw_power):
                    self._debug_log(f"  Rejected malformed comma format: '{raw_power}'")
                    continue

            power = self._parse_power_string(raw_power)
            if power is None or power < 10000 or power > 999000:
                continue

            # Avoid duplicate Y positions
            y_pos = anchor['y']
            too_close = any(abs(y_pos - used_y) < 30 for used_y in used_y_positions)
            if too_close:
                continue

            used_y_positions.add(y_pos)
            powers.append({
                'power': power,
                'y_position': y_pos,
                'raw_text': result_text,
            })

        # Debug: save the annotated ROI showing all anchors + crops
        if debug_dir:
            import os
            annotated_path = os.path.join(debug_dir, 'targeted_anchors.png')
            cv2.imwrite(annotated_path, debug_annotated)

        self._debug_log(f"  Targeted scan found {len(powers)} power values")
        return powers

    def find_team_powers_hsv(self, image, debug_dir=None, debug_prefix=''):
        """
        Find team power values using HSV filtering + two-column detection.

        Strategy to separate power text from champion icon "60" labels:

        1. HSV-filter the whole region to isolate white/bright text
        2. Use the LEFT column (0-30% of ROI width) to find "Team Power:"
           label rows via row projection. The "Team Power:" label is a long
           string with density ~12+ in this zone, while "60" icon labels
           only reach density ~7-8 here — reliable separation.
        3. For each located "Team Power:" Y position, crop a tight band
           from the RIGHT column (30-100%) at that exact Y and OCR just
           the number with digit+K whitelist.

        This avoids icon noise entirely because only rows with a "Team
        Power:" label in the left column get scanned for numbers.

        Args:
            image: BGR image (the OCR region crop)
            debug_dir: If set, save filtered image for inspection

        Returns:
            List of dicts with 'power' (int) and 'y_position' (int)
        """
        height, width = image.shape[:2]

        # Step 1: HSV filter to isolate white/near-white pixels.
        # Build THREE filter variants at different thresholds for the
        # majority-vote OCR in Step 3. Different thresholds capture
        # different noise pixels, so Tesseract gets genuinely different
        # input at each threshold — preventing systematic misreads.
        if len(image.shape) == 3:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            white_mask = (hsv[:, :, 2] > 180) & (hsv[:, :, 1] < 80)
            filtered = np.where(white_mask, 255, 0).astype(np.uint8)
            strict_mask = (hsv[:, :, 2] > 200) & (hsv[:, :, 1] < 50)
            filtered_strict = np.where(strict_mask, 255, 0).astype(np.uint8)
            relaxed_mask = (hsv[:, :, 2] > 160) & (hsv[:, :, 1] < 100)
            filtered_relaxed = np.where(relaxed_mask, 255, 0).astype(np.uint8)
            filter_variants = [filtered, filtered_strict, filtered_relaxed]
        else:
            _, filtered = cv2.threshold(image, 180, 255, cv2.THRESH_BINARY)
            filter_variants = [filtered]

        # Step 2: Dual-column row projection to find "Team Power:" rows.
        #
        # The ROI is split into left (0-30%), middle (30-60%), right (60-100%).
        # "Team Power: 222.94K" spans left+mid columns, so both have density ≥10.
        # Noise sources only have density in ONE column:
        #   - Star ratings: high left (~17) but low mid (~5)
        #   - Icon "60" labels: low left (~5-9), variable mid
        #   - Icon borders: variable, rarely both ≥10
        #
        # Requiring BOTH left AND mid ≥ 10 average density selects only
        # power text rows.
        left_boundary = int(width * 0.30)
        mid_boundary = int(width * 0.60)
        left_col = filtered[:, :left_boundary]
        mid_col = filtered[:, left_boundary:mid_boundary]
        left_row_sums = left_col.sum(axis=1) // 255
        mid_row_sums = mid_col.sum(axis=1) // 255

        # Find bands where BOTH columns have sufficient density.
        # A row qualifies if left >= 10 AND mid >= 7. The left threshold
        # filters icon "60" labels (density ~5-8) from "Team Power:"
        # labels (density ~12-14). Mid is slightly more lenient because
        # the number text width varies.
        min_left_density = 10
        min_mid_density = 7
        label_bands = []
        in_band = False
        band_start = 0

        for y in range(height):
            if left_row_sums[y] >= min_left_density and mid_row_sums[y] >= min_mid_density:
                if not in_band:
                    band_start = y
                    in_band = True
            else:
                if in_band:
                    band_h = y - band_start
                    if 8 <= band_h <= 20:  # "Team Power:" text is ~12px tall
                        label_bands.append((band_start, y))
                    in_band = False
        if in_band:
            band_h = height - band_start
            if 8 <= band_h <= 20:
                label_bands.append((band_start, height))

        # Deduplicate bands that are too close (within 50px — one per opponent row)
        deduped_bands = []
        for band in label_bands:
            mid = (band[0] + band[1]) // 2
            too_close = any(abs(mid - (b[0] + b[1]) // 2) < 50 for b in deduped_bands)
            if not too_close:
                deduped_bands.append(band)
        label_bands = deduped_bands

        self._debug_log(f"  Dual-column projection found {len(label_bands)} 'Team Power:' rows")

        # Debug: save filtered image with band markers
        if debug_dir:
            import os
            debug_img = cv2.cvtColor(filtered, cv2.COLOR_GRAY2BGR)
            # Draw column boundaries
            cv2.line(debug_img, (left_boundary, 0), (left_boundary, height - 1),
                     (255, 255, 0), 1)
            cv2.line(debug_img, (mid_boundary, 0), (mid_boundary, height - 1),
                     (200, 200, 0), 1)
            for band_top, band_bot in label_bands:
                # Green box on left+mid columns = detected "Team Power:" label
                cv2.rectangle(debug_img, (0, band_top), (mid_boundary, band_bot),
                              (0, 255, 0), 1)
            cv2.imwrite(os.path.join(debug_dir, f'{debug_prefix}hsv_filtered.png'), filtered)
            # hsv_bands.png is saved after OCR loop to include number crop markers

        # Step 3: OCR the number portion at each detected label Y position.
        # The "Team Power:" label + colon position varies per row, so we
        # dynamically find the colon-to-number gap for each band.
        #
        # Uses best-of-3 majority vote across multiple HSV filter
        # thresholds (standard/strict/relaxed) × 2 scale combos = 6
        # total reads. A value must appear 2+ times to be trusted.
        whitelist_config = '--psm 7 -c tessedit_char_whitelist=0123456789.,K'
        powers = []
        used_y_positions = set()

        for band_idx, (band_top, band_bot) in enumerate(label_bands):
            # Find the number start by detecting the gap after the colon.
            # Use a slightly wider vertical crop for gap detection to
            # ensure we see all character strokes.
            gap_crop_y = max(0, band_top - 2)
            gap_crop_h = min(band_bot - band_top + 4, height - gap_crop_y)

            band_row = filtered[gap_crop_y:gap_crop_y + gap_crop_h, :]
            col_sums = band_row.sum(axis=0) // 255

            # Find clusters of white columns
            active_cols = [x for x in range(width) if col_sums[x] > 0]
            number_start_x = int(width * 0.44)  # fallback

            if active_cols:
                clusters = []
                cs = active_cols[0]
                prev = active_cols[0]
                for x in active_cols[1:]:
                    if x - prev > 3:
                        clusters.append((cs, prev))
                        cs = x
                    prev = x
                clusters.append((cs, prev))

                # Find the colon-to-number gap. The ":" colon is always
                # at approximately x=95-100 in the ROI. Look for the first
                # gap > 5px whose left edge falls in x=90-115.
                for ci in range(len(clusters) - 1):
                    gap_start = clusters[ci][1]
                    gap_end = clusters[ci + 1][0]
                    if 90 <= gap_start <= 115 and gap_end - gap_start > 5:
                        number_start_x = gap_end
                        break

            # Best-of-3 majority vote OCR with multiple filter variants.
            #
            # Tesseract's failure modes:
            #   - Digit-dropping: leading digits vanish → smaller number
            #   - Digit mutation: a digit misreads consistently when the
            #     same filtered image has noise near the digit.
            #
            # Running more OCR attempts on the SAME filtered image won't
            # fix mutations — the noise is baked into the pixels. Instead
            # we OCR across THREE different HSV filter thresholds, giving
            # Tesseract genuinely different input for each. A mutation
            # caused by noise at one threshold is unlikely to repeat at a
            # different threshold where that noise pixel doesn't survive.
            #
            # Each filter variant gets 2 attempts (different scale/padding)
            # = 6 total reads. Best-of-3 majority picks the winner.
            ocr_configs = [
                # (y_pad, scale, interpolation)
                (5, 3, cv2.INTER_CUBIC),   # wide context, 3x
                (2, 2, cv2.INTER_CUBIC),   # standard, 2x
            ]

            best_text = None
            best_power = None
            best_raw_power = None
            debug_strip = None
            all_reads = []

            for filt_img in filter_variants:
                for y_pad, scale, interp in ocr_configs:
                    crop_y = max(0, band_top - y_pad)
                    crop_h = min(band_bot - band_top + 2 * y_pad, height - crop_y)
                    band_strip = filt_img[crop_y:crop_y + crop_h, number_start_x:]

                    if band_strip.shape[0] < 5 or band_strip.shape[1] < 10:
                        continue

                    padded = cv2.copyMakeBorder(band_strip, 10, 10, 5, 5,
                                                cv2.BORDER_CONSTANT, value=0)
                    upscaled = cv2.resize(padded, None, fx=scale, fy=scale,
                                          interpolation=interp)

                    raw_text = pytesseract.image_to_string(
                        upscaled, config=whitelist_config
                    ).strip().lstrip('., ')

                    if not raw_text or not re.match(r'\d', raw_text):
                        continue

                    match = re.match(r'^([\d,\.]+[K]?)$', raw_text)
                    if not match:
                        continue

                    raw_power = match.group(1)

                    # Validate comma format
                    if ',' in raw_power and not raw_power.upper().endswith('K'):
                        if not re.match(r'^\d{1,3}(,\d{3})+$', raw_power):
                            continue

                    power = self._parse_power_string(raw_power)
                    if power is not None and 1000 <= power <= 999000:
                        all_reads.append((power, raw_text, band_strip))

            # Pick winner: require 2+ votes (majority). Ties broken by
            # higher value (digit-dropping always produces smaller numbers,
            # so the larger reading captured more leading digits).
            if all_reads:
                power_counts = Counter(r[0] for r in all_reads)
                unique_reads = {}
                for power, text, strip in all_reads:
                    if power not in unique_reads:
                        unique_reads[power] = (power, text, strip)

                # Values with 2+ votes
                majority_values = {p for p, c in power_counts.items() if c >= 2}

                if majority_values:
                    # Among majority values, pick: most votes, then highest
                    # power (larger = more leading digits = more correct)
                    best_entry = max(
                        (v for v in unique_reads.values() if v[0] in majority_values),
                        key=lambda r: (power_counts[r[0]], r[0])
                    )
                else:
                    # No majority — log warning, pick highest frequency
                    self._debug_log(f"  Band {band_idx + 1}: WARNING no majority "
                                    f"after {len(all_reads)} reads ({dict(power_counts)})")
                    best_entry = max(
                        unique_reads.values(),
                        key=lambda r: (power_counts[r[0]], r[0])
                    )

                best_power, best_text, debug_strip = best_entry

            # Debug: save band crop and annotate bands image
            if debug_dir:
                # Save the strip from the standard crop for visual inspection
                std_crop_y = max(0, band_top - 2)
                std_crop_h = min(band_bot - band_top + 4, height - std_crop_y)
                std_strip = filtered[std_crop_y:std_crop_y + std_crop_h, number_start_x:]
                status = 'hit' if best_power else 'miss'
                cv2.imwrite(
                    os.path.join(debug_dir, f'{debug_prefix}band_{band_idx + 1}_{status}.png'),
                    std_strip
                )
                if debug_strip is not None:
                    padded = cv2.copyMakeBorder(debug_strip, 10, 10, 5, 5,
                                                cv2.BORDER_CONSTANT, value=0)
                    up_debug = cv2.resize(padded, None, fx=3, fy=3,
                                          interpolation=cv2.INTER_CUBIC)
                    cv2.imwrite(
                        os.path.join(debug_dir, f'{debug_prefix}band_{band_idx + 1}_{status}_2x.png'),
                        up_debug
                    )
                # Draw number crop zone on bands image
                color = (0, 255, 0) if best_power else (0, 0, 255)
                cv2.rectangle(debug_img, (number_start_x, band_top),
                              (width - 1, band_bot), color, 1)
                label = best_text or 'EMPTY'
                cv2.putText(debug_img, label, (number_start_x, band_top - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

            if not best_power:
                self._debug_log(f"  Band {band_idx + 1} Y={band_top}-{band_bot} -> no valid read")
                continue

            y_pos = (band_top + band_bot) // 2

            too_close = any(abs(y_pos - used_y) < 30 for used_y in used_y_positions)
            if too_close:
                continue

            used_y_positions.add(y_pos)
            powers.append({
                'power': best_power,
                'y_position': y_pos,
                'raw_text': best_text,
            })
            votes = dict(Counter(r[0] for r in all_reads))
            self._debug_log(f"  Band {band_idx + 1} Y={band_top}-{band_bot} ->{best_power:,} ('{best_text}') votes={votes}")

        # Save the annotated bands image after all bands processed
        if debug_dir:
            cv2.imwrite(os.path.join(debug_dir, f'{debug_prefix}hsv_bands.png'), debug_img)

        self._debug_log(f"  HSV scan found {len(powers)} power values")
        return powers

    def find_player_levels_hsv(self, image, debug_dir=None, debug_prefix='',
                               power_y_hints=None):
        """
        Find player level numbers using HSV filtering.

        The level number (1-100) appears as white text inside a colored circle
        badge on the left side of each opponent row.

        Strategy:
        1. Upscale the raw color image 3x FIRST — at native resolution the
           digits are only 1-2px wide, too thin for reliable OCR. Upscaling
           before filtering produces 3-6px strokes with cleaner edges.
        2. HSV-filter the upscaled image to isolate white text pixels
        3. If power_y_hints are provided, OCR directly at those Y positions
           (most reliable — we know exactly where opponent rows are).
           Otherwise, fall back to row projection band detection.
        4. OCR each position/band with digit-only whitelist

        Args:
            image: BGR image (the level region crop, ~1.75% width of screen)
            debug_dir: If set, save debug images
            debug_prefix: Prefix for debug filenames
            power_y_hints: Optional list of Y positions (in original image
                coords) where power values were found. Used to predict
                level badge positions directly instead of band detection.

        Returns:
            List of dicts with 'level' (int) and 'y_position' (int)
            (y_position is in ORIGINAL image coordinates, not upscaled)
        """
        orig_height, orig_width = image.shape[:2]

        if orig_height < 10 or orig_width < 5:
            return []

        # Step 1: Upscale the raw color image BEFORE filtering.
        # At native ~30px wide, digit strokes are 1-2px — too thin for
        # morphology or reliable HSV edge detection. 3x upscale produces
        # 3-6px strokes that filter and OCR much more cleanly.
        PRE_SCALE = 3
        upscaled_img = cv2.resize(image, None, fx=PRE_SCALE, fy=PRE_SCALE,
                                  interpolation=cv2.INTER_CUBIC)
        height, width = upscaled_img.shape[:2]

        # Step 2: HSV filter on the upscaled image.
        # Create TWO filtered images at different thresholds:
        #   - strict (V>190, S<60): cleaner, less noise, but drops digit
        #     edge pixels on certain badge colors (teal/cyan)
        #   - relaxed (V>180, S<80): matches power scan thresholds, captures
        #     more digit edges but also more portrait art noise
        #
        # OCR tries the strict filter first. If all strict attempts fail
        # for a position, it falls back to the relaxed filter — the extra
        # noise is acceptable because we know the position is correct
        # from power-guided hints, we just need more digit pixels.
        if len(upscaled_img.shape) == 3:
            hsv = cv2.cvtColor(upscaled_img, cv2.COLOR_BGR2HSV)
            strict_mask = (hsv[:, :, 2] > 190) & (hsv[:, :, 1] < 60)
            filtered = np.where(strict_mask, 255, 0).astype(np.uint8)
            relaxed_mask = (hsv[:, :, 2] > 180) & (hsv[:, :, 1] < 80)
            filtered_relaxed = np.where(relaxed_mask, 255, 0).astype(np.uint8)
        else:
            _, filtered = cv2.threshold(upscaled_img, 190, 255, cv2.THRESH_BINARY)
            filtered_relaxed = filtered  # no color info, can't relax

        # Step 3: Determine OCR target positions.
        # If power_y_hints are provided, use them directly — we know exactly
        # where opponent rows are from the power scan. Otherwise, fall back
        # to row projection band detection.
        whitelist_config = '--psm 7 -c tessedit_char_whitelist=0123456789'
        levels = []
        used_y_positions = set()  # in upscaled coordinates
        est_band_h = 12 * PRE_SCALE  # typical level text height at 3x (~36px)

        # PSM 7 = single text line, PSM 8 = single word.
        # PSM 8 can handle short 2-digit numbers better than PSM 7.
        whitelist_psm8 = '--psm 8 -c tessedit_char_whitelist=0123456789'
        ocr_attempts = [
            # (y_pad, additional_scale, interpolation, tesseract_config)
            (8 * PRE_SCALE, 2, cv2.INTER_CUBIC, whitelist_config),    # wide, 6x, psm7
            (8 * PRE_SCALE, 2, cv2.INTER_CUBIC, whitelist_psm8),     # wide, 6x, psm8
            (5 * PRE_SCALE, 2, cv2.INTER_CUBIC, whitelist_config),   # medium, 6x, psm7
            (5 * PRE_SCALE, 2, cv2.INTER_CUBIC, whitelist_psm8),     # medium, 6x, psm8
            (8 * PRE_SCALE, 1, cv2.INTER_CUBIC, whitelist_config),   # wide, 3x, psm7
            (5 * PRE_SCALE, 1, cv2.INTER_CUBIC, whitelist_config),   # medium, 3x, psm7
        ]

        if power_y_hints and len(power_y_hints) >= 2:
            # Power-guided mode: OCR at known opponent row Y positions.
            # The "Team Power:" text sits lower in each row than the level
            # badge. Compute the offset dynamically from the row spacing:
            # the badge is approximately 14% of one row spacing above the
            # power text position.
            #
            # Use the MINIMUM spacing between consecutive hints to get the
            # true single-row spacing. When the power scan misses entries,
            # some spacings are 2x or 3x the real row spacing — using the
            # median would produce a wrong offset.
            sorted_hints = sorted(power_y_hints)
            spacings = [sorted_hints[i+1] - sorted_hints[i] for i in range(len(sorted_hints) - 1)]
            row_spacing = min(spacings)

            # Sanity check: if the minimum spacing is unreasonably large
            # (> 150px, meaning even adjacent found powers are far apart),
            # clamp the offset to a safe maximum.
            y_offset = int(row_spacing * 0.14)
            y_offset = min(y_offset, 20)  # never more than 20px offset

            target_positions = [int(y * PRE_SCALE) - y_offset * PRE_SCALE for y in power_y_hints]
            self._debug_log(f"  [LVL] Power-guided: {len(target_positions)} positions (offset={y_offset}px up)")
        else:
            # Fallback: row projection band detection
            row_sums = filtered.sum(axis=1) // 255
            min_density = 3 * PRE_SCALE
            min_band_h_detect = 6 * PRE_SCALE
            max_band_h_detect = 24 * PRE_SCALE
            bands = []
            in_band = False
            band_start = 0

            for y in range(height):
                if row_sums[y] >= min_density:
                    if not in_band:
                        band_start = y
                        in_band = True
                else:
                    if in_band:
                        band_h = y - band_start
                        if min_band_h_detect <= band_h <= max_band_h_detect:
                            bands.append((band_start, y))
                        in_band = False
            if in_band:
                band_h = height - band_start
                if min_band_h_detect <= band_h <= max_band_h_detect:
                    bands.append((band_start, height))

            # Deduplicate bands within 50*PRE_SCALE px
            dedup_dist = 50 * PRE_SCALE
            deduped = []
            for band in bands:
                mid = (band[0] + band[1]) // 2
                too_close = any(abs(mid - (b[0] + b[1]) // 2) < dedup_dist for b in deduped)
                if not too_close:
                    deduped.append(band)
            bands = deduped
            target_positions = [(b[0] + b[1]) // 2 for b in bands]
            self._debug_log(f"  [LVL] Row projection found {len(bands)} level bands")

        # Debug: save filtered image with target markers
        if debug_dir:
            import os
            debug_img = cv2.cvtColor(filtered, cv2.COLOR_GRAY2BGR)
            for ty in target_positions:
                cv2.rectangle(debug_img, (0, ty - est_band_h // 2),
                              (width - 1, ty + est_band_h // 2),
                              (0, 255, 0), 1)

        # Step 4: OCR at each target position.
        # Crop X to skip the leftmost edge noise from the portrait frame.
        # Use a small 10% crop — 25% was too aggressive and cut into the
        # leftmost digit of 3-digit numbers like "100".
        x_crop_start = int(width * 0.10)  # Skip the left 10% (frame edge noise)

        for pos_idx, target_y in enumerate(target_positions):
            best_level = None

            # Local row projection: find the tight text band within
            # the target area, just like the power scan does. This
            # crops to only the digit rows, excluding noise above/below.
            search_top = max(0, target_y - est_band_h)
            search_bot = min(height, target_y + est_band_h)
            local_strip = filtered[search_top:search_bot, x_crop_start:]
            local_sums = local_strip.sum(axis=1) // 255

            # Find all contiguous bands within the search area, then pick
            # the one closest to target_y. Previous approach picked the
            # "densest" band, but noise blobs from portrait art can have
            # higher total density than the actual digit band — causing
            # misreads like 57→27 (noise band above digits) or 100→6
            # (noise band instead of digit band). Closest-to-target is
            # more reliable because power-guided positioning already
            # tells us where digits should be.
            in_local = False
            local_start = 0
            candidate_bands = []

            for ly in range(local_strip.shape[0]):
                if local_sums[ly] >= 3:
                    if not in_local:
                        local_start = ly
                        in_local = True
                else:
                    if in_local:
                        band_h = ly - local_start
                        if 6 <= band_h <= max(50, est_band_h):
                            candidate_bands.append((search_top + local_start, search_top + ly))
                        in_local = False
            if in_local:
                band_h = local_strip.shape[0] - local_start
                if 6 <= band_h <= max(50, est_band_h):
                    candidate_bands.append((search_top + local_start, search_top + local_strip.shape[0]))

            # Pick the band whose center is closest to target_y
            best_band = None
            if candidate_bands:
                best_band = min(candidate_bands,
                                key=lambda b: abs((b[0] + b[1]) // 2 - target_y))

            # Run OCR on BOTH strict and relaxed filtered images, collecting
            # all valid reads. Then pick the best one using a "longest wins"
            # heuristic — the most common failure mode is digit-dropping
            # (72→7, 61→1, 57→5) where Tesseract reads fewer digits than
            # actually present. A longer reading (more digits) is more
            # likely correct than a shorter one.
            #
            # For each filter, redo local band detection since the band
            # boundaries shift with different thresholds.
            all_reads = []       # list of valid level values from all attempts
            strict_reads = []    # reads from strict filter only (higher trust)

            for filter_pass, filt_img in enumerate([filtered, filtered_relaxed]):
                # Redo band detection for relaxed pass
                if filter_pass == 1:
                    local_strip_r = filt_img[search_top:search_bot, x_crop_start:]
                    local_sums_r = local_strip_r.sum(axis=1) // 255
                    in_lr = False
                    lr_start = 0
                    cands_r = []
                    for ly in range(local_strip_r.shape[0]):
                        if local_sums_r[ly] >= 3:
                            if not in_lr:
                                lr_start = ly
                                in_lr = True
                        else:
                            if in_lr:
                                bh = ly - lr_start
                                if 6 <= bh <= max(50, est_band_h):
                                    cands_r.append((search_top + lr_start, search_top + ly))
                                in_lr = False
                    if in_lr:
                        bh = local_strip_r.shape[0] - lr_start
                        if 6 <= bh <= max(50, est_band_h):
                            cands_r.append((search_top + lr_start, search_top + local_strip_r.shape[0]))
                    pass_band = min(cands_r, key=lambda b: abs((b[0]+b[1])//2 - target_y)) if cands_r else best_band
                else:
                    pass_band = best_band

                # Column projection: find tight horizontal bounds of the
                # digits within the band to exclude noise left/right.
                # Use the band from this filter pass to find columns with
                # white pixels, then crop to just those columns + padding.
                col_crop_left = 0
                col_crop_right = width - x_crop_start  # full width by default
                if pass_band:
                    bt, bb = pass_band
                    col_strip = filt_img[bt:bb, x_crop_start:]
                    col_sums = col_strip.sum(axis=0) // 255
                    # Find first and last column with any content
                    active_cols = [x for x in range(len(col_sums)) if col_sums[x] > 0]
                    if len(active_cols) >= 2:
                        # Add small padding (3px at 3x scale = 1 orig pixel)
                        col_crop_left = max(0, active_cols[0] - 3)
                        col_crop_right = min(len(col_sums), active_cols[-1] + 4)

                for y_pad, scale, interp, tess_config in ocr_attempts:
                    if pass_band:
                        bt, bb = pass_band
                        crop_y = max(0, bt - y_pad)
                        crop_h = min(bb - bt + 2 * y_pad, height - crop_y)
                    else:
                        crop_y = max(0, target_y - est_band_h // 2 - y_pad)
                        crop_h = min(est_band_h + 2 * y_pad, height - crop_y)

                    band_strip = filt_img[crop_y:crop_y + crop_h,
                                          x_crop_start + col_crop_left:
                                          x_crop_start + col_crop_right]

                    if band_strip.shape[0] < 4 or band_strip.shape[1] < 4:
                        continue

                    # Connected component filtering: remove small noise
                    # blobs that confuse Tesseract. Digit strokes at 3x
                    # scale are ~3-6px wide × 10-30px tall, so real digit
                    # components have area ≥ 30px². Noise specks from
                    # portrait art are typically < 20px².
                    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
                        band_strip, connectivity=8)
                    cleaned = np.zeros_like(band_strip)
                    min_component_area = 25  # pixels at 3x scale
                    for lbl in range(1, num_labels):  # skip background (0)
                        if stats[lbl, cv2.CC_STAT_AREA] >= min_component_area:
                            cleaned[labels == lbl] = 255
                    band_strip = cleaned

                    padded = cv2.copyMakeBorder(band_strip, 10, 10, 5, 5,
                                                cv2.BORDER_CONSTANT, value=0)
                    if scale > 1:
                        ocr_img = cv2.resize(padded, None, fx=scale, fy=scale,
                                             interpolation=interp)
                    else:
                        ocr_img = padded

                    raw_text = pytesseract.image_to_string(
                        ocr_img, config=tess_config
                    ).strip()

                    if not raw_text:
                        continue

                    try:
                        val = int(raw_text)
                    except ValueError:
                        continue

                    if 1 <= val <= 100:
                        all_reads.append(val)
                        if filter_pass == 0:
                            strict_reads.append(val)

            # Pick the best reading using a multi-level heuristic:
            #   1. Prefer more digits (2-digit > 1-digit > 3-digit by count)
            #   2. Among same digit count, prefer values that appeared in
            #      the strict filter (less noise = higher confidence)
            #   3. Break remaining ties by total frequency
            if all_reads:
                counts = Counter(all_reads)
                strict_counts = Counter(strict_reads)

                # Confidence gate: require at least 3 total reads OR at
                # least 1 strict read. With fewer reads, single-digit
                # misreads (e.g. 70→7, 80→8) can't be distinguished from
                # real single-digit levels. When rejected, the level is
                # set to None so the arena filter applies only the power
                # condition for this opponent.
                total_reads = len(all_reads)
                total_strict = len(strict_reads)
                if total_reads < 3 and total_strict < 1:
                    self._debug_log(f"  [LVL] Pos {pos_idx + 1} Y={target_y} -> REJECTED "
                                    f"(low confidence: {total_reads} reads, {total_strict} strict, "
                                    f"values={dict(counts)})")
                    best_level = None
                else:
                    best_level = max(counts.keys(),
                                     key=lambda v: (len(str(v)),
                                                    strict_counts.get(v, 0),
                                                    counts[v]))

            # Debug annotation
            if debug_dir:
                color = (0, 255, 0) if best_level else (0, 0, 255)
                label = str(best_level) if best_level else '?'
                cv2.putText(debug_img, label, (2, target_y - est_band_h // 2 - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

            if best_level is None:
                self._debug_log(f"  [LVL] Pos {pos_idx + 1} Y={target_y} -> no valid read (0 reads)")
                continue

            too_close = any(abs(target_y - used_y) < 30 * PRE_SCALE for used_y in used_y_positions)
            if too_close:
                continue

            used_y_positions.add(target_y)
            levels.append({
                'level': best_level,
                'y_position': target_y // PRE_SCALE,  # Convert back to original coords
            })
            self._debug_log(f"  [LVL] Pos {pos_idx + 1} Y={target_y} -> L{best_level} (all: {dict(counts)}, strict: {dict(strict_counts)})")

        if debug_dir:
            import os
            cv2.imwrite(os.path.join(debug_dir, f'{debug_prefix}level_bands.png'), debug_img)

        self._debug_log(f"  [LVL] Found {len(levels)} player levels")
        return levels


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
