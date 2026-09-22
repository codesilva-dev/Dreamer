import sys
import cv2
import threading
import time
import os
import json
import pyautogui
from pynput import keyboard as pynput_keyboard
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox, QGroupBox, QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QInputDialog)
from PyQt5.QtCore import Qt, QTimer

from window_capture import WindowCapture
from template_matcher import TemplateMatcher
from region_selection import RegionSelectionWindow
from utils import log_message, show_preview, show_error, show_info
from config import (
    GAME_WINDOW_TITLE, TEMPLATES_DIR,
    CLICK_DELAY, TEMPLATE_BATTLE, TEMPLATE_ARENA, TEMPLATE_CLASSIC_ARENA,
)
from text_recognition import TextRecognizer
from human_clicker import HumanClicker
from natural_click import NaturalClick
from macro_recorder import MacroRecorder, MacroPlayer
from sequences.arena_sequence_v2 import ClassicArenaSequenceV2
from sequences.free_shop_items import FreeShopItemsSequence
from sequences.dismiss_junk_offers import DismissJunkOffersSequence
from sequences.guardian_ring import GuardianRingSequence
from sequences.collect_gem import CollectGemSequence
from sequences.menu_rewards import MenuRewardsSequence
from sequences.check_market import CheckMarketSequence
from sequences.quests import QuestsSequence
from sequences.sum3 import Sum3Sequence
from sequences.iron_twins import IronTwinsSequence
import config



class DreamerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Dreamer - Window Scanner')
        self.setGeometry(100, 100, 900, 700)
        
        # Initialize components
        self.window_capture = WindowCapture(GAME_WINDOW_TITLE)
        self.template_matcher = TemplateMatcher(self.window_capture)
        self.last_frame = None
        self.stop_requested = False  # Flag to stop running sequences

        # Auto-clicker state
        self.auto_clicker = HumanClicker()
        self.natural_click = NaturalClick()
        self.auto_click_running = False
        self.auto_click_thread = None
        self.auto_click_position = None  # (x, y) screen coords to click at

        # Macro recorder state (log funcs use QTimer for thread safety — set after setup_ui)
        self.macro_recorder = None
        self.macro_player = None
        self.macro_play_thread = None

        # UI Setup (must be before text_recognizer since it logs on init)
        self.setup_ui()

        # Now that UI exists, create macro components with thread-safe logging
        self.macro_recorder = MacroRecorder(
            self.window_capture,
            log_func=lambda msg: QTimer.singleShot(0, lambda m=msg: self.log(m))
        )
        self.macro_player = MacroPlayer(
            self.window_capture,
            log_func=lambda msg: QTimer.singleShot(0, lambda m=msg: self.log(m))
        )
        
        # Initialize text recognizer after UI is ready (it logs on init)
        self.text_recognizer = TextRecognizer(self.window_capture, self.log)
        
        # Resize game window to target size for consistent OCR
        self._resize_game_window()

        # Start global kill switch hotkey listener (Ctrl+Shift+Q)
        self._start_kill_switch()

        # Load saved settings (arena filters, etc.)
        self._load_settings()
    
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
    
    def _start_kill_switch(self):
        """Start a global hotkey listener for Ctrl+Shift+Q to force-quit the app.

        This works even when the main GUI thread is blocked by a running
        sequence, because pynput runs its listener on a separate thread.
        """
        def _kill():
            print('\n[KILL SWITCH] Ctrl+Shift+Q pressed — force-quitting Dreamer\n')
            os._exit(0)

        self._hotkey_listener = pynput_keyboard.GlobalHotKeys({
            '<ctrl>+<shift>+q': _kill,
        })
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()
        self.log('Kill switch active: press Ctrl+Shift+Q to force-quit at any time')

    def setup_ui(self):
        """Initialize UI components"""
        self.image_label = QLabel('Click "Add Template" to capture a screen region')
        self.image_label.setAlignment(Qt.AlignCenter)

        self.add_template_btn = QPushButton('Add Template')
        self.add_template_btn.clicked.connect(self.start_region_selection)

        self.stop_btn = QPushButton('STOP')
        self.stop_btn.clicked.connect(self.request_stop)
        self.stop_btn.setStyleSheet('background-color: #ff4444; color: white; font-weight: bold;')
        self.stop_btn.setEnabled(False)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        # === Runs Section ===
        runs_group = QGroupBox('Runs')
        runs_layout = QHBoxLayout()

        self.run_classic_arena_btn = QPushButton('Classic Arena')
        self.run_classic_arena_btn.clicked.connect(self.run_classic_arena)
        runs_layout.addWidget(self.run_classic_arena_btn)

        self.run_free_shop_btn = QPushButton('Get Free Shop Items')
        self.run_free_shop_btn.clicked.connect(self.run_free_shop_items)
        runs_layout.addWidget(self.run_free_shop_btn)

        self.run_guardian_btn = QPushButton('Guardian Ring')
        self.run_guardian_btn.clicked.connect(self.run_guardian_ring)
        runs_layout.addWidget(self.run_guardian_btn)

        self.run_bypass_junk_btn = QPushButton('Bypass Junk')
        self.run_bypass_junk_btn.clicked.connect(self.run_bypass_junk)
        runs_layout.addWidget(self.run_bypass_junk_btn)

        self.run_collect_gem_btn = QPushButton('Collect Gem')
        self.run_collect_gem_btn.clicked.connect(self.run_collect_gem)
        runs_layout.addWidget(self.run_collect_gem_btn)

        self.run_menu_rewards_btn = QPushButton('Menu Rewards')
        self.run_menu_rewards_btn.clicked.connect(self.run_menu_rewards)
        runs_layout.addWidget(self.run_menu_rewards_btn)

        self.run_check_market_btn = QPushButton('Check Market')
        self.run_check_market_btn.clicked.connect(self.run_check_market)
        runs_layout.addWidget(self.run_check_market_btn)

        self.run_quests_btn = QPushButton('Quests')
        self.run_quests_btn.clicked.connect(self.run_quests)
        runs_layout.addWidget(self.run_quests_btn)

        self.run_sum3_btn = QPushButton('Sum3')
        self.run_sum3_btn.clicked.connect(self.run_sum3)
        runs_layout.addWidget(self.run_sum3_btn)

        # Iron Twins: stage selector + gear-up macro + run button
        runs_layout.addWidget(QLabel('IT Stage:'))
        self.it_stage_spin = QSpinBox()
        self.it_stage_spin.setRange(1, 15)
        self.it_stage_spin.setValue(config.IRON_TWINS_STAGE)
        self.it_stage_spin.setToolTip('Iron Twins stage (1-15)')
        self.it_stage_spin.valueChanged.connect(self._on_it_stage_changed)
        runs_layout.addWidget(self.it_stage_spin)

        runs_layout.addWidget(QLabel('Gear Macro:'))
        self.it_macro_combo = QComboBox()
        self.it_macro_combo.setMinimumWidth(120)
        self.it_macro_combo.setToolTip('Macro to run after stage selection (gear swap)')
        self.it_macro_combo.addItem('(None)')
        self.it_macro_combo.addItems(MacroRecorder.list_macros())
        self.it_macro_combo.currentTextChanged.connect(self._on_it_macro_changed)
        runs_layout.addWidget(self.it_macro_combo)

        self.run_iron_twins_btn = QPushButton('Iron Twins')
        self.run_iron_twins_btn.clicked.connect(self.run_iron_twins)
        runs_layout.addWidget(self.run_iron_twins_btn)

        runs_layout.addWidget(self.stop_btn)
        runs_layout.addStretch()
        runs_group.setLayout(runs_layout)

        # === Arena Config UI ===
        arena_config_group = QGroupBox('Arena Config')
        arena_config_layout = QVBoxLayout()

        config_row = QHBoxLayout()

        config_row.addWidget(QLabel('Max Power:'))
        self.arena_max_power_spin = QSpinBox()
        self.arena_max_power_spin.setRange(0, 999000)
        self.arena_max_power_spin.setSingleStep(10000)
        self.arena_max_power_spin.setValue(config.ARENA_MAX_OPPONENT_POWER)
        self.arena_max_power_spin.setSpecialValueText('No limit')
        self.arena_max_power_spin.setToolTip('Skip opponents above this power (0 = no limit)')
        self.arena_max_power_spin.valueChanged.connect(self._on_arena_max_power_changed)
        config_row.addWidget(self.arena_max_power_spin)

        config_row.addWidget(QLabel('Max Level:'))
        self.arena_max_level_spin = QSpinBox()
        self.arena_max_level_spin.setRange(0, 100)
        self.arena_max_level_spin.setSingleStep(1)
        self.arena_max_level_spin.setValue(config.ARENA_MAX_OPPONENT_LEVEL)
        self.arena_max_level_spin.setSpecialValueText('No limit')
        self.arena_max_level_spin.setToolTip('Skip opponents above this level (0 = no limit)')
        self.arena_max_level_spin.valueChanged.connect(self._on_arena_max_level_changed)
        config_row.addWidget(self.arena_max_level_spin)

        config_row.addStretch()
        arena_config_layout.addLayout(config_row)
        arena_config_group.setLayout(arena_config_layout)

        # === Auto-Clicker UI ===
        auto_click_group = QGroupBox('Auto Clicker')
        auto_click_layout = QVBoxLayout()

        # Row 1: min/max interval controls
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel('Min (s):'))
        self.ac_min_spin = QDoubleSpinBox()
        self.ac_min_spin.setRange(0.5, 10.0)
        self.ac_min_spin.setValue(2.0)
        self.ac_min_spin.setSingleStep(0.1)
        self.ac_min_spin.setDecimals(1)
        interval_layout.addWidget(self.ac_min_spin)

        interval_layout.addWidget(QLabel('Max (s):'))
        self.ac_max_spin = QDoubleSpinBox()
        self.ac_max_spin.setRange(0.5, 10.0)
        self.ac_max_spin.setValue(4.0)
        self.ac_max_spin.setSingleStep(0.1)
        self.ac_max_spin.setDecimals(1)
        interval_layout.addWidget(self.ac_max_spin)
        auto_click_layout.addLayout(interval_layout)

        # Row 2: Set position + status label
        pos_layout = QHBoxLayout()
        self.ac_set_pos_btn = QPushButton('Set Click Position (3s delay)')
        self.ac_set_pos_btn.clicked.connect(self.ac_set_position)
        pos_layout.addWidget(self.ac_set_pos_btn)

        self.ac_pos_label = QLabel('Position: not set')
        pos_layout.addWidget(self.ac_pos_label)
        auto_click_layout.addLayout(pos_layout)

        # Row 3: Start / Stop / next interval preview
        ctrl_layout = QHBoxLayout()
        self.ac_start_btn = QPushButton('Start Auto Click')
        self.ac_start_btn.setStyleSheet('background-color: #44aa44; color: white; font-weight: bold;')
        self.ac_start_btn.clicked.connect(self.ac_start)
        self.ac_start_btn.setEnabled(False)
        ctrl_layout.addWidget(self.ac_start_btn)

        self.ac_stop_btn = QPushButton('Stop Auto Click')
        self.ac_stop_btn.setStyleSheet('background-color: #ff4444; color: white; font-weight: bold;')
        self.ac_stop_btn.clicked.connect(self.ac_stop)
        self.ac_stop_btn.setEnabled(False)
        ctrl_layout.addWidget(self.ac_stop_btn)

        self.ac_status_label = QLabel('Status: idle')
        ctrl_layout.addWidget(self.ac_status_label)
        auto_click_layout.addLayout(ctrl_layout)

        auto_click_group.setLayout(auto_click_layout)

        # === Macro Recorder UI ===
        macro_group = QGroupBox('Macro Recorder')
        macro_layout = QVBoxLayout()

        # Row 1: Record, Stop Recording, status
        macro_row1 = QHBoxLayout()
        self.macro_record_btn = QPushButton('Record')
        self.macro_record_btn.setStyleSheet('background-color: #cc4444; color: white; font-weight: bold;')
        self.macro_record_btn.clicked.connect(self.macro_start_recording)
        macro_row1.addWidget(self.macro_record_btn)

        self.macro_stop_record_btn = QPushButton('Stop Recording')
        self.macro_stop_record_btn.clicked.connect(self.macro_stop_recording)
        self.macro_stop_record_btn.setEnabled(False)
        macro_row1.addWidget(self.macro_stop_record_btn)

        self.macro_status_label = QLabel('Status: idle')
        macro_row1.addWidget(self.macro_status_label)
        macro_layout.addLayout(macro_row1)

        # Row 2: Macro dropdown, Play, Stop Playback, Loop checkbox, Delete
        macro_row2 = QHBoxLayout()
        self.macro_combo = QComboBox()
        self.macro_combo.setMinimumWidth(200)
        macro_row2.addWidget(self.macro_combo)

        self.macro_play_btn = QPushButton('Play')
        self.macro_play_btn.setStyleSheet('background-color: #44aa44; color: white; font-weight: bold;')
        self.macro_play_btn.clicked.connect(self.macro_play)
        self.macro_play_btn.setEnabled(False)
        macro_row2.addWidget(self.macro_play_btn)

        self.macro_stop_play_btn = QPushButton('Stop Playback')
        self.macro_stop_play_btn.setStyleSheet('background-color: #ff4444; color: white; font-weight: bold;')
        self.macro_stop_play_btn.clicked.connect(self.macro_stop_playback)
        self.macro_stop_play_btn.setEnabled(False)
        macro_row2.addWidget(self.macro_stop_play_btn)

        self.macro_loop_cb = QCheckBox('Loop')
        macro_row2.addWidget(self.macro_loop_cb)

        self.macro_delete_btn = QPushButton('Delete')
        self.macro_delete_btn.clicked.connect(self.macro_delete)
        self.macro_delete_btn.setEnabled(False)
        macro_row2.addWidget(self.macro_delete_btn)

        macro_layout.addLayout(macro_row2)
        macro_group.setLayout(macro_layout)

        self._refresh_macro_list()

        tools_layout = QHBoxLayout()
        tools_layout.addWidget(self.add_template_btn)
        tools_layout.addStretch()

        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        layout.addWidget(runs_group)
        layout.addWidget(arena_config_group)
        layout.addLayout(tools_layout)
        layout.addWidget(auto_click_group)
        layout.addWidget(macro_group)
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

    # ── Settings persistence ────────────────────────────────────────

    SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')

    def _load_settings(self):
        """Load saved settings from settings.json and apply to UI + config."""
        if not os.path.isfile(self.SETTINGS_FILE):
            return
        try:
            with open(self.SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
        except (OSError, json.JSONDecodeError):
            return

        if 'arena_max_power' in settings:
            val = int(settings['arena_max_power'])
            self.arena_max_power_spin.setValue(val)  # triggers _on_arena_max_power_changed
        if 'arena_max_level' in settings:
            val = int(settings['arena_max_level'])
            self.arena_max_level_spin.setValue(val)  # triggers _on_arena_max_level_changed
        if 'iron_twins_stage' in settings:
            val = int(settings['iron_twins_stage'])
            self.it_stage_spin.setValue(val)  # triggers _on_it_stage_changed
        if 'iron_twins_macro' in settings:
            macro_name = settings['iron_twins_macro']
            idx = self.it_macro_combo.findText(macro_name)
            if idx >= 0:
                self.it_macro_combo.setCurrentIndex(idx)

    def _save_settings(self):
        """Save current settings to settings.json."""
        settings = {
            'arena_max_power': config.ARENA_MAX_OPPONENT_POWER,
            'arena_max_level': config.ARENA_MAX_OPPONENT_LEVEL,
            'iron_twins_stage': config.IRON_TWINS_STAGE,
            'iron_twins_macro': self.it_macro_combo.currentText(),
        }
        try:
            with open(self.SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except OSError:
            pass

    # ── Arena config handlers ─────────────────────────────────────

    def _on_arena_max_power_changed(self, value):
        """Update the config module's ARENA_MAX_OPPONENT_POWER at runtime."""
        config.ARENA_MAX_OPPONENT_POWER = value
        if value == 0:
            self.log('Arena config: max power = no limit')
        else:
            self.log(f'Arena config: max power = {value:,}')
        self._save_settings()

    def _on_arena_max_level_changed(self, value):
        """Update the config module's ARENA_MAX_OPPONENT_LEVEL at runtime."""
        config.ARENA_MAX_OPPONENT_LEVEL = value
        if value == 0:
            self.log('Arena config: max level = no limit')
        else:
            self.log(f'Arena config: max level = {value}')
        self._save_settings()

    def _on_it_stage_changed(self, value):
        """Update the config module's IRON_TWINS_STAGE at runtime."""
        config.IRON_TWINS_STAGE = value
        self.log(f'Iron Twins: stage = {value}')
        self._save_settings()

    def _on_it_macro_changed(self, text):
        """Update the selected gear-up macro for Iron Twins."""
        self.log(f'Iron Twins: gear macro = {text}')
        self._save_settings()

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
    
    # ─── Run Methods ─────────────────────────────────────────────────

    def run_classic_arena(self):
        """Navigate from home to Classic Arena and run the full battle sequence."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_classic_arena_btn.setEnabled(False)

            self.log('')
            self.log('  Navigating to Classic Arena...')

            # Navigate: Home → Battle → Arena → Classic Arena
            steps = [
                ("Battle", TEMPLATE_BATTLE),
                ("Arena", TEMPLATE_ARENA),
                ("Classic Arena", TEMPLATE_CLASSIC_ARENA),
            ]

            for step_name, template_path in steps:
                if self.is_stop_requested():
                    self.log('  STOPPED BY USER')
                    return

                self.log(f'  Looking for "{step_name}"...')
                success, message = self.template_matcher.find_and_click(
                    template_path, wait_after=CLICK_DELAY
                )
                if success:
                    self.log(f'  Clicked "{step_name}"')
                else:
                    self.log(f'  Failed to find "{step_name}" — aborting')
                    return

            self.log('  Reached Classic Arena')
            self.log('')

            # Run the arena sequence
            v2 = ClassicArenaSequenceV2(
                self.window_capture, self.template_matcher,
                self.text_recognizer, self.log,
                stop_check=self.is_stop_requested
            )
            v2.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_classic_arena_btn.setEnabled(True)

    def run_free_shop_items(self):
        """Navigate to Shop and collect all free items."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_free_shop_btn.setEnabled(False)

            seq = FreeShopItemsSequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested,
                dry_run=False
            )
            seq.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_free_shop_btn.setEnabled(True)

    def run_bypass_junk(self):
        """Dismiss any popup junk offers on screen."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_bypass_junk_btn.setEnabled(False)

            seq = DismissJunkOffersSequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested
            )
            seq.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_bypass_junk_btn.setEnabled(True)

    def run_guardian_ring(self):
        """Click Guardian Ring and upgrade all available levels."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_guardian_btn.setEnabled(False)

            seq = GuardianRingSequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested
            )
            seq.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_guardian_btn.setEnabled(True)

    def run_collect_gem(self):
        """Find and click the collectGem icon on screen."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_collect_gem_btn.setEnabled(False)

            seq = CollectGemSequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested
            )
            seq.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_collect_gem_btn.setEnabled(True)

    def run_menu_rewards(self):
        """Find and click the checkMenu icon on screen."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_menu_rewards_btn.setEnabled(False)

            seq = MenuRewardsSequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested
            )
            seq.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_menu_rewards_btn.setEnabled(True)

    def run_check_market(self):
        """Find and click the freshMarket icon on screen."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_check_market_btn.setEnabled(False)

            seq = CheckMarketSequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested
            )
            seq.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_check_market_btn.setEnabled(True)

    def run_quests(self):
        """Open quests panel and log daily quest status."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_quests_btn.setEnabled(False)

            seq = QuestsSequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested
            )
            seq.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_quests_btn.setEnabled(True)

    def run_sum3(self):
        """Run the Summon 3 Champions quest sequence."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_sum3_btn.setEnabled(False)

            seq = Sum3Sequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested
            )
            seq.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_sum3_btn.setEnabled(True)

    def run_iron_twins(self):
        """Navigate to Iron Twins and fight the selected stage."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_iron_twins_btn.setEnabled(False)

            # Get gear-up macro name (None if "(None)" selected)
            macro_name = self.it_macro_combo.currentText()
            if macro_name == '(None)':
                macro_name = None

            seq = IronTwinsSequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested,
                gear_macro=macro_name,
            )
            seq.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_iron_twins_btn.setEnabled(True)

    # ─── Auto Clicker Methods ───────────────────────────────────────────

    def ac_set_position(self):
        """Give user 3 seconds to hover over the desired click target."""
        self.ac_set_pos_btn.setEnabled(False)
        self.ac_pos_label.setText('Move mouse to target...')
        self.log('Auto Clicker: move your mouse to the click target — capturing in 3s...')

        self._ac_countdown = 3
        self._ac_timer = QTimer(self)
        self._ac_timer.timeout.connect(self._ac_countdown_tick)
        self._ac_timer.start(1000)

    def _ac_countdown_tick(self):
        self._ac_countdown -= 1
        if self._ac_countdown > 0:
            self.ac_pos_label.setText(f'Capturing in {self._ac_countdown}...')
        else:
            self._ac_timer.stop()
            pos = pyautogui.position()
            self.auto_click_position = (pos.x, pos.y)
            self.ac_pos_label.setText(f'Position: ({pos.x}, {pos.y})')
            self.ac_set_pos_btn.setEnabled(True)
            self.ac_start_btn.setEnabled(True)
            self.log(f'Auto Clicker: position set to ({pos.x}, {pos.y})')

    def ac_start(self):
        """Start the auto clicker in a background thread."""
        if self.auto_click_running:
            return

        if self.auto_click_position is None:
            self.log('Auto Clicker: set a click position first!')
            return

        min_val = self.ac_min_spin.value()
        max_val = self.ac_max_spin.value()
        if min_val >= max_val:
            self.log('Auto Clicker: min must be less than max!')
            return

        # Reconfigure the clicker with current spin-box values
        self.auto_clicker = HumanClicker(min_interval=min_val, max_interval=max_val)

        self.auto_click_running = True
        self.ac_start_btn.setEnabled(False)
        self.ac_stop_btn.setEnabled(True)
        self.ac_set_pos_btn.setEnabled(False)
        self.ac_min_spin.setEnabled(False)
        self.ac_max_spin.setEnabled(False)
        self.ac_status_label.setText('Status: running')

        # Preview first few intervals in the log
        preview = self.auto_clicker.preview(8)
        preview_str = ', '.join(f'{v:.2f}' for v in preview)
        self.log(f'Auto Clicker: started at ({self.auto_click_position[0]}, {self.auto_click_position[1]})')
        self.log(f'  Interval range: {min_val:.1f}s – {max_val:.1f}s (clustered)')
        self.log(f'  Preview intervals: [{preview_str}, ...]')

        self.auto_click_thread = threading.Thread(target=self._ac_loop, daemon=True)
        self.auto_click_thread.start()

    def _ac_loop(self):
        """Background thread: click at human-like intervals."""
        x, y = self.auto_click_position
        click_count = 0

        while self.auto_click_running:
            interval = self.auto_clicker.next_interval()

            # Sleep in small increments so we can respond to stop quickly
            elapsed = 0.0
            while elapsed < interval and self.auto_click_running:
                chunk = min(0.1, interval - elapsed)
                time.sleep(chunk)
                elapsed += chunk

            if not self.auto_click_running:
                break

            hold = self.natural_click.click(x, y)
            click_count += 1

            # Log every click with its interval and hold duration
            # Use QTimer.singleShot to safely update the UI from this thread
            msg = f'  Click #{click_count}  (waited {interval:.2f}s, held {hold*1000:.0f}ms)'
            QTimer.singleShot(0, lambda m=msg: self._ac_log_from_thread(m))

    def _ac_log_from_thread(self, message):
        """Thread-safe logging helper."""
        self.log(message)

    def ac_stop(self):
        """Stop the auto clicker."""
        self.auto_click_running = False
        self.ac_start_btn.setEnabled(True)
        self.ac_stop_btn.setEnabled(False)
        self.ac_set_pos_btn.setEnabled(True)
        self.ac_min_spin.setEnabled(True)
        self.ac_max_spin.setEnabled(True)
        self.ac_status_label.setText('Status: idle')
        self.log('Auto Clicker: stopped')


    # ─── Macro Recorder Methods ────────────────────────────────────────

    def _refresh_macro_list(self):
        """Reload the macro dropdown from saved files on disk."""
        self.macro_combo.clear()
        macros = MacroRecorder.list_macros()
        self.macro_combo.addItems(macros)
        has_macros = len(macros) > 0
        self.macro_play_btn.setEnabled(has_macros)
        self.macro_delete_btn.setEnabled(has_macros)

    def macro_start_recording(self):
        """Start recording mouse clicks inside the game window."""
        try:
            self.macro_recorder.start()
            self.macro_record_btn.setEnabled(False)
            self.macro_stop_record_btn.setEnabled(True)
            self.macro_play_btn.setEnabled(False)
            self.macro_delete_btn.setEnabled(False)
            self.macro_status_label.setText('Status: RECORDING')
            self.macro_status_label.setStyleSheet('color: red; font-weight: bold;')
            self.log('Macro: recording started. Click inside the game window...')
        except Exception as e:
            self.log(f'Macro: failed to start recording: {e}')

    def macro_stop_recording(self):
        """Stop recording, prompt for a name, and save the macro."""
        clicks = self.macro_recorder.stop()
        self.macro_record_btn.setEnabled(True)
        self.macro_stop_record_btn.setEnabled(False)
        self.macro_status_label.setText('Status: idle')
        self.macro_status_label.setStyleSheet('')

        if not clicks:
            self.log('Macro: no clicks were recorded.')
            self._refresh_macro_list()
            return

        self.log(f'Macro: recorded {len(clicks)} click(s).')

        name, ok = QInputDialog.getText(self, 'Save Macro', 'Enter macro name:')
        if ok and name.strip():
            name = name.strip()
            filepath = self.macro_recorder.save(name)
            self.log(f'Macro: saved to {filepath}')
            self._refresh_macro_list()
            # Select the newly saved macro
            idx = self.macro_combo.findText(name)
            if idx >= 0:
                self.macro_combo.setCurrentIndex(idx)
        else:
            self.log('Macro: save cancelled.')
            self._refresh_macro_list()

    def macro_play(self):
        """Play the currently selected macro."""
        name = self.macro_combo.currentText()
        if not name:
            self.log('Macro: no macro selected.')
            return

        macro_data = MacroRecorder.load_macro(name)
        if not macro_data:
            self.log(f'Macro: failed to load "{name}".')
            return

        click_count = len(macro_data.get('clicks', []))
        if click_count == 0:
            self.log(f'Macro: "{name}" has no clicks.')
            return

        loop = self.macro_loop_cb.isChecked()
        self.macro_play_btn.setEnabled(False)
        self.macro_stop_play_btn.setEnabled(True)
        self.macro_record_btn.setEnabled(False)
        self.macro_delete_btn.setEnabled(False)
        mode = 'loop' if loop else 'single'
        self.macro_status_label.setText(f'Status: PLAYING ({mode})')
        self.macro_status_label.setStyleSheet('color: green; font-weight: bold;')

        self.log(f'Macro: playing "{name}" ({click_count} clicks, {mode})...')

        def _run():
            try:
                self.macro_player.play(macro_data, loop=loop)
            except Exception as e:
                QTimer.singleShot(0, lambda: self.log(f'Macro: playback error: {e}'))
            finally:
                QTimer.singleShot(0, self._macro_playback_finished)

        self.macro_play_thread = threading.Thread(target=_run, daemon=True)
        self.macro_play_thread.start()

    def _macro_playback_finished(self):
        """UI cleanup after playback ends (called on main thread via QTimer)."""
        self.macro_play_btn.setEnabled(True)
        self.macro_stop_play_btn.setEnabled(False)
        self.macro_record_btn.setEnabled(True)
        self.macro_status_label.setText('Status: idle')
        self.macro_status_label.setStyleSheet('')
        self._refresh_macro_list()
        self.log('Macro: playback finished.')

    def macro_stop_playback(self):
        """Signal macro playback to stop."""
        self.macro_player.stop()
        self.log('Macro: stop requested...')

    def macro_delete(self):
        """Delete the currently selected macro after confirmation."""
        name = self.macro_combo.currentText()
        if not name:
            return

        reply = QMessageBox.question(
            self, 'Delete Macro',
            f'Delete macro "{name}"?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            MacroRecorder.delete_macro(name)
            self.log(f'Macro: deleted "{name}".')
            self._refresh_macro_list()


def main():
    app = QApplication(sys.argv)
    window = DreamerApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
