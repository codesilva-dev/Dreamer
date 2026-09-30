# New calibration-based team power detection
# This will replace the find_team_powers_hsv method

def find_team_powers_hsv_calibrated(self, image, debug_dir=None, debug_prefix=''):
    """
    Find team power values using calibration data.

    Uses calibrated offsets from "Power" text to know exactly where
    team power numbers and level badges are located.

    Args:
        image: BGR image (the OCR region crop)
        debug_dir: If set, save debug images
        debug_prefix: Prefix for debug filenames

    Returns:
        List of dicts with 'power' (int), 'level' (int), and 'y_position' (int)
    """
    import json
    import os
    from config import SCRIPT_DIR

    height, width = image.shape[:2]

    # Step 1: Load calibration data
    calibration_path = os.path.join(SCRIPT_DIR, 'arena_ocr_calibration.json')

    try:
        with open(calibration_path, 'r') as f:
            calibration = json.load(f)

        team_power_offset_x = calibration['team_power_offset_x']
        team_power_offset_y = calibration['team_power_offset_y']
        level_offset_x = calibration['level_offset_x']
        level_offset_y = calibration['level_offset_y']

        self._debug_log(f"  [CALIBRATION] Team Power offset: ({team_power_offset_x:+d}, {team_power_offset_y:+d})")
        self._debug_log(f"  [CALIBRATION] Level offset: ({level_offset_x:+d}, {level_offset_y:+d})")
    except Exception as e:
        self._debug_log(f"  [ERROR] Failed to load calibration: {e}")
        self._debug_log(f"  [ERROR] Run 'python calibrate_arena_ocr.py' first!")
        return []

    # Step 2: HSV filter for better OCR
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

    # Step 3: Upscale and OCR to find all "Power" text instances
    filtered_upscaled = cv2.resize(filtered, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    ocr_config = '--psm 6'  # Assume uniform block of text
    try:
        ocr_result = pytesseract.image_to_data(
            filtered_upscaled,
            config=ocr_config,
            output_type=pytesseract.Output.DICT
        )
    except Exception as e:
        self._debug_log(f"  [ERROR] OCR exception: {e}")
        return []

    # Step 4: Find all "Power" text instances
    power_instances = []
    for i, text in enumerate(ocr_result['text']):
        if not text:
            continue

        text_lower = text.lower()
        if 'power' in text_lower or 'fower' in text_lower or 'pover' in text_lower:
            # Get center of "Power" text (scaled back to original size)
            left = ocr_result['left'][i] // 2
            top = ocr_result['top'][i] // 2
            w = ocr_result['width'][i] // 2
            h = ocr_result['height'][i] // 2

            power_center_x = left + w // 2
            power_center_y = top + h // 2

            # Calculate where team power number should be
            team_power_x = power_center_x + team_power_offset_x
            team_power_y = power_center_y + team_power_offset_y

            # Calculate where level should be
            level_x = power_center_x + level_offset_x
            level_y = power_center_y + level_offset_y

            power_instances.append({
                'power_pos': (power_center_x, power_center_y),
                'team_power_pos': (team_power_x, team_power_y),
                'level_pos': (level_x, level_y),
                'power_box': (left, top, w, h)
            })

            self._debug_log(f"  [POWER] Found at ({power_center_x}, {power_center_y}), "
                          f"team_power@({team_power_x}, {team_power_y}), "
                          f"level@({level_x}, {level_y})")

    self._debug_log(f"  Found {len(power_instances)} 'Power' instances")

    if not power_instances:
        return []

    # Step 5: OCR team power numbers at each calibrated position
    results = []
    whitelist_power = '--psm 7 -c tessedit_char_whitelist=0123456789.,K'
    whitelist_level = '--psm 7 -c tessedit_char_whitelist=0123456789'

    for idx, instance in enumerate(power_instances):
        tp_x, tp_y = instance['team_power_pos']
        lv_x, lv_y = instance['level_pos']

        # OCR team power number
        # Crop a region around the expected position
        crop_width = 150  # Enough for "300.55K"
        crop_height = 20

        x1 = max(0, tp_x - 5)
        y1 = max(0, tp_y - crop_height // 2)
        x2 = min(width, tp_x + crop_width)
        y2 = min(height, tp_y + crop_height // 2)

        power_value = None
        power_text = None

        # Try OCR with multiple filter variants
        for filt_img in filter_variants:
            power_crop = filt_img[y1:y2, x1:x2]

            if power_crop.shape[0] < 5 or power_crop.shape[1] < 10:
                continue

            # Upscale for better OCR
            power_crop = np.ascontiguousarray(power_crop)
            padded = cv2.copyMakeBorder(power_crop, 10, 10, 5, 5, cv2.BORDER_CONSTANT, value=0)
            upscaled = cv2.resize(padded, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

            try:
                raw_text = pytesseract.image_to_string(upscaled, config=whitelist_power).strip().lstrip('., ')
            except Exception:
                continue

            if not raw_text or not re.match(r'\d', raw_text):
                continue

            match = re.match(r'^([\d,\.]+[K]?)$', raw_text)
            if not match:
                continue

            raw_power = match.group(1)
            power = self._parse_power_string(raw_power)

            if power and 1000 <= power <= 999000:
                power_value = power
                power_text = raw_text
                self._debug_log(f"  [POWER #{idx+1}] Read: {power:,} from '{raw_text}'")
                break

        # OCR player level
        crop_size = 30  # Level badge is small

        lx1 = max(0, lv_x - crop_size // 2)
        ly1 = max(0, lv_y - crop_size // 2)
        lx2 = min(width, lv_x + crop_size // 2)
        ly2 = min(height, lv_y + crop_size // 2)

        level_value = None

        for filt_img in filter_variants:
            level_crop = filt_img[ly1:ly2, lx1:lx2]

            if level_crop.shape[0] < 5 or level_crop.shape[1] < 5:
                continue

            # Upscale heavily for small level numbers
            level_crop = np.ascontiguousarray(level_crop)
            padded = cv2.copyMakeBorder(level_crop, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=0)
            upscaled = cv2.resize(padded, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)

            try:
                raw_text = pytesseract.image_to_string(upscaled, config=whitelist_level).strip()
            except Exception:
                continue

            if not raw_text or not raw_text.isdigit():
                continue

            level = int(raw_text)
            if 30 <= level <= 100:
                level_value = level
                self._debug_log(f"  [LEVEL #{idx+1}] Read: {level}")
                break

        # Only add if we got both power and level
        if power_value and level_value:
            results.append({
                'power': power_value,
                'level': level_value,
                'y_position': int(tp_y),
                'power_text': power_text
            })
            self._debug_log(f"  ✓ Opponent #{idx+1}: Power={power_value:,}, Level={level_value}")
        elif power_value:
            self._debug_log(f"  ! Opponent #{idx+1}: Power={power_value:,}, Level=? (OCR failed)")
        else:
            self._debug_log(f"  ✗ Opponent #{idx+1}: Failed to read power")

    # Save debug image
    if debug_dir:
        import os
        debug_img = cv2.cvtColor(filtered, cv2.COLOR_GRAY2BGR)

        for idx, instance in enumerate(power_instances):
            px, py = instance['power_pos']
            tp_x, tp_y = instance['team_power_pos']
            lv_x, lv_y = instance['level_pos']

            # Draw Power box (green)
            left, top, w, h = instance['power_box']
            cv2.rectangle(debug_img, (left, top), (left + w, top + h), (0, 255, 0), 2)

            # Draw team power location (blue)
            cv2.circle(debug_img, (tp_x, tp_y), 5, (255, 0, 0), -1)
            cv2.line(debug_img, (px, py), (tp_x, tp_y), (255, 128, 0), 1)

            # Draw level location (red)
            cv2.circle(debug_img, (lv_x, lv_y), 5, (0, 0, 255), -1)
            cv2.line(debug_img, (px, py), (lv_x, lv_y), (128, 0, 255), 1)

        cv2.imwrite(os.path.join(debug_dir, f'{debug_prefix}calibrated_detection.png'), debug_img)

    self._debug_log(f"  Calibrated scan found {len(results)} complete opponents (power + level)")
    return results
