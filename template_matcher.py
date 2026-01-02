import time
import cv2
import pyautogui


class TemplateMatcher:
    def __init__(self, window_capture):
        self.window_capture = window_capture
    
    def find_template(self, template_path, threshold=0.8):
        """
        Find template image in window without clicking.
        
        Returns:
            (found, location, size) where:
            - found: True/False
            - location: (x, y) center position relative to window, or None
            - size: (width, height) of template, or None
        """
        time.sleep(0.3)
        frame = self.window_capture.capture()
        
        template = cv2.imread(template_path)
        if template is None:
            return False, None, None
        
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        
        for scale in [1.0, 0.9, 1.1, 0.8, 1.2]:
            scaled_template = cv2.resize(gray_template, None, fx=scale, fy=scale,
                                        interpolation=cv2.INTER_CUBIC)
            
            if (scaled_template.shape[0] > gray_frame.shape[0] or
                scaled_template.shape[1] > gray_frame.shape[1]):
                continue
            
            result = cv2.matchTemplate(gray_frame, scaled_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                h, w = scaled_template.shape
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return True, (center_x, center_y), (w, h)
        
        return False, None, None
    
    def click_at_offset(self, base_x, base_y, offset_x=0, offset_y=0, wait_after=1.0):
        """
        Click at a position with offset from base coordinates.
        Coordinates are relative to window.
        """
        left, top, _, _ = self.window_capture.window_info
        abs_x = left + base_x + offset_x
        abs_y = top + base_y + offset_y
        
        pyautogui.moveTo(abs_x, abs_y, duration=0.3)
        time.sleep(0.2)
        pyautogui.click()
        time.sleep(wait_after)

    def find_and_click(self, template_path, threshold=0.8, wait_after=3.0):
        """Find template image in window and click it"""
        time.sleep(0.3)
        frame = self.window_capture.capture()
        
        # Load template image
        template = cv2.imread(template_path)
        if template is None:
            return False, f'Template not found: {template_path}'
        
        # Convert to grayscale
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        
        # Try multiple scales
        for scale in [1.0, 0.9, 1.1, 0.8, 1.2]:
            scaled_template = cv2.resize(gray_template, None, fx=scale, fy=scale, 
                                        interpolation=cv2.INTER_CUBIC)
            
            if (scaled_template.shape[0] > gray_frame.shape[0] or 
                scaled_template.shape[1] > gray_frame.shape[1]):
                continue
            
            result = cv2.matchTemplate(gray_frame, scaled_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                h, w = scaled_template.shape
                x = max_loc[0] + w // 2
                y = max_loc[1] + h // 2
                
                left, top, _, _ = self.window_capture.window_info
                abs_x = left + x
                abs_y = top + y
                
                pyautogui.moveTo(abs_x, abs_y, duration=0.3)
                time.sleep(0.2)
                pyautogui.click()
                time.sleep(wait_after)
                return True, f'Found (confidence: {max_val:.2%}, scale: {scale:.1f}x)'
        
        return False, 'Template not found in window'
