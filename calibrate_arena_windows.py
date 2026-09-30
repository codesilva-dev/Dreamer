#!/usr/bin/env python3
"""
Arena OCR Window Calibration Tool

This tool lets you define FIXED RECTANGLE WINDOWS for team power and level OCR.

Workflow:
1. Screenshot the Classic Arena opponent list
2. Auto-detect all "Power" text instances
3. For the FIRST "Power", you DRAW A RECTANGLE around the team power number
4. Then DRAW A RECTANGLE around the player level badge
5. Save the rectangle dimensions and offsets from "Power" center

The scanner will then:
- Find all "Power" instances
- Crop the SAME SIZED rectangle at the calibrated offset for each
- OCR only that fixed window
- Save debug images of each cropped window
"""

import cv2
import numpy as np
import json
import os
import pytesseract
from window_capture import WindowCapture
from config import SCRIPT_DIR

class ArenaWindowCalibrator:
    def __init__(self):
        self.window_capture = WindowCapture('Raid: Shadow Legends')
        self.screenshot = None
        self.display_img = None

        # Region selection for opponent list
        self.opponent_region_start = None
        self.opponent_region_end = None
        self.opponent_region = None

        # Detected Power locations
        self.power_locations = []

        # Rectangle drawing for team power window
        self.team_power_rect_start = None
        self.team_power_rect_end = None
        self.team_power_rect = None

        # Rectangle drawing for level window
        self.level_rect_start = None
        self.level_rect_end = None
        self.level_rect = None

        # Calibration data
        self.calibration = None

        # Mode state machine
        self.mode = 'select_opponent_region'  # -> 'draw_team_power' -> 'draw_level' -> 'done'

    def detect_power_text(self, region_img, offset_x=0, offset_y=0):
        """Auto-detect all 'Power' text instances in the opponent list region"""
        gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        upscaled = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        try:
            ocr_result = pytesseract.image_to_data(
                upscaled,
                config='--psm 6',
                output_type=pytesseract.Output.DICT
            )
        except Exception as e:
            print(f"❌ OCR failed: {e}")
            return []

        power_locations = []
        for i, text in enumerate(ocr_result['text']):
            if not text:
                continue

            text_lower = text.lower()
            if 'power' in text_lower or 'fower' in text_lower or 'pover' in text_lower:
                # Scale back to original size and add offset
                x = (ocr_result['left'][i] // 2) + offset_x
                y = (ocr_result['top'][i] // 2) + offset_y
                w = ocr_result['width'][i] // 2
                h = ocr_result['height'][i] // 2

                power_locations.append({
                    'x': x,
                    'y': y,
                    'w': w,
                    'h': h,
                    'center_x': x + w // 2,
                    'center_y': y + h // 2
                })

                print(f"  ✓ Found 'Power' at ({x}, {y}) center ({x + w // 2}, {y + h // 2})")

        return power_locations

    def mouse_callback(self, event, x, y, flags, param):
        # Mode 1: Select opponent list region
        if self.mode == 'select_opponent_region':
            if event == cv2.EVENT_LBUTTONDOWN:
                self.opponent_region_start = (x, y)
                print(f"Opponent region start: ({x}, {y})")
            elif event == cv2.EVENT_LBUTTONUP:
                if self.opponent_region_start:
                    x1, y1 = self.opponent_region_start
                    x2, y2 = x, y

                    self.opponent_region = (
                        min(x1, x2), min(y1, y2),
                        max(x1, x2), max(y1, y2)
                    )
                    self.opponent_region_end = (x, y)

                    print(f"Opponent region: {self.opponent_region}")
                    print("Detecting 'Power' text...")

                    # Extract region and find Power
                    rx1, ry1, rx2, ry2 = self.opponent_region
                    region_img = self.screenshot[ry1:ry2, rx1:rx2].copy()
                    self.power_locations = self.detect_power_text(region_img, rx1, ry1)

                    if not self.power_locations:
                        print("❌ No 'Power' found! Try again.")
                        self.opponent_region_start = None
                        self.opponent_region_end = None
                        self.opponent_region = None
                    else:
                        print(f"✓ Found {len(self.power_locations)} 'Power' instances")
                        print(f"→ Now DRAW A RECTANGLE around the TEAM POWER NUMBER for Power #1")
                        self.mode = 'draw_team_power'
            return

        # Mode 2: Draw rectangle around team power window
        if self.mode == 'draw_team_power':
            if event == cv2.EVENT_LBUTTONDOWN:
                self.team_power_rect_start = (x, y)
                print(f"Team Power rect start: ({x}, {y})")
            elif event == cv2.EVENT_LBUTTONUP:
                if self.team_power_rect_start:
                    x1, y1 = self.team_power_rect_start
                    x2, y2 = x, y

                    self.team_power_rect = (
                        min(x1, x2), min(y1, y2),
                        max(x1, x2), max(y1, y2)
                    )
                    self.team_power_rect_end = (x, y)

                    rx1, ry1, rx2, ry2 = self.team_power_rect
                    width = rx2 - rx1
                    height = ry2 - ry1

                    # Calculate offset from Power center
                    power = self.power_locations[0]
                    offset_x = rx1 - power['center_x']
                    offset_y = ry1 - power['center_y']

                    print(f"Team Power window: {width}x{height} at offset ({offset_x:+d}, {offset_y:+d}) from Power center")
                    print(f"→ Now DRAW A RECTANGLE around the PLAYER LEVEL BADGE")
                    self.mode = 'draw_level'
            return

        # Mode 3: Draw rectangle around level window
        if self.mode == 'draw_level':
            if event == cv2.EVENT_LBUTTONDOWN:
                self.level_rect_start = (x, y)
                print(f"Level rect start: ({x}, {y})")
            elif event == cv2.EVENT_LBUTTONUP:
                if self.level_rect_start:
                    x1, y1 = self.level_rect_start
                    x2, y2 = x, y

                    self.level_rect = (
                        min(x1, x2), min(y1, y2),
                        max(x1, x2), max(y1, y2)
                    )
                    self.level_rect_end = (x, y)

                    lx1, ly1, lx2, ly2 = self.level_rect
                    width = lx2 - lx1
                    height = ly2 - ly1

                    # Calculate offset from Power center
                    power = self.power_locations[0]
                    offset_x = lx1 - power['center_x']
                    offset_y = ly1 - power['center_y']

                    print(f"Level window: {width}x{height} at offset ({offset_x:+d}, {offset_y:+d}) from Power center")

                    # Build calibration data
                    tp_x1, tp_y1, tp_x2, tp_y2 = self.team_power_rect
                    self.calibration = {
                        'team_power_window': {
                            'offset_x': tp_x1 - power['center_x'],
                            'offset_y': tp_y1 - power['center_y'],
                            'width': tp_x2 - tp_x1,
                            'height': tp_y2 - tp_y1
                        },
                        'level_window': {
                            'offset_x': lx1 - power['center_x'],
                            'offset_y': ly1 - power['center_y'],
                            'width': lx2 - lx1,
                            'height': ly2 - ly1
                        },
                        'reference_power_center': (power['center_x'], power['center_y'])
                    }

                    print(f"\n{'='*60}")
                    print(f"✓ Calibration complete!")
                    print(f"Team Power: {self.calibration['team_power_window']['width']}x{self.calibration['team_power_window']['height']} "
                          f"at ({self.calibration['team_power_window']['offset_x']:+d}, {self.calibration['team_power_window']['offset_y']:+d})")
                    print(f"Level: {self.calibration['level_window']['width']}x{self.calibration['level_window']['height']} "
                          f"at ({self.calibration['level_window']['offset_x']:+d}, {self.calibration['level_window']['offset_y']:+d})")
                    print(f"Press 's' to save calibration")
                    print(f"{'='*60}\n")

                    self.mode = 'done'
            return

    def save_calibration(self):
        """Save calibration to JSON"""
        if not self.calibration:
            print("❌ No calibration to save!")
            return False

        output_path = os.path.join(SCRIPT_DIR, 'arena_ocr_calibration.json')
        with open(output_path, 'w') as f:
            json.dump(self.calibration, f, indent=2)

        print(f"\n{'='*60}")
        print(f"✓ Calibration saved to: {output_path}")
        print(f"{'='*60}\n")

        return True

    def draw_rectangles_preview(self, img):
        """Draw preview rectangles for all detected Power instances"""
        if not self.power_locations or not self.calibration:
            return

        tp_win = self.calibration['team_power_window']
        lv_win = self.calibration['level_window']

        for i, power in enumerate(self.power_locations):
            px, py = power['center_x'], power['center_y']

            # Team power window
            tp_x1 = px + tp_win['offset_x']
            tp_y1 = py + tp_win['offset_y']
            tp_x2 = tp_x1 + tp_win['width']
            tp_y2 = tp_y1 + tp_win['height']

            # Level window
            lv_x1 = px + lv_win['offset_x']
            lv_y1 = py + lv_win['offset_y']
            lv_x2 = lv_x1 + lv_win['width']
            lv_y2 = lv_y1 + lv_win['height']

            # Draw
            color_tp = (255, 0, 0) if i == 0 else (255, 128, 0)
            color_lv = (0, 0, 255) if i == 0 else (128, 0, 255)

            cv2.rectangle(img, (tp_x1, tp_y1), (tp_x2, tp_y2), color_tp, 2)
            cv2.rectangle(img, (lv_x1, lv_y1), (lv_x2, lv_y2), color_lv, 2)

            # Power center marker
            cv2.circle(img, (px, py), 3, (0, 255, 0), -1)

    def run(self):
        """Main calibration loop"""
        print("="*60)
        print("Arena OCR Window Calibration Tool")
        print("="*60)
        print("\nWorkflow:")
        print("1. Draw rectangle around opponent list area")
        print("2. Tool auto-detects all 'Power' text")
        print("3. DRAW RECTANGLE around team power number (for first Power)")
        print("4. DRAW RECTANGLE around player level badge")
        print("5. Press 's' to save calibration")
        print("="*60)

        print("\nCapturing game window...")
        self.screenshot = self.window_capture.capture()
        if self.screenshot is None:
            print("❌ Could not capture game window!")
            return

        print("✓ Window captured!")
        print("→ DRAW RECTANGLE around the opponent list area\n")

        self.display_img = self.screenshot.copy()

        window_name = "Arena Window Calibration (s=save, r=reset, q=quit)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, self.mouse_callback)

        while True:
            display = self.display_img.copy()

            # Draw opponent region
            if self.opponent_region:
                x1, y1, x2, y2 = self.opponent_region
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw Power boxes
            for power in self.power_locations:
                cv2.rectangle(display,
                            (power['x'], power['y']),
                            (power['x'] + power['w'], power['y'] + power['h']),
                            (0, 255, 0), 2)

            # Draw team power rectangle
            if self.team_power_rect:
                x1, y1, x2, y2 = self.team_power_rect
                cv2.rectangle(display, (x1, y1), (x2, y2), (255, 0, 0), 3)
                cv2.putText(display, "Team Power", (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            # Draw level rectangle
            if self.level_rect:
                x1, y1, x2, y2 = self.level_rect
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(display, "Level", (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

            # Draw preview on all Power instances if calibrated
            if self.mode == 'done':
                self.draw_rectangles_preview(display)

            # Instruction overlay
            instruction_text = ""
            if self.mode == 'select_opponent_region':
                instruction_text = "Draw rectangle around opponent list area"
            elif self.mode == 'draw_team_power':
                instruction_text = "Draw rectangle around TEAM POWER NUMBER"
            elif self.mode == 'draw_level':
                instruction_text = "Draw rectangle around PLAYER LEVEL BADGE"
            elif self.mode == 'done':
                instruction_text = "Calibration complete! Press 's' to save, 'r' to reset"

            overlay = display.copy()
            cv2.rectangle(overlay, (10, 10), (900, 50), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, display, 0.3, 0, display)
            cv2.putText(display, instruction_text, (20, 35),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cv2.imshow(window_name, display)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                print("\nQuitting...")
                break
            elif key == ord('s'):
                if self.save_calibration():
                    print("Calibration saved!")
                    break
            elif key == ord('r'):
                print("\nResetting...")
                self.__init__()
                self.screenshot = self.window_capture.capture()
                self.display_img = self.screenshot.copy()
                print("→ Draw rectangle around opponent list area\n")

        cv2.destroyAllWindows()

if __name__ == '__main__':
    calibrator = ArenaWindowCalibrator()
    calibrator.run()
