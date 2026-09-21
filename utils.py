import os
import logging
from datetime import datetime
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt

import numpy as np

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
        handler = logging.FileHandler(filepath, mode='w', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s  %(message)s', datefmt='%H:%M:%S'))
        _file_logger.addHandler(handler)

    return _file_logger


def log_message(widget, message):
    widget.log_output.append(message)
    QApplication.processEvents()
    # Also write to log file
    _get_file_logger().info(message)

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
