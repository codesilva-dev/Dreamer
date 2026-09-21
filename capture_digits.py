"""
Interactive Digit Template Capture Tool

Captures the level region from the live game window, applies HSV
filtering, finds digit-sized blobs via connected component analysis,
and shows each one for manual labeling.

Controls:
  0-9  = Save this crop as that digit
  S    = Skip (don't save)
  Q    = Quit

Saved templates go to digit_templates/{digit}.png
Multiple samples of the same digit are saved as {digit}.png,
{digit}_1.png, {digit}_2.png, etc. Only the best/cleanest one
needs to be kept — delete the rest after capture.

Usage:
    1. Have Raid: Shadow Legends open on the Classic Arena screen
    2. Run: python capture_digits.py
    3. Label each digit crop that appears
    4. Review digit_templates/ and keep the cleanest sample per digit
"""

import cv2
import numpy as np
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))
import config
from window_capture import WindowCapture

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'digit_templates')
PRE_SCALE = 3
# Standard height to normalize all digit templates to
TEMPLATE_HEIGHT = 32  # pixels at 3x scale


def capture_level_region():
    """Capture the level region from the game window."""
    wc = WindowCapture(config.GAME_WINDOW_TITLE)
    window_info = wc.get_window()
    if not window_info:
        print("Game window not found!")
        return None

    left, top, w_width, w_height = window_info
    print(f"Window: ({left}, {top}) {w_width}x{w_height}")

    # Capture the level region
    region = config.FLUID_LEVEL_REGION
    x = int(left + region['x_start'] * w_width)
    y = int(top + region['y_start'] * w_height)
    w = int(region['width'] * w_width)
    h = int(region['height'] * w_height)

    screenshot = np.array(
        __import__('PIL.ImageGrab', fromlist=['grab']).grab(bbox=(x, y, x + w, y + h))
    )
    # PIL gives RGB, convert to BGR for OpenCV
    image = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
    print(f"Captured level region: {image.shape[1]}x{image.shape[0]}")
    return image


def extract_digit_crops(image):
    """
    Apply HSV filtering and extract individual digit crops.

    Returns list of dicts with 'crop' (image), 'x', 'y' (position in
    upscaled image).
    """
    # Upscale 3x
    upscaled = cv2.resize(image, None, fx=PRE_SCALE, fy=PRE_SCALE,
                          interpolation=cv2.INTER_CUBIC)
    height, width = upscaled.shape[:2]

    # HSV filter (relaxed - capture full digit edges)
    hsv = cv2.cvtColor(upscaled, cv2.COLOR_BGR2HSV)
    white_mask = (hsv[:, :, 2] > 180) & (hsv[:, :, 1] < 80)
    filtered = np.where(white_mask, 255, 0).astype(np.uint8)

    # Skip left 10% (frame noise)
    x_crop_start = int(width * 0.10)
    work_area = filtered[:, x_crop_start:]

    # Connected component analysis on the full filtered image
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        work_area, connectivity=8)

    crops = []
    for lbl in range(1, num_labels):
        area = stats[lbl, cv2.CC_STAT_AREA]
        x = stats[lbl, cv2.CC_STAT_LEFT]
        y = stats[lbl, cv2.CC_STAT_TOP]
        w = stats[lbl, cv2.CC_STAT_WIDTH]
        h = stats[lbl, cv2.CC_STAT_HEIGHT]

        # Filter for digit-sized components at 3x scale:
        # - Area: digits have 40-500px at 3x scale
        # - Height: 15-45px (5-15px original * 3)
        # - Width: 6-35px (2-12px original * 3)
        # - Aspect ratio: digits are taller than wide (h/w > 0.8)
        if (area >= 40 and
            15 <= h <= 50 and
            6 <= w <= 40 and
            h / max(w, 1) >= 0.5):

            # Crop with 2px padding
            pad = 2
            cx = max(0, x - pad)
            cy = max(0, y - pad)
            cw = min(work_area.shape[1] - cx, w + 2 * pad)
            ch = min(work_area.shape[0] - cy, h + 2 * pad)

            digit_crop = work_area[cy:cy + ch, cx:cx + cw].copy()

            crops.append({
                'crop': digit_crop,
                'x': x + x_crop_start,
                'y': y,
                'w': w,
                'h': h,
                'area': area,
            })

    # Sort top-to-bottom, then left-to-right
    crops.sort(key=lambda c: (c['y'] // 30, c['x']))

    return crops, filtered, upscaled


def normalize_digit(crop, target_height=TEMPLATE_HEIGHT):
    """
    Normalize a digit crop to a standard height while preserving
    aspect ratio. Adds black padding to center the digit.
    """
    h, w = crop.shape[:2]
    if h == 0 or w == 0:
        return crop

    # Scale to target height
    scale = target_height / h
    new_w = max(1, int(w * scale))
    resized = cv2.resize(crop, (new_w, target_height),
                         interpolation=cv2.INTER_CUBIC)

    # Threshold to clean up interpolation artifacts
    _, resized = cv2.threshold(resized, 127, 255, cv2.THRESH_BINARY)

    return resized


def save_digit(crop, digit_label):
    """Save a digit crop to digit_templates/{digit}.png"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Normalize to standard height
    normalized = normalize_digit(crop)

    # Find next available filename
    base = os.path.join(OUTPUT_DIR, f"{digit_label}.png")
    if not os.path.exists(base):
        path = base
    else:
        idx = 1
        while True:
            path = os.path.join(OUTPUT_DIR, f"{digit_label}_{idx}.png")
            if not os.path.exists(path):
                break
            idx += 1

    cv2.imwrite(path, normalized)
    print(f"  Saved {path} ({normalized.shape[1]}x{normalized.shape[0]})")
    return path


def main():
    print("=== Digit Template Capture Tool ===")
    print("Make sure Raid: Shadow Legends is on the Classic Arena screen.")
    print()

    # Clean up old auto-harvested templates
    old_subdirs = [os.path.join(OUTPUT_DIR, str(d)) for d in range(10)]
    for d in old_subdirs:
        if os.path.isdir(d):
            import shutil
            shutil.rmtree(d)
            print(f"  Cleaned up old subdir: {d}")

    print("Capturing in 2 seconds...")
    time.sleep(2)

    image = capture_level_region()
    if image is None:
        return

    crops, filtered, upscaled = extract_digit_crops(image)
    print(f"\nFound {len(crops)} digit-sized components")

    if not crops:
        print("No digits found. Make sure you're on the arena screen.")
        return

    # Show overview
    overview = cv2.cvtColor(filtered, cv2.COLOR_GRAY2BGR)
    for i, c in enumerate(crops):
        cv2.rectangle(overview, (c['x'], c['y']),
                      (c['x'] + c['w'], c['y'] + c['h']),
                      (0, 255, 0), 1)
        cv2.putText(overview, str(i + 1), (c['x'], c['y'] - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)

    # Resize overview for display
    display_h = 800
    scale = display_h / overview.shape[0]
    overview_display = cv2.resize(overview, None, fx=scale, fy=scale,
                                  interpolation=cv2.INTER_NEAREST)
    cv2.imshow('Overview - all detected components', overview_display)

    print(f"\nLabeling {len(crops)} crops...")
    print("Press 0-9 to label, S to skip, Q to quit")
    print()

    saved_count = 0
    for i, crop_info in enumerate(crops):
        crop = crop_info['crop']

        # Show the digit enlarged
        display_size = 200
        enlarged = cv2.resize(crop, (display_size, display_size),
                              interpolation=cv2.INTER_NEAREST)
        # Convert to color for display
        if len(enlarged.shape) == 2:
            enlarged = cv2.cvtColor(enlarged, cv2.COLOR_GRAY2BGR)

        # Add info text
        info = f"Crop {i + 1}/{len(crops)} | {crop.shape[1]}x{crop.shape[0]}px | area={crop_info['area']}"
        cv2.putText(enlarged, info, (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 200, 200), 1)
        cv2.putText(enlarged, "0-9=label  S=skip  Q=quit", (5, 190),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 200, 200), 1)

        cv2.imshow('Digit to label', enlarged)
        key = cv2.waitKey(0) & 0xFF

        if key == ord('q') or key == ord('Q'):
            print("Quit.")
            break
        elif key == ord('s') or key == ord('S'):
            print(f"  Crop {i + 1}: skipped")
            continue
        elif ord('0') <= key <= ord('9'):
            digit = chr(key)
            save_digit(crop, digit)
            saved_count += 1
        else:
            print(f"  Crop {i + 1}: unrecognized key, skipping")

    cv2.destroyAllWindows()

    print(f"\n=== Done! Saved {saved_count} digit templates to {OUTPUT_DIR}/ ===")
    print("Review the templates and keep only the cleanest one per digit.")
    print("Delete duplicates (e.g. keep 5.png, delete 5_1.png, 5_2.png)")


if __name__ == '__main__':
    main()
