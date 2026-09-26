"""
Add Window Region Tool - Interactively define and save window regions for OCR/template matching.

Usage:
1. Run this script
2. Click and drag to select a region on the game window
3. Enter a name for the region
4. The region coordinates will be saved to windows.json and printed for use in code
"""

import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QPushButton, QLabel, QLineEdit,
                              QMessageBox)
from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor
from window_capture import WindowCapture
import json
import os


class WindowSelector(QWidget):
    """Overlay widget for selecting a region."""

    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.image = image
        self.start_point = None
        self.end_point = None
        self.selecting = False
        self.setMouseTracking(True)

        # Convert CV2 image to QImage for display
        height, width, channel = image.shape
        bytes_per_line = 3 * width
        from PyQt5.QtGui import QImage, QPixmap
        q_image = QImage(image.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        self.pixmap = QPixmap.fromImage(q_image)

        self.setFixedSize(width, height)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.selecting = True

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.selecting:
            self.end_point = event.pos()
            self.selecting = False
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)

        if self.start_point and self.end_point:
            # Draw selection rectangle
            rect = QRect(self.start_point, self.end_point).normalized()

            # Semi-transparent fill
            painter.fillRect(rect, QColor(0, 255, 0, 50))

            # Border
            pen = QPen(QColor(0, 255, 0), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Draw dimensions
            painter.setPen(QColor(255, 255, 255))
            text = f"{rect.width()} x {rect.height()}"
            painter.drawText(rect.topLeft() + QPoint(5, -5), text)

    def get_selection(self):
        """Get the selected region as (x, y, width, height)."""
        if self.start_point and self.end_point:
            rect = QRect(self.start_point, self.end_point).normalized()
            return (rect.x(), rect.y(), rect.width(), rect.height())
        return None


class AddWindowTool(QMainWindow):
    """Main window for the Add Window tool."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Add Window Region Tool")
        self.window_capture = WindowCapture('Raid: Shadow Legends')
        self.windows = self.load_windows()
        self.selector = None
        self.current_frame = None

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Instructions
        instructions = QLabel(
            "1. Click 'Capture Screen' to take a snapshot\n"
            "2. Click and drag to select the region\n"
            "3. Enter a name and click 'Save Region'"
        )
        layout.addWidget(instructions)

        # Capture button
        self.capture_btn = QPushButton("Capture Screen")
        self.capture_btn.clicked.connect(self.capture_screen)
        layout.addWidget(self.capture_btn)

        # Name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Region Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., cb_victory_damage")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        # Save button
        self.save_btn = QPushButton("Save Region")
        self.save_btn.clicked.connect(self.save_region)
        self.save_btn.setEnabled(False)
        layout.addWidget(self.save_btn)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.setGeometry(100, 100, 400, 200)

    def load_windows(self):
        """Load existing window regions from windows.json."""
        windows_file = 'windows.json'
        if os.path.exists(windows_file):
            with open(windows_file, 'r') as f:
                return json.load(f)
        return {}

    def save_windows(self):
        """Save window regions to windows.json."""
        with open('windows.json', 'w') as f:
            json.dump(self.windows, f, indent=2)

    def capture_screen(self):
        """Capture the game window."""
        try:
            frame = self.window_capture.capture()
            if frame is None:
                QMessageBox.warning(self, "Error", "Could not capture game window")
                return

            self.current_frame = frame

            # Create selector window
            if self.selector:
                self.selector.close()

            self.selector = WindowSelector(frame)
            self.selector.setWindowTitle("Select Region (drag to select)")
            self.selector.show()

            self.save_btn.setEnabled(True)
            self.status_label.setText("Screen captured. Select a region on the game window.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to capture screen: {e}")

    def save_region(self):
        """Save the selected region."""
        if not self.selector:
            QMessageBox.warning(self, "Error", "No region selected")
            return

        selection = self.selector.get_selection()
        if not selection:
            QMessageBox.warning(self, "Error", "No region selected. Click and drag to select an area.")
            return

        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a region name")
            return

        # Get window dimensions for relative coordinates
        _, _, win_width, win_height = self.window_capture.window_info

        x, y, width, height = selection

        # Calculate relative coordinates (as percentages)
        x_rel = x / win_width
        y_rel = y / win_height
        width_rel = width / win_width
        height_rel = height / win_height

        # Store both absolute and relative coordinates
        region_data = {
            'absolute': {
                'x': x,
                'y': y,
                'width': width,
                'height': height
            },
            'relative': {
                'x': round(x_rel, 4),
                'y': round(y_rel, 4),
                'width': round(width_rel, 4),
                'height': round(height_rel, 4)
            },
            'window_size': {
                'width': win_width,
                'height': win_height
            }
        }

        self.windows[name] = region_data
        self.save_windows()

        # Show success message with code snippet
        code_snippet = f"""
Region saved successfully!

Name: {name}
Absolute: x={x}, y={y}, width={width}, height={height}
Relative: x={x_rel:.4f}, y={y_rel:.4f}, width={width_rel:.4f}, height={height_rel:.4f}

Python code to use this region:
----------------------------------------
# Using absolute coordinates:
region = ({x}, {y}, {width}, {height})

# Using relative coordinates (recommended):
_, _, win_width, win_height = self.window_capture.window_info
region_x = int(win_width * {x_rel:.4f})
region_y = int(win_height * {y_rel:.4f})
region_width = int(win_width * {width_rel:.4f})
region_height = int(win_height * {height_rel:.4f})
region = (region_x, region_y, region_width, region_height)
----------------------------------------
"""

        QMessageBox.information(self, "Success", code_snippet)
        self.status_label.setText(f"Region '{name}' saved!")

        # Save a preview image
        preview_img = self.current_frame[y:y+height, x:x+width]
        preview_path = f"debug/window_{name}.png"
        os.makedirs("debug", exist_ok=True)
        cv2.imwrite(preview_path, preview_img)
        self.status_label.setText(f"Region '{name}' saved! Preview: {preview_path}")

        # Reset for next selection
        self.name_input.clear()
        if self.selector:
            self.selector.close()
            self.selector = None


if __name__ == '__main__':
    app = QApplication(sys.argv)
    tool = AddWindowTool()
    tool.show()
    sys.exit(app.exec_())
