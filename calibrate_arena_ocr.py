#!/usr/bin/env python3
"""
Arena OCR Calibration Tool

This tool helps you calibrate the exact pixel offsets for:
1. Team Power numbers (relative to "Power" text)
2. Player Level badges (relative to "Power" text)

Workflow:
1. Takes a screenshot of Classic Arena opponent list
2. Automatically detects all instances of "Power" text using OCR
3. For each detected "Power", you click where the team power number and level are
4. Calculates average offsets to use for all future OCR

Usage:
1. Navigate to Classic Arena in-game (so opponent list is visible)
2. Run this script
3. The tool will automatically find all "Power" text instances
4. For each detected "Power" (green box), click where the team power NUMBER starts
5. Then click where the player LEVEL badge is
6. Repeat for all detected "Power" instances
7. Press 's' to save calibration, 'q' to quit
"""

import cv2
import numpy as np
import json
import os
import pytesseract
from window_capture import WindowCapture
from config import SCRIPT_DIR

class ArenaOCRCalibrator:
    def __init__(self):
        self.window_capture = WindowCapture('Raid: Shadow Legends')
        self.calibration_points = []
        self.power_locations = []  # Auto-detected "Power" locations
        self.current_power_index = 0
        self.mode = 'select_region'  # 'select_region' -> 'mark_team_power' -> 'mark_level'
        self.screenshot = None
        self.display_img = None

        # Region selection
        self.region_start = None
        self.region_end = None
        self.selected_region = None

    def detect_power_text_in_region(self, region_img, offset_x=0, offset_y=0):
        """Detect 'Power' text in a specific image region"""
        # Convert to grayscale and apply threshold
        gray = cv2.cvtColor(region_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

        # Upscale for better OCR
        upscaled = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        # Run OCR to find "Power" text
        ocr_config = '--psm 6'
        try:
            ocr_result = pytesseract.image_to_data(
                upscaled,
                config=ocr_config,
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
            if 'power' in text_lower or 'fower' in text_lower:
                # Scale back to original size and add region offset
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

                print(f"  ✓ Found 'Power' at ({x}, {y}) size {w}x{h}")

        return power_locations

    def mouse_callback(self, event, x, y, flags, param):
        # Region selection mode
        if self.mode == 'select_region':
            if event == cv2.EVENT_LBUTTONDOWN:
                self.region_start = (x, y)
                print(f"Region start: ({x}, {y})")
            elif event == cv2.EVENT_LBUTTONUP:
                if self.region_start:
                    self.region_end = (x, y)
                    x1, y1 = self.region_start
                    x2, y2 = self.region_end

                    # Normalize coordinates
                    self.selected_region = (
                        min(x1, x2), min(y1, y2),
                        max(x1, x2), max(y1, y2)
                    )

                    print(f"Region selected: {self.selected_region}")
                    print("Detecting 'Power' text in selected region...")

                    # Extract region and detect Power
                    x1, y1, x2, y2 = self.selected_region
                    region_img = self.screenshot[y1:y2, x1:x2].copy()

                    # Detect power in this region
                    self.power_locations = self.detect_power_text_in_region(region_img, x1, y1)

                    if not self.power_locations:
                        print("❌ No 'Power' text found in region! Try again.")
                        self.region_start = None
                        self.region_end = None
                        self.selected_region = None
                    else:
                        print(f"✓ Found {len(self.power_locations)} instances")
                        print("Click where the TEAM POWER NUMBER starts\n")
                        self.mode = 'mark_team_power'

            elif event == cv2.EVENT_MOUSEMOVE:
                if self.region_start and not self.region_end:
                    # Draw preview rectangle
                    pass  # Handled in main loop
            return

        # Calibration mode
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(self.calibration_points) > 0:
                print("✓ Already calibrated! Press 's' to save or 'r' to reset.")
                return

            if not self.power_locations:
                print("❌ No 'Power' text detected!")
                return

            # Use the first detected "Power" as reference
            current_power = self.power_locations[0]
            power_x = current_power['center_x']
            power_y = current_power['center_y']

            if self.mode == 'mark_team_power':
                # User clicked where team power number starts
                current_power['team_power_x'] = x
                current_power['team_power_y'] = y

                offset_x = x - power_x
                offset_y = y - power_y

                print(f"✓ Team Power: ({x}, {y}), offset: ({offset_x:+d}, {offset_y:+d}) px from Power")
                print("  → Now click on the PLAYER LEVEL badge (on the left side)")
                self.mode = 'mark_level'

                # Draw marker
                cv2.circle(self.display_img, (x, y), 5, (255, 0, 0), -1)
                cv2.putText(self.display_img, "Power#", (x + 10, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                cv2.line(self.display_img, (power_x, power_y), (x, y), (255, 255, 0), 2)

            elif self.mode == 'mark_level':
                # User clicked on player level badge
                offset_x = x - power_x
                offset_y = y - power_y

                # Save the single calibration point
                offset_data = {
                    'power_pos': (power_x, power_y),
                    'team_power_offset': (current_power['team_power_x'] - power_x,
                                         current_power['team_power_y'] - power_y),
                    'level_offset': (offset_x, offset_y),
                }

                self.calibration_points.append(offset_data)

                print(f"✓ Level: ({x}, {y}), offset: ({offset_x:+d}, {offset_y:+d}) px from Power")
                print(f"\n{'='*60}")
                print(f"✓ Calibration complete!")
                print(f"  Team Power offset: ({offset_data['team_power_offset'][0]:+d}, {offset_data['team_power_offset'][1]:+d})")
                print(f"  Level offset: ({offset_x:+d}, {offset_y:+d})")
                print(f"  Press 's' to save calibration")
                print(f"{'='*60}\n")

                # Draw marker
                cv2.circle(self.display_img, (x, y), 5, (0, 0, 255), -1)
                cv2.putText(self.display_img, "Level", (x + 10, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                cv2.line(self.display_img, (power_x, power_y), (x, y), (255, 0, 255), 2)

                # Draw preview on all other "Power" instances
                for i, power in enumerate(self.power_locations):
                    if i == 0:
                        continue  # Skip the one we just calibrated

                    px = power['center_x']
                    py = power['center_y']

                    # Draw predicted team power location
                    tp_x = px + offset_data['team_power_offset'][0]
                    tp_y = py + offset_data['team_power_offset'][1]
                    cv2.circle(self.display_img, (tp_x, tp_y), 3, (255, 128, 0), -1)

                    # Draw predicted level location
                    lv_x = px + offset_x
                    lv_y = py + offset_y
                    cv2.circle(self.display_img, (lv_x, lv_y), 3, (128, 0, 255), -1)

    def get_calibration_data(self):
        """Get calibration data from the single calibration point"""
        if not self.calibration_points:
            return None

        point = self.calibration_points[0]

        return {
            'team_power_offset_x': point['team_power_offset'][0],
            'team_power_offset_y': point['team_power_offset'][1],
            'level_offset_x': point['level_offset'][0],
            'level_offset_y': point['level_offset'][1],
            'calibrated_power_pos': point['power_pos']
        }

    def save_calibration(self):
        """Save calibration data to JSON file"""
        if not self.calibration_points:
            print("❌ No calibration to save!")
            return False

        data = self.get_calibration_data()

        output_path = os.path.join(SCRIPT_DIR, 'arena_ocr_calibration.json')
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n{'='*60}")
        print(f"✓ Calibration saved to: {output_path}")
        print(f"{'='*60}")
        print(f"Offsets from 'Power' text:")
        print(f"  • Team Power number: X={data['team_power_offset_x']:+d}, Y={data['team_power_offset_y']:+d}")
        print(f"  • Player Level badge: X={data['level_offset_x']:+d}, Y={data['level_offset_y']:+d}")
        print(f"{'='*60}\n")

        return True

    def draw_power_boxes(self, img):
        """Draw boxes around detected 'Power' text"""
        for i, power in enumerate(self.power_locations):
            # Color: green for current, gray for others
            if i == self.current_power_index:
                color = (0, 255, 0)  # Green - current
                thickness = 3
            elif i < self.current_power_index:
                color = (128, 128, 128)  # Gray - already calibrated
                thickness = 2
            else:
                color = (255, 255, 0)  # Yellow - pending
                thickness = 2

            cv2.rectangle(img,
                         (power['x'], power['y']),
                         (power['x'] + power['w'], power['y'] + power['h']),
                         color, thickness)

            # Label
            label = f"#{i+1}"
            cv2.putText(img, label,
                       (power['x'], power['y'] - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    def run(self):
        """Main calibration loop"""
        print("="*60)
        print("Arena OCR Calibration Tool")
        print("="*60)
        print("\nInstructions:")
        print("1. Make sure Raid: Shadow Legends is open to Classic Arena")
        print("2. Draw a rectangle around the opponent list area")
        print("3. The tool will detect all 'Power' text in that area")
        print("4. Click where ONE team power NUMBER starts (e.g., '3' in '300.55K')")
        print("5. Click where the player LEVEL badge is (on the left side)")
        print("6. Press 's' to save calibration, 'r' to reset, 'q' to quit")
        print("="*60)

        # Capture screenshot
        print("\nCapturing game window...")
        self.screenshot = self.window_capture.capture()
        if self.screenshot is None:
            print("❌ Could not capture game window!")
            return

        print("✓ Window captured!")
        print("→ Click and drag to select the opponent list area\n")

        self.display_img = self.screenshot.copy()

        # Create window
        window_name = "Arena OCR Calibration (s=save, q=quit)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, self.mouse_callback)

        while True:
            # Draw on a fresh copy
            display = self.display_img.copy()

            # Draw region selection
            if self.mode == 'select_region':
                if self.region_start:
                    # Get current mouse position for preview
                    x, y, w, h = cv2.getWindowImageRect(window_name)
                    # Draw selection rectangle
                    if self.region_end:
                        x1, y1 = self.region_start
                        x2, y2 = self.region_end
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    # else: Live preview handled by mousemove

            # Draw selected region outline
            if self.selected_region:
                x1, y1, x2, y2 = self.selected_region
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 3)

            # Draw boxes around all detected "Power" instances
            if self.mode != 'select_region':
                self.draw_power_boxes(display)

            # Add instruction overlay
            instruction_text = ""
            if self.mode == 'select_region':
                instruction_text = "Click and drag to select opponent list area"
            elif self.mode == 'mark_team_power':
                instruction_text = "Click where Team Power NUMBER starts (e.g., '3' in '300.55K')"
            elif self.mode == 'mark_level':
                instruction_text = "Click on Player Level badge (on the left)"
            elif len(self.calibration_points) > 0:
                instruction_text = "Calibration complete! Press 's' to save, 'r' to reset"

            # Semi-transparent instruction box
            overlay = display.copy()
            cv2.rectangle(overlay, (10, 10), (800, 50), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, display, 0.3, 0, display)
            cv2.putText(display, instruction_text, (20, 35),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cv2.imshow(window_name, display)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                print("\nQuitting without saving...")
                break
            elif key == ord('s'):
                if self.save_calibration():
                    print("Calibration saved successfully!")
                    break
                else:
                    print("Complete calibration before saving!")
            elif key == ord('r'):
                print("\nResetting calibration...")
                self.calibration_points = []
                self.power_locations = []
                self.mode = 'select_region'
                self.region_start = None
                self.region_end = None
                self.selected_region = None
                self.display_img = self.screenshot.copy()
                print("→ Select opponent list area again\n")

        cv2.destroyAllWindows()

if __name__ == '__main__':
    calibrator = ArenaOCRCalibrator()
    calibrator.run()
