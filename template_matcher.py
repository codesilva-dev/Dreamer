import cv2
import numpy as np
import pyautogui
from natural_click import NaturalClick


class TemplateMatcher:
    def __init__(self, window_capture):
        self.window_capture = window_capture
        self.clicker = NaturalClick()

    def find_template(self, template_path, threshold=0.8, use_color=False):
        """
        Find template image in window without clicking.

        Args:
            template_path: Path to the template image file.
            threshold: Minimum match confidence (0-1).
            use_color: If True, match using full BGR color channels instead
                of grayscale. Better for distinguishing small text/digit
                differences where color provides extra signal.

        Returns:
            (found, location, size) where:
            - found: True/False
            - location: (x, y) center position relative to window, or None
            - size: (width, height) of template, or None
        """
        self.clicker.natural_delay(0.3)
        frame = self.window_capture.capture()

        template = cv2.imread(template_path)
        if template is None:
            return False, None, None

        if use_color:
            match_frame = frame
            match_template = template
        else:
            match_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            match_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        for scale in [1.0, 0.9, 1.1, 0.8, 1.2]:
            scaled_template = cv2.resize(match_template, None, fx=scale, fy=scale,
                                        interpolation=cv2.INTER_CUBIC)

            if (scaled_template.shape[0] > match_frame.shape[0] or
                scaled_template.shape[1] > match_frame.shape[1]):
                continue

            result = cv2.matchTemplate(match_frame, scaled_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                h, w = scaled_template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return True, (center_x, center_y), (w, h)

        return False, None, None

    def find_all_templates(self, template_path, threshold=0.8, min_distance=30):
        """
        Find ALL instances of a template in the current window.

        Uses non-maximum suppression to avoid duplicate detections
        of the same on-screen element.

        Args:
            template_path: Path to the template image.
            threshold: Minimum match confidence (0-1).
            min_distance: Minimum pixel distance between distinct matches.

        Returns:
            List of (x, y) center positions relative to window,
            sorted by Y position (top to bottom). Empty list if none found.
        """
        self.clicker.natural_delay(0.3)
        frame = self.window_capture.capture()

        template = cv2.imread(template_path)
        if template is None:
            return []

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        for scale in [1.0, 0.9, 1.1, 0.8, 1.2]:
            scaled_template = cv2.resize(gray_template, None, fx=scale, fy=scale,
                                         interpolation=cv2.INTER_CUBIC)

            if (scaled_template.shape[0] > gray_frame.shape[0] or
                    scaled_template.shape[1] > gray_frame.shape[1]):
                continue

            result = cv2.matchTemplate(gray_frame, scaled_template, cv2.TM_CCOEFF_NORMED)
            h, w = scaled_template.shape

            # Find all locations above threshold
            locations = np.where(result >= threshold)
            if len(locations[0]) == 0:
                continue

            # Collect all candidate center points
            candidates = []
            for pt_y, pt_x in zip(*locations):
                center_x = pt_x + w // 2
                center_y = pt_y + h // 2
                score = result[pt_y, pt_x]
                candidates.append((center_x, center_y, score))

            # Non-maximum suppression: keep the highest-scoring point
            # within each cluster of nearby detections
            candidates.sort(key=lambda c: -c[2])  # best score first
            kept = []
            for cx, cy, score in candidates:
                too_close = any(
                    abs(cx - kx) < min_distance and abs(cy - ky) < min_distance
                    for kx, ky, _ in kept
                )
                if not too_close:
                    kept.append((cx, cy, score))

            if kept:
                # Sort by Y position (top to bottom)
                kept.sort(key=lambda c: c[1])
                return [(x, y) for x, y, _ in kept]

        return []

    def click_at_offset(self, base_x, base_y, offset_x=0, offset_y=0, wait_after=1.0):
        """
        Click at a position with offset from base coordinates.
        Coordinates are relative to window.
        """
        left, top, _, _ = self.window_capture.window_info
        abs_x = left + base_x + offset_x
        abs_y = top + base_y + offset_y

        pyautogui.moveTo(abs_x, abs_y, duration=0.3)
        self.clicker.natural_delay(0.2)
        self.clicker.click()
        self.clicker.natural_delay(wait_after)

    def find_and_click(self, template_path, threshold=0.8, wait_after=3.0):
        """Find template image in window and click it"""
        self.clicker.natural_delay(0.3)
        frame = self.window_capture.capture()

        # Load template image
        template = cv2.imread(template_path)
        if template is None:
            return False, f'Template not found: {template_path}'

        # Convert to grayscale
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        # Try multiple scales
        for scale in [1.0, 0.9, 1.1, 0.8, 1.2]:
            scaled_template = cv2.resize(gray_template, None, fx=scale, fy=scale,
                                        interpolation=cv2.INTER_CUBIC)

            if (scaled_template.shape[0] > gray_frame.shape[0] or
                scaled_template.shape[1] > gray_frame.shape[1]):
                continue

            result = cv2.matchTemplate(gray_frame, scaled_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                h, w = scaled_template.shape
                x = max_loc[0] + w // 2
                y = max_loc[1] + h // 2

                left, top, _, _ = self.window_capture.window_info
                abs_x = left + x
                abs_y = top + y

                pyautogui.moveTo(abs_x, abs_y, duration=0.3)
                self.clicker.natural_delay(0.2)
                self.clicker.click()
                self.clicker.natural_delay(wait_after)
                return True, f'Found (confidence: {max_val:.2%}, scale: {scale:.1f}x)'

        return False, 'Template not found in window'
