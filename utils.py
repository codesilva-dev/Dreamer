import os
from PyQt5.QtWidgets import QMessageBox, QApplication
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt

import numpy as np

def log_message(widget, message):
    widget.log_output.append(message)
    QApplication.processEvents()

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
