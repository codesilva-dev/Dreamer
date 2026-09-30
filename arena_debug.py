"""
Shared arena debug capture — single global counter so all photos
from scanner, battle, and sequence sort in true execution order.
"""

import os
import cv2
from config import SCRIPT_DIR

_counter = 0
_debug_dir = os.path.join(SCRIPT_DIR, 'debug', 'arena_captures')


def reset():
    """Reset counter and clear the captures folder. Call once per scan session."""
    global _counter
    _counter = 0
    if os.path.exists(_debug_dir):
        for f in os.listdir(_debug_dir):
            if f.endswith('.png'):
                try:
                    os.remove(os.path.join(_debug_dir, f))
                except OSError:
                    pass


def save(frame, label):
    """Save a debug screenshot with a globally sequential number."""
    global _counter
    if frame is None:
        return
    if frame.size == 0:
        # Create a small red placeholder so missing crops are visible
        _counter += 1
        os.makedirs(_debug_dir, exist_ok=True)
        import numpy as np
        placeholder = np.zeros((20, 100, 3), dtype=np.uint8)
        placeholder[:, :, 2] = 255  # Red
        cv2.putText(placeholder, "EMPTY", (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        filename = f"{_counter:04d}_{label}_EMPTY.png"
        cv2.imwrite(os.path.join(_debug_dir, filename), placeholder)
        return
    _counter += 1
    os.makedirs(_debug_dir, exist_ok=True)
    filename = f"{_counter:04d}_{label}.png"
    cv2.imwrite(os.path.join(_debug_dir, filename), frame)
