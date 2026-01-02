"""
Debug Overlay - Transparent window that shows scan regions over the game
"""

import sys
import time
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QRect, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QBrush

# Windows-specific imports for true click-through
if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes
    
    # Windows constants
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    
    user32 = ctypes.windll.user32
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long


class DebugOverlay(QWidget):
    """
    Transparent overlay window that displays scan regions over the game.
    Click-through so it doesn't interfere with gameplay.
    """
    
    def __init__(self):
        super().__init__()
        
        # Store regions to draw: list of (rect, color, label)
        self.regions = []
        
        # Store detection flashes: list of {rect, color, label, expire_time}
        self.detection_flashes = []
        
        # Window position/size (will be set to match game window)
        self.game_rect = None
        
        # Setup transparent, click-through, always-on-top window
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |  # Always on top
            Qt.FramelessWindowHint |   # No border
            Qt.Tool                    # Don't show in taskbar
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # Transparent background
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # Click-through (Qt level)
        
        # Don't show until positioned
        self.hide()
        
        # Auto-refresh timer (for flash expiration)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._on_refresh)
        self.refresh_timer.start(100)  # Check every 100ms
    
    def showEvent(self, event):
        """Apply Windows-specific click-through when window is shown"""
        super().showEvent(event)
        self._make_click_through()
    
    def _make_click_through(self):
        """Use Windows API to make window truly click-through"""
        if sys.platform == 'win32':
            hwnd = int(self.winId())
            # Get current extended style
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            # Add layered and transparent flags
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
    
    def _on_refresh(self):
        """Timer callback to expire old flashes"""
        now = time.time()
        # Remove expired flashes
        self.detection_flashes = [f for f in self.detection_flashes if f['expire_time'] > now]
        self.update()
        
    def set_game_window(self, left, top, width, height):
        """Position overlay to match game window"""
        self.game_rect = QRect(left, top, width, height)
        self.setGeometry(left, top, width, height)
        
    def clear_regions(self):
        """Clear all regions"""
        self.regions = []
        self.update()
        
    def add_region(self, x, y, width, height, color='red', label=''):
        """
        Add a region to display
        
        Args:
            x, y: Position relative to game window
            width, height: Size of region
            color: 'red', 'green', 'blue', 'yellow', or hex string
            label: Optional text label
        """
        color_map = {
            'red': QColor(255, 0, 0, 180),
            'green': QColor(0, 255, 0, 180),
            'blue': QColor(0, 100, 255, 180),
            'yellow': QColor(255, 255, 0, 180),
            'orange': QColor(255, 165, 0, 180),
            'purple': QColor(128, 0, 128, 180),
        }
        
        qcolor = color_map.get(color, QColor(255, 0, 0, 180))
        self.regions.append({
            'rect': QRect(x, y, width, height),
            'color': qcolor,
            'label': label
        })
        self.update()
    
    def flash_detection(self, x, y, width, height, power_value, duration=1.0):
        """
        Flash a green indicator showing a detected team power
        
        Args:
            x, y: Position relative to game window (where power was found)
            width: Width of the flash bar
            height: Height of the flash bar (typically ~30-40px for one row)
            power_value: The power value detected (shown as label)
            duration: How long to show the flash (seconds)
        """
        flash = {
            'rect': QRect(x, y, width, height),
            'color': QColor(0, 255, 0, 120),  # Semi-transparent green
            'label': f'FOUND: {power_value:,}',
            'expire_time': time.time() + duration
        }
        self.detection_flashes.append(flash)
        self.show()
        self.update()
    
    def flash_detection_at_y(self, y_position, power_value, duration=1.0):
        """
        Flash detection at a Y position spanning the OCR region width
        
        Args:
            y_position: Y position in window coordinates
            power_value: The power value detected
            duration: How long to show (seconds)
        """
        if not self.game_rect:
            return
        
        # Flash spans the Team Power text area
        width = self.game_rect.width()
        flash_x = int(width * 0.65)  # Match OCR region x_start
        flash_width = int(width * 0.25)  # Match OCR region width
        flash_height = 35  # Height of one opponent row approximately
        
        # Center the flash on the Y position
        flash_y = y_position - flash_height // 2
        
        self.flash_detection(flash_x, flash_y, flash_width, flash_height, power_value, duration)
    
    def show_full_scan_region(self, window_info, full_region_config):
        """Show only the FULL SCAN region (red) - used during initial scan"""
        left, top, width, height = window_info
        self.set_game_window(left, top, width, height)
        self.clear_regions()
        
        x = int(width * full_region_config['x_start'])
        y = int(height * full_region_config['y_start'])
        w = int(width * full_region_config['width'])
        h = int(height * full_region_config['height'])
        self.add_region(x, y, w, h, 'red', 'FULL SCAN')
        
        self.show()
        self.update()
    
    def show_bottom_band_region(self, window_info, bottom_band_config):
        """Show only the BOTTOM BAND region (yellow) - used after scrolling"""
        left, top, width, height = window_info
        self.set_game_window(left, top, width, height)
        self.clear_regions()
        
        x = int(width * bottom_band_config['x_start'])
        y = int(height * bottom_band_config['y_start'])
        w = int(width * bottom_band_config['width'])
        h = int(height * bottom_band_config['height'])
        self.add_region(x, y, w, h, 'yellow', 'BOTTOM BAND')
        
        self.show()
        self.update()
        
    def show_ocr_regions(self, window_info, full_region_config, bottom_band_config=None):
        """
        Convenience method to show BOTH OCR scan regions (for static preview)
        
        Args:
            window_info: (left, top, width, height) of game window
            full_region_config: Dict with x_start, y_start, width, height (as percentages)
            bottom_band_config: Optional dict for bottom band region
        """
        left, top, width, height = window_info
        self.set_game_window(left, top, width, height)
        self.clear_regions()
        
        # Full OCR region (red)
        if full_region_config:
            x = int(width * full_region_config['x_start'])
            y = int(height * full_region_config['y_start'])
            w = int(width * full_region_config['width'])
            h = int(height * full_region_config['height'])
            self.add_region(x, y, w, h, 'red', 'FULL SCAN')
        
        # Bottom band (yellow)
        if bottom_band_config:
            x = int(width * bottom_band_config['x_start'])
            y = int(height * bottom_band_config['y_start'])
            w = int(width * bottom_band_config['width'])
            h = int(height * bottom_band_config['height'])
            self.add_region(x, y, w, h, 'yellow', 'BOTTOM BAND')
        
        self.show()
        self.update()
        
    def show_single_region(self, window_info, region_config, color='red', label=''):
        """Show just one region"""
        left, top, width, height = window_info
        self.set_game_window(left, top, width, height)
        self.clear_regions()
        
        x = int(width * region_config['x_start'])
        y = int(height * region_config['y_start'])
        w = int(width * region_config['width'])
        h = int(height * region_config['height'])
        self.add_region(x, y, w, h, color, label)
        
        self.show()
        self.update()
        
    def paintEvent(self, event):
        """Draw the regions and detection flashes"""
        if not self.regions and not self.detection_flashes:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Setup font for labels
        font = QFont('Arial', 12, QFont.Bold)
        painter.setFont(font)
        
        # Draw static regions (scan areas)
        for region in self.regions:
            rect = region['rect']
            color = region['color']
            label = region['label']
            
            # Draw rectangle outline (thick)
            pen = QPen(color)
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # Draw corner markers for visibility
            corner_size = 15
            # Top-left
            painter.drawLine(rect.left(), rect.top(), rect.left() + corner_size, rect.top())
            painter.drawLine(rect.left(), rect.top(), rect.left(), rect.top() + corner_size)
            # Top-right
            painter.drawLine(rect.right(), rect.top(), rect.right() - corner_size, rect.top())
            painter.drawLine(rect.right(), rect.top(), rect.right(), rect.top() + corner_size)
            # Bottom-left
            painter.drawLine(rect.left(), rect.bottom(), rect.left() + corner_size, rect.bottom())
            painter.drawLine(rect.left(), rect.bottom(), rect.left(), rect.bottom() - corner_size)
            # Bottom-right
            painter.drawLine(rect.right(), rect.bottom(), rect.right() - corner_size, rect.bottom())
            painter.drawLine(rect.right(), rect.bottom(), rect.right(), rect.bottom() - corner_size)
            
            # Draw label with background
            if label:
                text_rect = painter.fontMetrics().boundingRect(label)
                text_rect.moveTo(rect.left() + 5, rect.top() + 5)
                text_rect.adjust(-3, -2, 6, 4)
                
                painter.fillRect(text_rect, QColor(0, 0, 0, 150))
                painter.setPen(QPen(color))
                painter.drawText(rect.left() + 5, rect.top() + 20, label)
        
        # Draw detection flashes (filled rectangles)
        for flash in self.detection_flashes:
            rect = flash['rect']
            color = flash['color']
            label = flash['label']
            
            # Draw filled semi-transparent rectangle
            painter.fillRect(rect, color)
            
            # Draw border
            border_color = QColor(0, 255, 0, 255)  # Solid green border
            pen = QPen(border_color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # Draw label
            if label:
                # White text with black outline for visibility
                painter.setPen(QPen(QColor(0, 0, 0, 255)))
                painter.drawText(rect.left() + 6, rect.top() + 22, label)
                painter.drawText(rect.left() + 4, rect.top() + 22, label)
                painter.drawText(rect.left() + 5, rect.top() + 23, label)
                painter.drawText(rect.left() + 5, rect.top() + 21, label)
                painter.setPen(QPen(QColor(255, 255, 255, 255)))
                painter.drawText(rect.left() + 5, rect.top() + 22, label)
        
        painter.end()
        
    def start_auto_refresh(self, interval_ms=500):
        """Start auto-refresh timer"""
        self.refresh_timer.start(interval_ms)
        
    def stop_auto_refresh(self):
        """Stop auto-refresh timer"""
        self.refresh_timer.stop()


# Singleton instance for easy access
_overlay_instance = None

def get_overlay():
    """Get or create the debug overlay singleton"""
    global _overlay_instance
    if _overlay_instance is None:
        _overlay_instance = DebugOverlay()
    return _overlay_instance

def show_scan_regions(window_capture, full_config, bottom_config=None):
    """
    Quick helper to show BOTH scan regions (static preview)
    
    Args:
        window_capture: WindowCapture instance with window_info
        full_config: ARENA_OCR_REGION config dict
        bottom_config: ARENA_OCR_BOTTOM_BAND config dict (optional)
    """
    overlay = get_overlay()
    if window_capture.window_info:
        overlay.show_ocr_regions(
            window_capture.window_info,
            full_config,
            bottom_config
        )
    return overlay

def show_full_scan_mode(window_info, full_config):
    """Show only the FULL SCAN region (red)"""
    overlay = get_overlay()
    if window_info:
        overlay.show_full_scan_region(window_info, full_config)
    return overlay

def show_bottom_band_mode(window_info, bottom_config):
    """Show only the BOTTOM BAND region (yellow)"""
    overlay = get_overlay()
    if window_info:
        overlay.show_bottom_band_region(window_info, bottom_config)
    return overlay

def hide_overlay():
    """Hide the overlay"""
    overlay = get_overlay()
    overlay.hide()
    overlay.clear_regions()

def flash_power_detection(window_info, y_position, power_value, duration=1.0):
    """
    Flash a detection indicator at a Y position
    
    Args:
        window_info: (left, top, width, height) of game window
        y_position: Y position where power was found (window coordinates)
        power_value: The power value detected
        duration: How long to show the flash
    """
    overlay = get_overlay()
    if window_info:
        left, top, width, height = window_info
        overlay.set_game_window(left, top, width, height)
        overlay.flash_detection_at_y(y_position, power_value, duration)
    return overlay
