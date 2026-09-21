"""
Digit Template Harvester for Level OCR

Processes saved level region images from debug/ to extract individual
digit templates. Uses the same HSV filtering pipeline as the level
scanner, then connected component analysis to isolate each digit.

Saves cropped digit images to digit_templates/ for review and labeling.
Each digit is saved as digit_templates/frame_pos_idx.png with the
expected label in the filename for easy verification.

Usage:
    python harvest_digits.py

Then manually review the output in digit_templates/ and rename any
incorrect files. Once verified, the digit templates can be used for
template-based digit matching instead of Tesseract OCR.
"""

import cv2
import numpy as np
import os

# Known ground truth from consistent OCR reads across multiple runs:
# Format: (image_file, list_of_levels_top_to_bottom)
GROUND_TRUTH = [
    ('level_region_initial_top.png', [66, 72, 86, 65]),
    ('level_region_scroll1.png', [86, 65, 72, 61]),
    ('level_region_scroll2.png', [61, 57, 80, 100]),
    ('level_region_scroll3.png', [57, 80, 100, 65]),  # 4th may not exist
]

DEBUG_DIR = os.path.join(os.path.dirname(__file__), 'debug')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'digit_templates')

PRE_SCALE = 3


def process_image(image_path, expected_levels):
    """Process a level region image and extract individual digits."""
    image = cv2.imread(image_path)
    if image is None:
        print(f"  Could not read {image_path}")
        return []

    orig_h, orig_w = image.shape[:2]
    print(f"  Image: {orig_w}x{orig_h}")

    # Upscale 3x before filtering (same as level scanner)
    upscaled = cv2.resize(image, None, fx=PRE_SCALE, fy=PRE_SCALE,
                          interpolation=cv2.INTER_CUBIC)
    height, width = upscaled.shape[:2]

    # HSV filter - use relaxed thresholds to capture full digit edges
    hsv = cv2.cvtColor(upscaled, cv2.COLOR_BGR2HSV)
    white_mask = (hsv[:, :, 2] > 180) & (hsv[:, :, 1] < 80)
    filtered = np.where(white_mask, 255, 0).astype(np.uint8)

    # Row projection to find level bands
    x_crop_start = int(width * 0.10)
    row_sums = filtered[:, x_crop_start:].sum(axis=1) // 255

    # Find bands
    bands = []
    in_band = False
    band_start = 0
    min_density = 3 * PRE_SCALE
    min_band_h = 6 * PRE_SCALE
    max_band_h = 24 * PRE_SCALE

    for y in range(height):
        if row_sums[y] >= min_density:
            if not in_band:
                band_start = y
                in_band = True
        else:
            if in_band:
                band_h = y - band_start
                if min_band_h <= band_h <= max_band_h:
                    bands.append((band_start, y))
                in_band = False
    if in_band:
        band_h = height - band_start
        if min_band_h <= band_h <= max_band_h:
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

    print(f"  Found {len(bands)} bands")

    digits_extracted = []

    for band_idx, (band_top, band_bot) in enumerate(bands):
        if band_idx >= len(expected_levels):
            break

        expected = expected_levels[band_idx]
        expected_digits = list(str(expected))

        # Extract the band with padding
        pad = 5
        crop_top = max(0, band_top - pad)
        crop_bot = min(height, band_bot + pad)
        band_img = filtered[crop_top:crop_bot, x_crop_start:]

        if band_img.shape[0] < 4 or band_img.shape[1] < 4:
            continue

        # Connected component analysis to find individual digits
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            band_img, connectivity=8)

        # Collect significant components (skip background label 0)
        components = []
        for lbl in range(1, num_labels):
            area = stats[lbl, cv2.CC_STAT_AREA]
            x = stats[lbl, cv2.CC_STAT_LEFT]
            y = stats[lbl, cv2.CC_STAT_TOP]
            w = stats[lbl, cv2.CC_STAT_WIDTH]
            h = stats[lbl, cv2.CC_STAT_HEIGHT]

            # Filter: digit components should be reasonably sized
            # At 3x scale, digits are ~10-20px wide, 20-40px tall
            if area >= 20 and h >= 8 and w >= 4:
                components.append({
                    'label': lbl, 'area': area,
                    'x': x, 'y': y, 'w': w, 'h': h,
                    'cx': centroids[lbl][0]
                })

        # Sort by X position (left to right = digit order)
        components.sort(key=lambda c: c['x'])

        # Merge components that overlap horizontally (parts of same digit)
        merged = []
        for comp in components:
            if merged and comp['x'] < merged[-1]['x'] + merged[-1]['w'] + 2:
                # Overlapping with previous - merge
                prev = merged[-1]
                new_x = min(prev['x'], comp['x'])
                new_y = min(prev['y'], comp['y'])
                new_right = max(prev['x'] + prev['w'], comp['x'] + comp['w'])
                new_bot = max(prev['y'] + prev['h'], comp['y'] + comp['h'])
                merged[-1] = {
                    'x': new_x, 'y': new_y,
                    'w': new_right - new_x, 'h': new_bot - new_y,
                    'labels': prev.get('labels', [prev['label']]) + [comp['label']],
                    'area': prev['area'] + comp['area'],
                }
            else:
                comp['labels'] = [comp['label']]
                merged.append(comp)

        print(f"  Band {band_idx + 1}: {len(merged)} digit components "
              f"(expected '{expected}' = {len(expected_digits)} digits)")

        if len(merged) != len(expected_digits):
            print(f"    WARNING: component count mismatch! Skipping.")
            # Save the full band for inspection anyway
            continue

        # Extract each digit
        for digit_idx, (comp, exp_digit) in enumerate(zip(merged, expected_digits)):
            # Crop the digit from the band image
            dx, dy = comp['x'], comp['y']
            dw, dh = comp['w'], comp['h']

            # Add 2px padding around the digit
            dx_start = max(0, dx - 2)
            dy_start = max(0, dy - 2)
            dx_end = min(band_img.shape[1], dx + dw + 2)
            dy_end = min(band_img.shape[0], dy + dh + 2)

            digit_crop = band_img[dy_start:dy_end, dx_start:dx_end]

            digits_extracted.append({
                'digit': exp_digit,
                'crop': digit_crop,
                'source_band': band_idx,
                'source_file': os.path.basename(image_path),
            })

    return digits_extracted


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Also create per-digit subdirectories
    for d in range(10):
        os.makedirs(os.path.join(OUTPUT_DIR, str(d)), exist_ok=True)

    all_digits = []

    for filename, expected_levels in GROUND_TRUTH:
        filepath = os.path.join(DEBUG_DIR, filename)
        print(f"\nProcessing {filename}...")

        if not os.path.exists(filepath):
            print(f"  File not found, skipping")
            continue

        digits = process_image(filepath, expected_levels)
        all_digits.extend(digits)

    # Save each extracted digit
    digit_counts = {}
    for d in all_digits:
        digit = d['digit']
        count = digit_counts.get(digit, 0)
        digit_counts[digit] = count + 1

        # Save to digit_templates/{digit}/{digit}_{count}.png
        outpath = os.path.join(OUTPUT_DIR, digit, f"{digit}_{count}.png")
        cv2.imwrite(outpath, d['crop'])
        print(f"  Saved {outpath} ({d['crop'].shape[1]}x{d['crop'].shape[0]}) "
              f"from {d['source_file']} band {d['source_band'] + 1}")

    print(f"\n=== Summary ===")
    print(f"Total digits extracted: {len(all_digits)}")
    for digit in sorted(digit_counts.keys()):
        print(f"  '{digit}': {digit_counts[digit]} samples")


if __name__ == '__main__':
    main()
