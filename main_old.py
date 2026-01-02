
import sys
import time
import pyautogui
import cv2
import numpy as np
import pygetwindow as gw
import pytesseract
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QMessageBox, QLineEdit, QTextEdit, QHBoxLayout
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt



class DreamerApp(QWidget):
	def __init__(self):
		super().__init__()
		self.setWindowTitle('Dreamer - Window Scanner')
		self.setGeometry(100, 100, 900, 700)
		self.image_label = QLabel('Click "Capture Raid: Shadow Legends Window" to begin')
		self.image_label.setAlignment(Qt.AlignCenter)
		self.capture_btn = QPushButton('Capture Raid: Shadow Legends Window')
		self.capture_btn.clicked.connect(self.capture_and_show)

		self.arenas_btn = QPushButton('Arenas')
		self.arenas_btn.clicked.connect(self.run_arenas_sequence)
		
		self.save_template_btn = QPushButton('Save Template')
		self.save_template_btn.clicked.connect(self.save_current_screenshot_as_template)
		self.save_template_btn.setEnabled(False)

		self.search_input = QLineEdit()
		self.search_input.setPlaceholderText('Enter text to search for...')
		self.ocr_btn = QPushButton('Search Text in Screenshot')
		self.ocr_btn.clicked.connect(self.search_text_in_screenshot)
		self.ocr_btn.setEnabled(False)
		self.ocr_result = QTextEdit()
		self.ocr_result.setReadOnly(True)

		btn_layout = QHBoxLayout()
		btn_layout.addWidget(self.capture_btn)
		btn_layout.addWidget(self.arenas_btn)
		btn_layout.addWidget(self.save_template_btn)

		layout = QVBoxLayout()
		layout.addWidget(self.image_label)
		layout.addLayout(btn_layout)
		layout.addWidget(self.search_input)
		layout.addWidget(self.ocr_btn)
		layout.addWidget(QLabel('OCR Result:'))
		layout.addWidget(self.ocr_result)
		self.setLayout(layout)

		self.last_frame = None
		self.window_info = None

	def get_raid_window(self):
		window = None
		for w in gw.getAllTitles():
			if 'Raid: Shadow Legends' in w:
				window = gw.getWindowsWithTitle(w)[0]
				break
		if not window:
			raise Exception('Window "Raid: Shadow Legends" not found.')
		window.activate()
		time.sleep(0.5)  # Wait for window to come to front
		left, top, width, height = window.left, window.top, window.width, window.height
		self.window_info = (left, top, width, height)
		return self.window_info

	def capture_window(self):
		if not self.window_info:
			self.get_raid_window()
		left, top, width, height = self.window_info
		screenshot = pyautogui.screenshot(region=(left, top, width, height))
		frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
		self.last_frame = frame
		return frame

	def show_frame(self, frame):
		height, width, channel = frame.shape
		bytes_per_line = 3 * width
		q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_BGR888)
		pixmap = QPixmap.fromImage(q_img)
		self.image_label.setPixmap(pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

	def capture_and_show(self):
		try:
			self.get_raid_window()
			frame = self.capture_window()
			self.show_frame(frame)
			self.ocr_btn.setEnabled(True)
			self.save_template_btn.setEnabled(True)
			self.ocr_result.clear()
		except Exception as e:
			QMessageBox.critical(self, 'Error', f'Failed to capture window: {e}')
			self.ocr_btn.setEnabled(False)

	def save_current_screenshot_as_template(self):
		if self.last_frame is None:
			QMessageBox.warning(self, 'Warning', 'No screenshot available.')
			return
		
		from PyQt5.QtWidgets import QInputDialog, QFileDialog
		import os
		
		name, ok = QInputDialog.getText(self, 'Save Template', 'Enter template name:')
		if ok and name:
			# Create templates directory if it doesn't exist
			if not os.path.exists('templates'):
				os.makedirs('templates')
			
			filepath = f'templates/{name}.png'
			cv2.imwrite(filepath, self.last_frame)
			QMessageBox.information(self, 'Success', f'Template saved as {filepath}')

	def search_text_in_screenshot(self):
		if self.last_frame is None:
			QMessageBox.warning(self, 'Warning', 'No screenshot available. Capture the window first.')
			return
		search_text = self.search_input.text().strip()
		if not search_text:
			QMessageBox.warning(self, 'Warning', 'Please enter text to search for.')
			return
		try:
			ocr_result = pytesseract.image_to_string(self.last_frame)
			self.ocr_result.setPlainText(ocr_result)
			if search_text.lower() in ocr_result.lower():
				QMessageBox.information(self, 'Text Found', f'Text "{search_text}" found in screenshot!')
			else:
				QMessageBox.information(self, 'Text Not Found', f'Text "{search_text}" NOT found in screenshot.')
		except Exception as e:
			QMessageBox.critical(self, 'Error', f'OCR failed: {e}')

	def find_and_click_template(self, template_path, threshold=0.8):
		"""Find and click on a template image within the captured window"""
		if not self.window_info:
			self.get_raid_window()
		
		time.sleep(0.3)
		frame = self.capture_window()
		self.show_frame(frame)
		QApplication.processEvents()
		
		# Load template image
		template = cv2.imread(template_path)
		if template is None:
			self.ocr_result.append(f'  ✗ Template image not found: {template_path}')
			return False
		
		# Convert to grayscale for matching
		gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
		
		# Try template matching at multiple scales
		for scale in [1.0, 0.9, 1.1, 0.8, 1.2]:
			scaled_template = cv2.resize(gray_template, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
			
			if scaled_template.shape[0] > gray_frame.shape[0] or scaled_template.shape[1] > gray_frame.shape[1]:
				continue
			
			result = cv2.matchTemplate(gray_frame, scaled_template, cv2.TM_CCOEFF_NORMED)
			min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
			
			if max_val >= threshold:
				h, w = scaled_template.shape
				x = max_loc[0] + w // 2
				y = max_loc[1] + h // 2
				
				left, top, _, _ = self.window_info
				abs_x = left + x
				abs_y = top + y
				
				self.ocr_result.append(f'  ✓ Found template (confidence: {max_val:.2%}, scale: {scale:.1f}x)')
				QApplication.processEvents()
				
				pyautogui.moveTo(abs_x, abs_y, duration=0.3)
				time.sleep(0.2)
				pyautogui.click()
				return True
		
		return False

	def preprocess_for_ocr(self, frame):
		"""Preprocess image to improve OCR accuracy on colored text"""
		# Convert to grayscale
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		
		# Try multiple preprocessing approaches
		processed_images = []
		
		# 1. Upscaled 3x - helps with very small text
		upscaled3x = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
		processed_images.append(('Upscaled 3x', upscaled3x, 3))
		
		# 2. Upscaled 2x with sharpening
		upscaled2x = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
		kernel_sharp = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
		sharpened = cv2.filter2D(upscaled2x, -1, kernel_sharp)
		processed_images.append(('Upscaled 2x + Sharpened', sharpened, 2))
		
		# 3. Multiple threshold levels for white text
		for thresh_val in [150, 170, 190]:
			_, thresh = cv2.threshold(upscaled2x, thresh_val, 255, cv2.THRESH_BINARY)
			processed_images.append((f'Upscaled Threshold {thresh_val}', thresh, 2))
		
		# 4. Aggressive CLAHE on upscaled
		clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(8, 8))
		enhanced = clahe.apply(upscaled2x)
		processed_images.append(('CLAHE Strong', enhanced, 2))
		
		return processed_images

	def find_and_click_text(self, text, retries=3):
		for attempt in range(retries):
			if attempt > 0:
				self.ocr_result.append(f'  Retry {attempt}/{retries-1}...')
				QApplication.processEvents()
				time.sleep(1.0)  # Wait before retry
			
			time.sleep(0.3)  # Brief pause before capture
			frame = self.capture_window()
			self.show_frame(frame)  # Show what we're seeing
			QApplication.processEvents()  # Update UI
			
			# Helper function to find text with fuzzy matching
			def find_text_match(ocr_data, search_text, scale_factor=1):
				search_lower = search_text.lower()
				search_words = search_lower.split()
				
				# Method 1: Direct substring match
				for i, word in enumerate(ocr_data['text']):
					if word.strip() and search_lower in word.lower():
						return (i, word, 'direct match')
				
				# Method 2: Multi-word phrase detection (combine adjacent words)
				if len(search_words) > 1:
					for i in range(len(ocr_data['text']) - 1):
						word1 = ocr_data['text'][i].strip().lower()
						word2 = ocr_data['text'][i+1].strip().lower()
						if word1 and word2:
							combined = f"{word1} {word2}"
							if search_lower in combined or combined in search_lower:
								# Use middle point between the two words
								return (i, f"{word1} {word2}", 'multi-word match')
				
				# Method 3: Partial word matching (for multi-word searches)
				for search_word in search_words:
					for i, word in enumerate(ocr_data['text']):
						if len(search_word) > 3 and word.strip().lower() == search_word:
							return (i, word, f'partial match on "{search_word}"')
				
				return None
			
			# Try OCR with different Tesseract configs
			configs = [
				('--psm 11', 'Sparse text'),
				('--psm 6', 'Uniform block'),
				('--psm 3', 'Auto page segmentation'),
			]
			
			for config, config_name in configs:
				self.ocr_result.append(f'  [Original - {config_name}] Scanning...')
				QApplication.processEvents()
				ocr_data = pytesseract.image_to_data(frame, config=config, output_type=pytesseract.Output.DICT)
				detected_words = [w.strip() for w in ocr_data['text'] if w.strip()]
				self.ocr_result.append(f'  Detected: {", ".join(detected_words[:20])}{"..." if len(detected_words) > 20 else ""}')
				QApplication.processEvents()
				
				match_result = find_text_match(ocr_data, text)
				if match_result:
					i, matched_word, match_type = match_result
					self.ocr_result.append(f'  ✓ Found "{matched_word}" ({match_type})')
					QApplication.processEvents()
					x = ocr_data['left'][i] + ocr_data['width'][i] // 2
					y = ocr_data['top'][i] + ocr_data['height'][i] // 2
					left, top, _, _ = self.window_info
					abs_x = left + x
					abs_y = top + y
					
					pyautogui.moveTo(abs_x, abs_y, duration=0.3)
					time.sleep(0.2)
					pyautogui.click()
					return True
			
			# If not found, try preprocessed versions
			processed_images = self.preprocess_for_ocr(frame)
			
			for method_name, proc_img, scale_factor in processed_images:
				self.ocr_result.append(f'  [{method_name}] Scanning...')
				QApplication.processEvents()
				
				# Try each preprocessing with best PSM mode
				ocr_data = pytesseract.image_to_data(proc_img, config='--psm 11', output_type=pytesseract.Output.DICT)
				detected_words = [w.strip() for w in ocr_data['text'] if w.strip()]
				self.ocr_result.append(f'  Detected: {", ".join(detected_words[:20])}{"..." if len(detected_words) > 20 else ""}')
				QApplication.processEvents()
				
				match_result = find_text_match(ocr_data, text, scale_factor)
				if match_result:
					i, matched_word, match_type = match_result
					self.ocr_result.append(f'  ✓ Found "{matched_word}" ({match_type}) using {method_name}')
					QApplication.processEvents()
					x = ocr_data['left'][i] + ocr_data['width'][i] // 2
					y = ocr_data['top'][i] + ocr_data['height'][i] // 2
					
					# Adjust coordinates for upscaled images
					x = x // scale_factor
					y = y // scale_factor
					
					left, top, _, _ = self.window_info
					abs_x = left + x
					abs_y = top + y
					
					pyautogui.moveTo(abs_x, abs_y, duration=0.3)
					time.sleep(0.2)
					pyautogui.click()
					return True
		return False

	def run_arenas_sequence(self):
		try:
			self.get_raid_window()
			time.sleep(1.0)  # Wait for window to stabilize
			steps = ["Battle", "Arena", "Classic Arena"]
			for step in steps:
				self.ocr_result.append(f'Looking for "{step}"...')
				QApplication.processEvents()  # Update UI
				found = self.find_and_click_text(step)
				if found:
					self.ocr_result.append(f'✓ Clicked on "{step}"')
					time.sleep(2.0)  # Wait for UI to respond after click
				else:
					self.ocr_result.append(f'✗ Could not find "{step}"')
					break
				QApplication.processEvents()  # Update UI
			self.ocr_result.append(f'\nArenas sequence completed!')
		except Exception as e:
			self.ocr_result.append(f'\n✗ Error: {e}')
			QMessageBox.critical(self, 'Error', f'Arenas sequence failed: {e}')

def main():
	app = QApplication(sys.argv)
	window = DreamerApp()
	window.show()
	sys.exit(app.exec_())

if __name__ == "__main__":
	main()
