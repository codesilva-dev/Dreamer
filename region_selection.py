from PyQt5.QtWidgets import QWidget, QInputDialog, QMessageBox
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen
from PyQt5.QtCore import Qt, QRect, QPoint

class RegionSelectionWindow(QWidget):
    """Window for selecting region from a captured screenshot"""
    def __init__(self, parent, frame):
        super().__init__()
        self.parent_app = parent
        self.frame = frame
        self.begin = QPoint()
        self.end = QPoint()
        self.is_selecting = False
        self.setWindowTitle('Select Region - Click and drag to select, press Enter to save, Esc to cancel')
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_BGR888)
        self.pixmap = QPixmap.fromImage(q_img)
        self.setFixedSize(self.pixmap.size())
        self.setCursor(Qt.CrossCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)
        if self.is_selecting or (self.begin != QPoint() and self.end != QPoint()):
            painter.fillRect(self.rect(), Qt.black)
            painter.setOpacity(0.5)
            painter.drawPixmap(0, 0, self.pixmap)
            rect = QRect(self.begin, self.end).normalized()
            painter.setOpacity(1.0)
            painter.setClipRect(rect)
            painter.drawPixmap(0, 0, self.pixmap)
            painter.setClipping(False)
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = self.begin
        self.is_selecting = True
        self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        try:
            self.is_selecting = False
            self.end = event.pos()
            rect = QRect(self.begin, self.end).normalized()
            self.close()
            self.parent_app.show()
            self.parent_app.raise_()
            self.parent_app.activateWindow()
            if rect.width() > 10 and rect.height() > 10:
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                selected_region = self.frame[y:y+h, x:x+w]
                self.parent_app.save_template_region(selected_region)
            else:
                self.parent_app.log('Selection too small, cancelled')
        except Exception as e:
            self.parent_app.show()
            self.parent_app.log(f'Error during selection: {e}')
            import traceback
            traceback.print_exc()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            rect = QRect(self.begin, self.end).normalized()
            if rect.width() > 10 and rect.height() > 10:
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                selected_region = self.frame[y:y+h, x:x+w]
                self.close()
                self.parent_app.show()
                self.parent_app.save_template_region(selected_region)
            else:
                self.parent_app.log('Selection too small, cancelled')
                self.close()
                self.parent_app.show()
        elif event.key() == Qt.Key_Escape:
            self.close()
            self.parent_app.show()
            self.parent_app.log('Region selection cancelled')
