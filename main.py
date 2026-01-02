import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QPen, QPixmap, QImage
import os


from window_capture import WindowCapture
from template_matcher import TemplateMatcher
from region_selection import RegionSelectionWindow
from utils import log_message, show_preview, show_error, show_info
from config import (
    GAME_WINDOW_TITLE, TEMPLATES_DIR, MIN_SELECTION_SIZE,
    ARENA_OCR_REGION, ARENA_OCR_BOTTOM_BAND
)
from sequences.arenas import ArenasSequence
from sequences.battle_sequence import ClassicArenaSequence
from text_recognition import TextRecognizer
from debug_overlay import get_overlay, hide_overlay



class DreamerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Dreamer - Window Scanner')
        self.setGeometry(100, 100, 900, 700)
        
        # Initialize components
        self.window_capture = WindowCapture(GAME_WINDOW_TITLE)
        self.template_matcher = TemplateMatcher(self.window_capture)
        self.last_frame = None
        self.overlay_visible = False
        self.stop_requested = False  # Flag to stop running sequences
        
        # UI Setup (must be before text_recognizer since it logs on init)
        self.setup_ui()
        
        # Initialize text recognizer after UI is ready (it logs on init)
        self.text_recognizer = TextRecognizer(self.window_capture, self.log)
        
        # Resize game window to target size for consistent OCR
        self._resize_game_window()
    
    def _resize_game_window(self):
        """Resize the game window to the expected size (1734x703) if needed"""
        try:
            result = self.window_capture.resize_window()
            if result == 'resized':
                self.log('✓ Game window resized to 1734x703')
            elif result == 'already_correct':
                self.log('✓ Game window already at correct size (1734x703)')
            elif result == 'not_found':
                self.log('⚠ Could not find game window to resize')
            else:
                self.log('⚠ Could not resize game window')
        except Exception as e:
            self.log(f'⚠ Could not resize game window: {e}')
    
    def setup_ui(self):
        """Initialize UI components"""
        self.image_label = QLabel('Click "Add Template" to capture a screen region')
        self.image_label.setAlignment(Qt.AlignCenter)
        
        self.add_template_btn = QPushButton('Add Template')
        self.add_template_btn.clicked.connect(self.start_region_selection)
        
        self.arenas_btn = QPushButton('Run: Arenas')
        self.arenas_btn.clicked.connect(self.run_arenas_sequence)
        
        self.test_classic_arena_btn = QPushButton('Test: Scan Only')
        self.test_classic_arena_btn.clicked.connect(self.test_classic_arena_scan)
        
        self.test_attack_btn = QPushButton('Test: Scan + Attack 1')
        self.test_attack_btn.clicked.connect(self.test_classic_arena_attack)
        
        self.run_full_attack_btn = QPushButton('Run: Full Attack')
        self.run_full_attack_btn.clicked.connect(self.run_classic_arena_full)
        
        self.stop_btn = QPushButton('STOP')
        self.stop_btn.clicked.connect(self.request_stop)
        self.stop_btn.setStyleSheet('background-color: #ff4444; color: white; font-weight: bold;')
        self.stop_btn.setEnabled(False)
        
        self.overlay_btn = QPushButton('Show Scan Regions')
        self.overlay_btn.clicked.connect(self.toggle_overlay)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.add_template_btn)
        btn_layout.addWidget(self.arenas_btn)
        btn_layout.addWidget(self.test_classic_arena_btn)
        btn_layout.addWidget(self.test_attack_btn)
        btn_layout.addWidget(self.run_full_attack_btn)
        btn_layout.addWidget(self.stop_btn)
        
        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(self.overlay_btn)
        btn_layout2.addStretch()
        
        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        layout.addLayout(btn_layout)
        layout.addLayout(btn_layout2)
        layout.addWidget(QLabel('Log:'))
        layout.addWidget(self.log_output)
        self.setLayout(layout)
    
    def log(self, message):
        log_message(self, message)
    
    def request_stop(self):
        """Request stop of running sequence"""
        self.stop_requested = True
        self.log('')
        self.log('  ⚠ STOP REQUESTED - will stop after current action...')
        self.log('')
    
    def is_stop_requested(self):
        """Check if stop was requested"""
        return self.stop_requested
    
    def toggle_overlay(self):
        """Toggle the debug overlay showing scan regions"""
        try:
            if self.overlay_visible:
                # Hide overlay
                hide_overlay()
                self.overlay_visible = False
                self.overlay_btn.setText('Show Scan Regions')
                self.log('Debug overlay hidden')
            else:
                # Show overlay
                self.window_capture.get_window()
                if not self.window_capture.window_info:
                    self.log('✗ Could not find game window')
                    return
                
                overlay = get_overlay()
                overlay.show_ocr_regions(
                    self.window_capture.window_info,
                    ARENA_OCR_REGION,
                    ARENA_OCR_BOTTOM_BAND
                )
                self.overlay_visible = True
                self.overlay_btn.setText('Hide Scan Regions')
                self.log('Debug overlay shown:')
                self.log(f'  RED = Full scan region (initial scan)')
                self.log(f'  YELLOW = Bottom band (after scroll)')
        except Exception as e:
            self.log(f'✗ Overlay error: {e}')
    
    def start_region_selection(self):
        """Start region selection mode"""
        try:
            # Capture the game window first
            self.window_capture.get_window()
            frame = self.window_capture.capture()
            self.log('Window captured - select the region you want')
            
            # Hide main window and show selection window
            self.hide()
            self.selection_window = RegionSelectionWindow(self, frame)
            self.selection_window.show()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to capture window: {e}')
    
    def save_template_region(self, region_frame):
        try:
            from PyQt5.QtWidgets import QInputDialog
            self.log(f'Region captured: {region_frame.shape}')
            self.show()
            self.raise_()
            self.activateWindow()
            QApplication.processEvents()
            show_preview(self.image_label, region_frame)
            name, ok = QInputDialog.getText(self, 'Save Template', 'Enter template name:')
            if ok and name:
                if not os.path.exists(TEMPLATES_DIR):
                    os.makedirs(TEMPLATES_DIR)
                filepath = os.path.join(TEMPLATES_DIR, f'{name}.png')
                result = cv2.imwrite(filepath, region_frame)
                if result:
                    self.log(f'✓ Template saved: {filepath}')
                    show_info(self, f'Template saved as {filepath}')
                else:
                    self.log(f'✗ Failed to save template')
                    show_error(self, 'Failed to save template image')
            else:
                self.log('Template save cancelled')
        except Exception as e:
            self.log(f'✗ Error saving template: {e}')
            import traceback
            traceback.print_exc()
            show_error(self, f'Failed to save template: {e}')
    
    # show_preview now handled by utils.show_preview
    
    def run_arenas_sequence(self):
        try:
            sequence = ArenasSequence(self.window_capture, self.template_matcher, self.log)
            sequence.run()
        except Exception as e:
            self.log(f'✗ Error: {e}')
            show_error(self, f'Sequence failed: {e}')
    
    def test_classic_arena_scan(self):
        """Test Classic Arena OCR - scan only, no attacking"""
        try:
            self.log('\n[TEST MODE] Running Classic Arena SCAN test...')
            self.log('Make sure you are already on the Classic Arena screen!')
            
            classic_arena = ClassicArenaSequence(
                self.window_capture,
                self.template_matcher,
                self.text_recognizer,
                self.log
            )
            
            # Run in scan-only mode
            classic_arena.run(scan_only=True)
            
        except Exception as e:
            import traceback
            self.log(f'✗ Error: {e}')
            self.log(traceback.format_exc())
            show_error(self, f'Test failed: {e}')
    
    def test_classic_arena_attack(self):
        """Test Classic Arena - scan and attack ONE opponent"""
        try:
            self.log('\n[TEST MODE] Running Classic Arena ATTACK test...')
            self.log('Make sure you are already on the Classic Arena screen!')
            self.log('This will scan all opponents and attack the WEAKEST one.')
            
            classic_arena = ClassicArenaSequence(
                self.window_capture,
                self.template_matcher,
                self.text_recognizer,
                self.log
            )
            
            # Run in test attack mode (scan + attack first target only)
            classic_arena.run(test_single_attack=True)
            
        except Exception as e:
            import traceback
            self.log(f'✗ Error: {e}')
            self.log(traceback.format_exc())
            show_error(self, f'Test failed: {e}')
    
    def run_classic_arena_full(self):
        """Run full Classic Arena sequence - scan and attack ALL available opponents"""
        try:
            self.log('\n[FULL MODE] Running Classic Arena FULL sequence...')
            self.log('Make sure you are already on the Classic Arena screen!')
            self.log('This will scan all opponents and attack ALL available targets.')
            
            # Reset stop flag and enable stop button
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            
            classic_arena = ClassicArenaSequence(
                self.window_capture,
                self.template_matcher,
                self.text_recognizer,
                self.log,
                stop_check=self.is_stop_requested  # Pass stop check function
            )
            
            # Run full attack mode (scan + attack all targets)
            classic_arena.run()
            
        except Exception as e:
            import traceback
            self.log(f'✗ Error: {e}')
            self.log(traceback.format_exc())
            show_error(self, f'Full sequence failed: {e}')
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False


def main():
    app = QApplication(sys.argv)
    window = DreamerApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
