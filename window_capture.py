import time
import pyautogui
import cv2
import numpy as np
import pygetwindow as gw

# Target window size for consistent behavior
TARGET_WINDOW_WIDTH = 1734
TARGET_WINDOW_HEIGHT = 703


class WindowCapture:
    def __init__(self, window_title):
        self.window_title = window_title
        self.window_info = None

    def get_window(self):
        """Find and activate the target window"""
        window = None
        for w in gw.getAllTitles():
            if self.window_title in w:
                window = gw.getWindowsWithTitle(w)[0]
                break
        if not window:
            raise Exception(f'Window "{self.window_title}" not found.')
        window.activate()
        time.sleep(0.5)  # Wait for window to come to front
        left, top, width, height = window.left, window.top, window.width, window.height
        self.window_info = (left, top, width, height)
        return self.window_info

    def resize_window(self, width=TARGET_WINDOW_WIDTH, height=TARGET_WINDOW_HEIGHT):
        """
        Resize the game window to target dimensions for consistent OCR behavior.
        Only resizes if current size doesn't match target.
        
        Args:
            width: Target width (default: 1734)
            height: Target height (default: 703)
            
        Returns:
            'resized' if window was resized
            'already_correct' if window was already the correct size
            'not_found' if window wasn't found
            'error' if resize failed
        """
        window = None
        for w in gw.getAllTitles():
            if self.window_title in w:
                window = gw.getWindowsWithTitle(w)[0]
                break
        
        if not window:
            return 'not_found'
        
        # Check if already correct size
        if window.width == width and window.height == height:
            self.window_info = (window.left, window.top, width, height)
            return 'already_correct'
        
        try:
            # Resize the window
            window.resizeTo(width, height)
            time.sleep(0.3)  # Wait for resize to complete
            
            # Update window_info
            self.window_info = (window.left, window.top, width, height)
            return 'resized'
        except Exception:
            return 'error'

    def capture(self):
        """Capture screenshot of the window"""
        if not self.window_info:
            self.get_window()
        left, top, width, height = self.window_info
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        return frame
