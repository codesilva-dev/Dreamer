    def find_team_powers_calibrated(self, image, debug_dir=None, debug_prefix=''):
        """
        Find team power AND level using FIXED WINDOW calibration.

        Workflow:
        1. Load calibration (window sizes and offsets from Power center)
        2. Find all "Power" text instances using OCR
        3. For each Power, crop FIXED RECTANGLE at calibrated offset
        4. OCR the team power window
        5. OCR the level window
        6. Save debug images of each cropped window
        7. Return opponents with power + level

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

        # Step 1: Load calibration (window-based)
        calibration_path = os.path.join(SCRIPT_DIR, 'arena_ocr_calibration.json')

        try:
            with open(calibration_path, 'r') as f:
                calibration = json.load(f)

            tp_win = calibration['team_power_window']
            lv_win = calibration['level_window']

            self._debug_log(f"  [CALIBRATION] Team Power window: {tp_win['width']}x{tp_win['height']} "
                          f"at offset ({tp_win['offset_x']:+d}, {tp_win['offset_y']:+d})")
            self._debug_log(f"  [CALIBRATION] Level window: {lv_win['width']}x{lv_win['height']} "
                          f"at offset ({lv_win['offset_x']:+d}, {lv_win['offset_y']:+d})")
        except Exception as e:
            self._debug_log(f"  [ERROR] Failed to load calibration: {e}")
            self._debug_log(f"  [ERROR] Run 'python calibrate_arena_windows.py' first!")
            return []

        # Step 2: HSV filter for Power detection
        if len(image.shape) == 3:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            white_mask = (hsv[:, :, 2] > 180) & (hsv[:, :, 1] < 80)
            filtered = np.where(white_mask, 255, 0).astype(np.uint8)
        else:
            _, filtered = cv2.threshold(image, 180, 255, cv2.THRESH_BINARY)

        # Step 3: Find all "Power" text instances
        filtered_upscaled = cv2.resize(filtered, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        try:
            ocr_result = pytesseract.image_to_data(
                filtered_upscaled,
                config='--psm 6',
                output_type=pytesseract.Output.DICT
            )
        except Exception as e:
            self._debug_log(f"  [ERROR] OCR exception: {e}")
            return []

        power_instances = []
        for i, text in enumerate(ocr_result['text']):
            if not text:
                continue

            text_lower = text.lower()
            if 'power' in text_lower or 'fower' in text_lower or 'pover' in text_lower:
                # Get center of "Power" (scaled back to original)
                left = ocr_result['left'][i] // 2
                top = ocr_result['top'][i] // 2
                w = ocr_result['width'][i] // 2
                h = ocr_result['height'][i] // 2

                power_center_x = left + w // 2
                power_center_y = top + h // 2

                power_instances.append({
                    'center_x': power_center_x,
                    'center_y': power_center_y,
                    'box': (left, top, w, h)
                })

                self._debug_log(f"  [POWER] Found at center ({power_center_x}, {power_center_y})")

        self._debug_log(f"  Found {len(power_instances)} 'Power' instances")

        if not power_instances:
            return []

        # Step 4: OCR each power instance using FIXED WINDOWS
        results = []
        whitelist_power = '--psm 7 -c tessedit_char_whitelist=0123456789.,K'
        whitelist_level = '--psm 7 -c tessedit_char_whitelist=0123456789'

        for idx, power in enumerate(power_instances):
            px, py = power['center_x'], power['center_y']

            # Calculate team power window position
            tp_x1 = px + tp_win['offset_x']
            tp_y1 = py + tp_win['offset_y']
            tp_x2 = tp_x1 + tp_win['width']
            tp_y2 = tp_y1 + tp_win['height']

            # Calculate level window position
            lv_x1 = px + lv_win['offset_x']
            lv_y1 = py + lv_win['offset_y']
            lv_x2 = lv_x1 + lv_win['width']
            lv_y2 = lv_y1 + lv_win['height']

            # Clamp to image boundaries
            tp_x1, tp_y1 = max(0, tp_x1), max(0, tp_y1)
            tp_x2, tp_y2 = min(width, tp_x2), min(height, tp_y2)
            lv_x1, lv_y1 = max(0, lv_x1), max(0, lv_y1)
            lv_x2, lv_y2 = min(width, lv_x2), min(height, lv_y2)

            # Crop FIXED windows from original image
            team_power_window = image[tp_y1:tp_y2, tp_x1:tp_x2].copy()
            level_window = image[lv_y1:lv_y2, lv_x1:lv_x2].copy()

            # OCR team power
            power_value = None
            power_text = None

            if team_power_window.shape[0] > 5 and team_power_window.shape[1] > 10:
                # Convert to grayscale and threshold
                if len(team_power_window.shape) == 3:
                    gray_tp = cv2.cvtColor(team_power_window, cv2.COLOR_BGR2GRAY)
                else:
                    gray_tp = team_power_window

                _, thresh_tp = cv2.threshold(gray_tp, 180, 255, cv2.THRESH_BINARY)

                # Upscale for better OCR
                thresh_tp = np.ascontiguousarray(thresh_tp)
                padded_tp = cv2.copyMakeBorder(thresh_tp, 10, 10, 5, 5, cv2.BORDER_CONSTANT, value=0)
                upscaled_tp = cv2.resize(padded_tp, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

                try:
                    raw_text = pytesseract.image_to_string(upscaled_tp, config=whitelist_power).strip().lstrip('., ')

                    if raw_text and re.match(r'\d', raw_text):
                        match = re.match(r'^([\d,\.]+[K]?)$', raw_text)
                        if match:
                            raw_power = match.group(1)
                            power_value = self._parse_power_string(raw_power)

                            if power_value and 1000 <= power_value <= 999000:
                                power_text = raw_text
                                self._debug_log(f"  Band {idx + 1} -> {power_value:,} ('{raw_text}')")
                except Exception:
                    pass

            # OCR level
            level_value = None

            if level_window.shape[0] > 5 and level_window.shape[1] > 5:
                # Convert to grayscale and threshold
                if len(level_window.shape) == 3:
                    gray_lv = cv2.cvtColor(level_window, cv2.COLOR_BGR2GRAY)
                else:
                    gray_lv = level_window

                _, thresh_lv = cv2.threshold(gray_lv, 180, 255, cv2.THRESH_BINARY)

                # Upscale heavily for small level numbers
                thresh_lv = np.ascontiguousarray(thresh_lv)
                padded_lv = cv2.copyMakeBorder(thresh_lv, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=0)
                upscaled_lv = cv2.resize(padded_lv, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)

                try:
                    raw_text = pytesseract.image_to_string(upscaled_lv, config=whitelist_level).strip()

                    if raw_text and raw_text.isdigit():
                        level = int(raw_text)
                        if 30 <= level <= 100:
                            level_value = level
                            self._debug_log(f"    Level={level}")
                except Exception:
                    pass

            # Save debug images
            if debug_dir:
                status = 'hit' if power_value else 'miss'

                # Save team power window
                cv2.imwrite(
                    os.path.join(debug_dir, f'{debug_prefix}band_{idx + 1}_{status}.png'),
                    thresh_tp if power_value else team_power_window
                )

                # Save upscaled version
                if power_value:
                    cv2.imwrite(
                        os.path.join(debug_dir, f'{debug_prefix}band_{idx + 1}_{status}_2x.png'),
                        upscaled_tp
                    )

                # Save level window
                if level_value:
                    cv2.imwrite(
                        os.path.join(debug_dir, f'{debug_prefix}band_{idx + 1}_level.png'),
                        upscaled_lv
                    )

            # Only add if we got both power and level
            if power_value and level_value:
                results.append({
                    'power': power_value,
                    'level': level_value,
                    'y_position': int(py),
                    'raw_text': power_text
                })
                self._debug_log(f"  ✓ Opponent #{idx + 1}: Power={power_value:,}, Level={level_value}")
            elif power_value:
                # Still add if we have power but no level (level OCR can be flaky)
                results.append({
                    'power': power_value,
                    'level': None,
                    'y_position': int(py),
                    'raw_text': power_text
                })
                self._debug_log(f"  ! Opponent #{idx + 1}: Power={power_value:,}, Level=? (OCR failed)")
            else:
                self._debug_log(f"  ✗ Opponent #{idx + 1}: Failed to read power")

        self._debug_log(f"  Window-based scan found {len(results)} opponents")
        return results
