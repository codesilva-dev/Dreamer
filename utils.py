import os
import logging
from datetime import datetime
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtGui import QPixmap, QImage, QCursor
from PyQt5.QtCore import Qt

import numpy as np
import pyautogui

# ── File logger setup ──────────────────────────────────────────────
_file_logger = None

def _get_file_logger():
    """Lazily create a file logger that writes to logs/dreamer_<date>.log"""
    global _file_logger
    if _file_logger is not None:
        return _file_logger

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    filename = f'dreamer_{datetime.now():%Y-%m-%d}.log'
    filepath = os.path.join(log_dir, filename)

    _file_logger = logging.getLogger('dreamer')
    _file_logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if called more than once
    if not _file_logger.handlers:
        fmt = logging.Formatter('%(asctime)s  %(message)s', datefmt='%H:%M:%S')

        file_handler = logging.FileHandler(filepath, mode='w', encoding='utf-8')
        file_handler.setFormatter(fmt)
        _file_logger.addHandler(file_handler)

        # Also log to stdout (visible when running from terminal)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(fmt)
        _file_logger.addHandler(console_handler)

    return _file_logger


def log_message(widget, message):
    widget.log_output.append(message)
    QApplication.processEvents()
    # Also write to log file — flush immediately so logs survive a forced kill
    logger = _get_file_logger()
    logger.info(message)
    for handler in logger.handlers:
        handler.flush()

def show_preview(image_label, frame):
    height, width, channel = frame.shape
    bytes_per_line = 3 * width
    frame_contiguous = np.ascontiguousarray(frame)
    q_img = QImage(frame_contiguous.data.tobytes(), width, height, bytes_per_line, QImage.Format_BGR888)
    pixmap = QPixmap.fromImage(q_img)
    image_label.setPixmap(pixmap.scaled(image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

def show_error(parent, message):
    QMessageBox.critical(parent, 'Error', message)

def show_info(parent, message):
    QMessageBox.information(parent, 'Info', message)

def reset_home_screen_zoom(window_capture, clicker):
    """
    Reset home screen zoom by performing a drag upward.

    This prevents zoom-related template matching issues by ensuring
    the home screen is at the correct zoom level. Performs a hold-click
    and drags upward ~500 pixels.

    Args:
        window_capture: WindowCapture instance to get window position
        clicker: NaturalClick instance for delays
    """
    left, top, width, height = window_capture.window_info

    # Click in the center of the screen
    center_x = left + (width // 2)
    center_y = top + (height // 2)

    # Drag upward 500 pixels
    end_y = center_y - 500

    # Perform the drag
    pyautogui.moveTo(center_x, center_y)
    clicker.natural_delay(0.1)
    pyautogui.mouseDown()
    clicker.natural_delay(0.1)
    # Drag upward with duration so game registers it
    pyautogui.moveTo(center_x, end_y, duration=0.5)
    clicker.natural_delay(0.2)
    pyautogui.mouseUp()
    clicker.natural_delay(0.5)


# ── Cursor hiding ──────────────────────────────────────────────────

def hide_cursor():
    """Hide the mouse cursor globally."""
    QApplication.setOverrideCursor(Qt.BlankCursor)


def show_cursor():
    """Restore the mouse cursor."""
    QApplication.restoreOverrideCursor()
