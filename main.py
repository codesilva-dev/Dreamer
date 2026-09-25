import sys
import cv2
import threading
import time
import os
import json
import pyautogui
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pynput import keyboard as pynput_keyboard
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox, QGroupBox, QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QInputDialog, QTabWidget, QGridLayout)
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
from sequences.clan_boss import ClanBossSequence
from sequences.playtime_rewards import PlaytimeRewardsSequence
import config



class DreamerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Dreamer - Window Scanner')
        self.setGeometry(100, 100, 1100, 850)

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

        # Daily loop state
        self.daily_loop_running = False
        self.daily_loop_cycle = 0
        self.daily_loop_task_index = 0
        self.daily_wait_timer = None

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

        # Daily state tracking (7 PM EST reset cycle)
        self.daily_state = {
            'last_reset': None,           # datetime: last acknowledged 7 PM boundary
            'it_keys_exhausted': False,   # Iron Twins: True when 0/6 keys
        }

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

        # ── Global stylesheet for larger, more readable UI ──
        self.setStyleSheet("""
            QWidget { font-size: 12pt; }
            QPushButton {
                min-height: 36px;
                padding: 6px 14px;
                font-size: 12pt;
            }
            QGroupBox {
                font-size: 13pt;
                font-weight: bold;
                margin-top: 10px;
                padding-top: 16px;
            }
            QGroupBox::title { subcontrol-position: top left; padding: 4px 8px; }
            QTabWidget::pane { border: 1px solid #888; padding: 6px; }
            QTabBar::tab {
                font-size: 12pt;
                padding: 8px 20px;
                min-width: 100px;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                min-height: 32px;
                font-size: 12pt;
            }
            QCheckBox { font-size: 12pt; }
            QLabel { font-size: 12pt; }
        """)

        # ── Shared widgets ──
        self.stop_btn = QPushButton('STOP')
        self.stop_btn.clicked.connect(self.request_stop)
        self.stop_btn.setStyleSheet(
            'background-color: #ff4444; color: white; font-weight: bold; font-size: 14pt; min-height: 44px;')
        self.stop_btn.setEnabled(False)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet('font-family: Consolas, monospace; font-size: 11pt;')

        # ── Tab widget ──
        tabs = QTabWidget()

        # ============================================================
        # TAB 1: Sequences
        # ============================================================
        seq_tab = QWidget()
        seq_layout = QVBoxLayout()

        # --- Daily Loop section ---
        daily_group = QGroupBox('Daily Loop')
        daily_layout = QHBoxLayout()

        self.daily_loop_btn = QPushButton('Start Daily Loop')
        self.daily_loop_btn.setStyleSheet(
            'background-color: #4488cc; color: white; font-weight: bold; font-size: 13pt; min-height: 40px;')
        self.daily_loop_btn.clicked.connect(self.start_daily_loop)
        daily_layout.addWidget(self.daily_loop_btn)

        self.daily_loop_hourly_cb = QCheckBox('Loop every hour')
        self.daily_loop_hourly_cb.setToolTip('After completing all tasks, wait 60 minutes and run again')
        daily_layout.addWidget(self.daily_loop_hourly_cb)

        self.daily_status_label = QLabel('Status: idle')
        daily_layout.addWidget(self.daily_status_label)

        daily_layout.addStretch()
        daily_layout.addWidget(self.stop_btn)
        daily_group.setLayout(daily_layout)
        seq_layout.addWidget(daily_group)

        # --- Run buttons in a grid ---
        runs_group = QGroupBox('Run Sequences')
        runs_grid = QGridLayout()
        runs_grid.setSpacing(8)

        # Row 0: Daily / Quest related
        self.run_quests_btn = QPushButton('Quests')
        self.run_quests_btn.clicked.connect(self.run_quests)
        runs_grid.addWidget(self.run_quests_btn, 0, 0)

        self.run_sum3_btn = QPushButton('Sum3')
        self.run_sum3_btn.clicked.connect(self.run_sum3)
        runs_grid.addWidget(self.run_sum3_btn, 0, 1)

        self.run_collect_gem_btn = QPushButton('Collect Gem')
        self.run_collect_gem_btn.clicked.connect(self.run_collect_gem)
        runs_grid.addWidget(self.run_collect_gem_btn, 0, 2)

        self.run_menu_rewards_btn = QPushButton('Menu Rewards')
        self.run_menu_rewards_btn.clicked.connect(self.run_menu_rewards)
        runs_grid.addWidget(self.run_menu_rewards_btn, 0, 3)

        # Row 1: Rewards / Shop
        self.run_playtime_btn = QPushButton('Playtime Rewards')
        self.run_playtime_btn.clicked.connect(self.run_playtime_rewards)
        runs_grid.addWidget(self.run_playtime_btn, 1, 0)

        self.run_free_shop_btn = QPushButton('Free Shop Items')
        self.run_free_shop_btn.clicked.connect(self.run_free_shop_items)
        runs_grid.addWidget(self.run_free_shop_btn, 1, 1)

        self.run_check_market_btn = QPushButton('Check Market')
        self.run_check_market_btn.clicked.connect(self.run_check_market)
        runs_grid.addWidget(self.run_check_market_btn, 1, 2)

        self.run_guardian_btn = QPushButton('Guardian Ring')
        self.run_guardian_btn.clicked.connect(self.run_guardian_ring)
        runs_grid.addWidget(self.run_guardian_btn, 1, 3)

        # Row 2: Combat
        self.run_classic_arena_btn = QPushButton('Classic Arena')
        self.run_classic_arena_btn.clicked.connect(self.run_classic_arena)
        runs_grid.addWidget(self.run_classic_arena_btn, 2, 0)

        self.run_bypass_junk_btn = QPushButton('Bypass Junk')
        self.run_bypass_junk_btn.clicked.connect(self.run_bypass_junk)
        runs_grid.addWidget(self.run_bypass_junk_btn, 2, 1)

        # Row 3: Iron Twins (button + stage + macro)
        self.run_iron_twins_btn = QPushButton('Iron Twins')
        self.run_iron_twins_btn.clicked.connect(self.run_iron_twins)
        runs_grid.addWidget(self.run_iron_twins_btn, 3, 0)

        it_config = QHBoxLayout()
        it_config.addWidget(QLabel('Stage:'))
        self.it_stage_spin = QSpinBox()
        self.it_stage_spin.setRange(1, 15)
        self.it_stage_spin.setValue(config.IRON_TWINS_STAGE)
        self.it_stage_spin.setToolTip('Iron Twins stage (1-15)')
        self.it_stage_spin.valueChanged.connect(self._on_it_stage_changed)
        it_config.addWidget(self.it_stage_spin)
        it_config.addWidget(QLabel('Gear Macro:'))
        self.it_macro_combo = QComboBox()
        self.it_macro_combo.setMinimumWidth(140)
        self.it_macro_combo.setToolTip('Macro to run after stage selection (gear swap)')
        self.it_macro_combo.addItem('(None)')
        self.it_macro_combo.addItems(MacroRecorder.list_macros())
        self.it_macro_combo.currentTextChanged.connect(self._on_it_macro_changed)
        it_config.addWidget(self.it_macro_combo)
        it_config.addStretch()
        runs_grid.addLayout(it_config, 3, 1, 1, 3)

        # Row 4: Clan Boss (button + difficulty)
        self.run_cb_main_btn = QPushButton('Clan Boss')
        self.run_cb_main_btn.clicked.connect(self.run_cb_main)
        runs_grid.addWidget(self.run_cb_main_btn, 4, 0)

        cb_config = QHBoxLayout()
        cb_config.addWidget(QLabel('Difficulty:'))
        self.cb_difficulty_combo = QComboBox()
        self.cb_difficulty_combo.addItems(config.CB_DIFFICULTIES)
        self.cb_difficulty_combo.setCurrentText(config.CB_DIFFICULTY)
        self.cb_difficulty_combo.setToolTip('Clan Boss difficulty')
        self.cb_difficulty_combo.currentTextChanged.connect(self._on_cb_difficulty_changed)
        cb_config.addWidget(self.cb_difficulty_combo)
        cb_config.addStretch()
        runs_grid.addLayout(cb_config, 4, 1, 1, 3)

        runs_group.setLayout(runs_grid)
        seq_layout.addWidget(runs_group)
        seq_layout.addStretch()

        seq_tab.setLayout(seq_layout)
        tabs.addTab(seq_tab, 'Sequences')

        # ============================================================
        # TAB 2: Arena Config
        # ============================================================
        arena_tab = QWidget()
        arena_layout = QVBoxLayout()

        arena_config_group = QGroupBox('Arena Opponent Filters')
        arena_grid = QGridLayout()
        arena_grid.setSpacing(10)

        arena_grid.addWidget(QLabel('Max Power:'), 0, 0)
        self.arena_max_power_spin = QSpinBox()
        self.arena_max_power_spin.setRange(0, 999000)
        self.arena_max_power_spin.setSingleStep(10000)
        self.arena_max_power_spin.setValue(config.ARENA_MAX_OPPONENT_POWER)
        self.arena_max_power_spin.setSpecialValueText('No limit')
        self.arena_max_power_spin.setToolTip('Skip opponents above this power (0 = no limit)')
        self.arena_max_power_spin.valueChanged.connect(self._on_arena_max_power_changed)
        arena_grid.addWidget(self.arena_max_power_spin, 0, 1)

        arena_grid.addWidget(QLabel('Max Level:'), 1, 0)
        self.arena_max_level_spin = QSpinBox()
        self.arena_max_level_spin.setRange(0, 100)
        self.arena_max_level_spin.setSingleStep(1)
        self.arena_max_level_spin.setValue(config.ARENA_MAX_OPPONENT_LEVEL)
        self.arena_max_level_spin.setSpecialValueText('No limit')
        self.arena_max_level_spin.setToolTip('Skip opponents above this level (0 = no limit)')
        self.arena_max_level_spin.valueChanged.connect(self._on_arena_max_level_changed)
        arena_grid.addWidget(self.arena_max_level_spin, 1, 1)

        arena_grid.addWidget(QLabel('OR Power \u2264:'), 2, 0)
        self.arena_or_power_spin = QSpinBox()
        self.arena_or_power_spin.setRange(0, 999000)
        self.arena_or_power_spin.setSingleStep(10000)
        self.arena_or_power_spin.setValue(config.ARENA_OR_POWER)
        self.arena_or_power_spin.setSpecialValueText('Off')
        self.arena_or_power_spin.setToolTip(
            'Always fight opponents at or below this power, regardless of level (0 = off)')
        self.arena_or_power_spin.valueChanged.connect(self._on_arena_or_power_changed)
        arena_grid.addWidget(self.arena_or_power_spin, 2, 1)

        arena_config_group.setLayout(arena_grid)
        arena_layout.addWidget(arena_config_group)
        arena_layout.addStretch()

        arena_tab.setLayout(arena_layout)
        tabs.addTab(arena_tab, 'Arena Config')

        # ============================================================
        # TAB 3: Tools
        # ============================================================
        tools_tab = QWidget()
        tools_layout = QVBoxLayout()

        # --- Auto Clicker ---
        auto_click_group = QGroupBox('Auto Clicker')
        auto_click_layout = QVBoxLayout()

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
        interval_layout.addStretch()
        auto_click_layout.addLayout(interval_layout)

        pos_layout = QHBoxLayout()
        self.ac_set_pos_btn = QPushButton('Set Click Position (3s delay)')
        self.ac_set_pos_btn.clicked.connect(self.ac_set_position)
        pos_layout.addWidget(self.ac_set_pos_btn)
        self.ac_pos_label = QLabel('Position: not set')
        pos_layout.addWidget(self.ac_pos_label)
        pos_layout.addStretch()
        auto_click_layout.addLayout(pos_layout)

        ctrl_layout = QHBoxLayout()
        self.ac_start_btn = QPushButton('Start Auto Click')
        self.ac_start_btn.setStyleSheet(
            'background-color: #44aa44; color: white; font-weight: bold;')
        self.ac_start_btn.clicked.connect(self.ac_start)
        self.ac_start_btn.setEnabled(False)
        ctrl_layout.addWidget(self.ac_start_btn)
        self.ac_stop_btn = QPushButton('Stop Auto Click')
        self.ac_stop_btn.setStyleSheet(
            'background-color: #ff4444; color: white; font-weight: bold;')
        self.ac_stop_btn.clicked.connect(self.ac_stop)
        self.ac_stop_btn.setEnabled(False)
        ctrl_layout.addWidget(self.ac_stop_btn)
        self.ac_status_label = QLabel('Status: idle')
        ctrl_layout.addWidget(self.ac_status_label)
        ctrl_layout.addStretch()
        auto_click_layout.addLayout(ctrl_layout)

        auto_click_group.setLayout(auto_click_layout)
        tools_layout.addWidget(auto_click_group)

        # --- Macro Recorder ---
        macro_group = QGroupBox('Macro Recorder')
        macro_layout = QVBoxLayout()

        macro_row1 = QHBoxLayout()
        self.macro_record_btn = QPushButton('Record')
        self.macro_record_btn.setStyleSheet(
            'background-color: #cc4444; color: white; font-weight: bold;')
        self.macro_record_btn.clicked.connect(self.macro_start_recording)
        macro_row1.addWidget(self.macro_record_btn)
        self.macro_stop_record_btn = QPushButton('Stop Recording')
        self.macro_stop_record_btn.clicked.connect(self.macro_stop_recording)
        self.macro_stop_record_btn.setEnabled(False)
        macro_row1.addWidget(self.macro_stop_record_btn)
        self.macro_status_label = QLabel('Status: idle')
        macro_row1.addWidget(self.macro_status_label)
        macro_row1.addStretch()
        macro_layout.addLayout(macro_row1)

        macro_row2 = QHBoxLayout()
        self.macro_combo = QComboBox()
        self.macro_combo.setMinimumWidth(200)
        macro_row2.addWidget(self.macro_combo)
        self.macro_play_btn = QPushButton('Play')
        self.macro_play_btn.setStyleSheet(
            'background-color: #44aa44; color: white; font-weight: bold;')
        self.macro_play_btn.clicked.connect(self.macro_play)
        self.macro_play_btn.setEnabled(False)
        macro_row2.addWidget(self.macro_play_btn)
        self.macro_stop_play_btn = QPushButton('Stop Playback')
        self.macro_stop_play_btn.setStyleSheet(
            'background-color: #ff4444; color: white; font-weight: bold;')
        self.macro_stop_play_btn.clicked.connect(self.macro_stop_playback)
        self.macro_stop_play_btn.setEnabled(False)
        macro_row2.addWidget(self.macro_stop_play_btn)
        self.macro_loop_cb = QCheckBox('Loop')
        macro_row2.addWidget(self.macro_loop_cb)
        self.macro_delete_btn = QPushButton('Delete')
        self.macro_delete_btn.clicked.connect(self.macro_delete)
        self.macro_delete_btn.setEnabled(False)
        macro_row2.addWidget(self.macro_delete_btn)
        macro_row2.addStretch()
        macro_layout.addLayout(macro_row2)

        macro_group.setLayout(macro_layout)
        tools_layout.addWidget(macro_group)

        # --- Template capture ---
        template_group = QGroupBox('Template Capture')
        template_layout = QVBoxLayout()

        self.add_template_btn = QPushButton('Add Template')
        self.add_template_btn.clicked.connect(self.start_region_selection)
        template_layout.addWidget(self.add_template_btn)

        self.image_label = QLabel('Click "Add Template" to capture a screen region')
        self.image_label.setAlignment(Qt.AlignCenter)
        template_layout.addWidget(self.image_label)

        template_group.setLayout(template_layout)
        tools_layout.addWidget(template_group)

        tools_layout.addStretch()
        tools_tab.setLayout(tools_layout)
        tabs.addTab(tools_tab, 'Tools')

        self._refresh_macro_list()

        # ============================================================
        # Main layout: tabs on top, log always visible below
        # ============================================================
        layout = QVBoxLayout()
        layout.addWidget(tabs, stretch=1)
        log_label = QLabel('Log:')
        log_label.setStyleSheet('font-weight: bold; font-size: 12pt;')
        layout.addWidget(log_label)
        layout.addWidget(self.log_output, stretch=1)
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
        if 'arena_or_power' in settings:
            val = int(settings['arena_or_power'])
            self.arena_or_power_spin.setValue(val)  # triggers _on_arena_or_power_changed
        if 'iron_twins_stage' in settings:
            val = int(settings['iron_twins_stage'])
            self.it_stage_spin.setValue(val)  # triggers _on_it_stage_changed
        if 'iron_twins_macro' in settings:
            macro_name = settings['iron_twins_macro']
            idx = self.it_macro_combo.findText(macro_name)
            if idx >= 0:
                self.it_macro_combo.setCurrentIndex(idx)
        if 'cb_difficulty' in settings:
            val = settings['cb_difficulty']
            if val in config.CB_DIFFICULTIES:
                self.cb_difficulty_combo.setCurrentText(val)

        # Daily state
        if 'daily_state' in settings:
            ds = settings['daily_state']
            if ds.get('last_reset'):
                try:
                    self.daily_state['last_reset'] = datetime.fromisoformat(ds['last_reset'])
                except (ValueError, TypeError):
                    pass
            self.daily_state['it_keys_exhausted'] = ds.get('it_keys_exhausted', False)

    def _save_settings(self):
        """Save current settings to settings.json."""
        # Serialize daily_state for JSON
        ds_serialized = {
            'last_reset': self.daily_state['last_reset'].isoformat()
                          if self.daily_state['last_reset'] else None,
            'it_keys_exhausted': self.daily_state['it_keys_exhausted'],
        }

        settings = {
            'arena_max_power': config.ARENA_MAX_OPPONENT_POWER,
            'arena_max_level': config.ARENA_MAX_OPPONENT_LEVEL,
            'arena_or_power': config.ARENA_OR_POWER,
            'iron_twins_stage': config.IRON_TWINS_STAGE,
            'iron_twins_macro': self.it_macro_combo.currentText(),
            'cb_difficulty': config.CB_DIFFICULTY,
            'daily_state': ds_serialized,
        }
        try:
            with open(self.SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except OSError:
            pass

    # ── Daily reset (7 PM EST cycle) ─────────────────────────────

    def _check_daily_reset(self):
        """
        Check if 7 PM EST has passed since last reset. If so, clear all
        exhaustion flags. Call this at the top of each daily loop iteration.

        Safe to call at any time — if the app was busy at 7 PM, it will
        catch the reset whenever it next checks (7:05, 7:30, etc.).
        """
        est = ZoneInfo('America/New_York')
        now = datetime.now(est)

        # Find the most recent 7 PM EST boundary
        today_reset = now.replace(hour=19, minute=0, second=0, microsecond=0)
        if now < today_reset:
            last_boundary = today_reset - timedelta(days=1)
        else:
            last_boundary = today_reset

        # If we've never reset, or the last reset was before the latest boundary
        last = self.daily_state['last_reset']
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=est)

        if last is None or last < last_boundary:
            self.daily_state['last_reset'] = now
            self.daily_state['it_keys_exhausted'] = False
            # Future flags reset here too
            self._save_settings()
            return True  # reset occurred
        return False  # no reset needed

    def _it_keys_available(self):
        """Check if Iron Twins keys are available (not exhausted this cycle)."""
        return not self.daily_state['it_keys_exhausted']

    def _mark_it_keys_exhausted(self):
        """Mark Iron Twins keys as exhausted for this daily cycle."""
        self.daily_state['it_keys_exhausted'] = True
        self._save_settings()

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

    def _on_arena_or_power_changed(self, value):
        """Update the config module's ARENA_OR_POWER at runtime."""
        config.ARENA_OR_POWER = value
        if value == 0:
            self.log('Arena config: OR power = off')
        else:
            self.log(f'Arena config: OR power ≤ {value:,}')
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

    def _on_cb_difficulty_changed(self, text):
        """Update the config module's CB_DIFFICULTY at runtime."""
        config.CB_DIFFICULTY = text
        self.log(f'Clan Boss: difficulty = {text}')
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

    def run_playtime_rewards(self):
        """Collect all available playtime rewards."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_playtime_btn.setEnabled(False)

            seq = PlaytimeRewardsSequence(
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
            self.run_playtime_btn.setEnabled(True)

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

            # Check daily reset and key availability
            self._check_daily_reset()
            if not self._it_keys_available():
                self.log('Iron Twins: no keys remaining (resets at 7 PM EST)')
                return

            # Get gear-up macro name (None if "(None)" selected)
            macro_name = self.it_macro_combo.currentText()
            if macro_name == '(None)':
                macro_name = None

            seq = IronTwinsSequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested,
                gear_macro=macro_name,
            )
            result = seq.run()

            # If the sequence reports keys exhausted, mark state
            if result and isinstance(result, dict) and result.get('keys_exhausted'):
                self._mark_it_keys_exhausted()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_iron_twins_btn.setEnabled(True)

    def run_cb_main(self):
        """Navigate to Clan Boss and select the configured difficulty."""
        try:
            self.stop_requested = False
            self.stop_btn.setEnabled(True)
            self.run_cb_main_btn.setEnabled(False)

            seq = ClanBossSequence(
                self.window_capture, self.template_matcher,
                self.log, stop_check=self.is_stop_requested,
            )
            seq.run()

        except Exception as e:
            import traceback
            self.log(f'Error: {e}')
            self.log(traceback.format_exc())
        finally:
            self.stop_btn.setEnabled(False)
            self.stop_requested = False
            self.run_cb_main_btn.setEnabled(True)

    # ─── Daily Loop ─────────────────────────────────────────────────────

    # ── Daily task list (order matters — all start from home screen) ──

    DAILY_TASKS = [
        'Dismiss Junk Offers',
        'Collect Gem',
        'Free Shop Items',
        'Menu Rewards',
        'Playtime Rewards',
        'Guardian Ring',
        'Check Market',
        'CB Main',
        'Iron Twins',
        'Classic Arena',
        'Quests',
    ]

    def start_daily_loop(self):
        """Start or stop the daily loop."""
        if self.daily_loop_running:
            # Stop it
            self.daily_loop_running = False
            self.stop_requested = True
            self.daily_loop_btn.setText('Start Daily Loop')
            self.daily_loop_btn.setStyleSheet('background-color: #4488cc; color: white; font-weight: bold;')
            self.daily_status_label.setText('Status: stopping...')
            self.log('')
            self.log('Daily Loop: stop requested — will finish current task first')
            if self.daily_wait_timer:
                self.daily_wait_timer.stop()
                self.daily_wait_timer = None
            return

        # Start it
        self.daily_loop_running = True
        self.stop_requested = False
        self.daily_loop_cycle = 0
        self.daily_loop_task_index = 0
        self.daily_loop_btn.setText('Stop Daily Loop')
        self.daily_loop_btn.setStyleSheet('background-color: #ff4444; color: white; font-weight: bold;')
        self.daily_status_label.setText('Status: running')
        self.stop_btn.setEnabled(True)

        self.log('')
        self.log('Daily Loop started')

        # Kick off first cycle (runs on main thread via QTimer)
        QTimer.singleShot(0, self._daily_start_cycle)

    def _daily_log(self, msg):
        """Log for the daily loop (runs on main thread, so direct call is fine)."""
        self.log(msg)

    def _daily_start_cycle(self):
        """Begin a new daily cycle."""
        if not self.daily_loop_running:
            self._daily_loop_finished()
            return

        self.daily_loop_cycle += 1
        self.daily_loop_task_index = 0

        self.log('')
        self.log('=' * 60)
        self.log(f'  DAILY LOOP — Cycle {self.daily_loop_cycle}')
        self.log('=' * 60)
        self.daily_status_label.setText(f'Status: cycle {self.daily_loop_cycle}')

        # Check daily reset
        if self._check_daily_reset():
            self.log('  Daily reset (7 PM EST) — all tasks refreshed')

        # Start first task
        QTimer.singleShot(500, self._daily_run_next_task)

    def _daily_run_next_task(self):
        """Run the next task in the daily loop (on main thread)."""
        if not self.daily_loop_running:
            self._daily_loop_finished()
            return

        tasks = self.DAILY_TASKS
        idx = self.daily_loop_task_index

        if idx >= len(tasks):
            # All tasks done — run a re-check pass
            self._daily_recheck_pass()
            return

        task_name = tasks[idx]
        self.log(f'')
        self.log(f'  >> {task_name}')
        self.daily_status_label.setText(f'Status: {task_name}')
        QApplication.processEvents()

        # Dismiss junk offers BEFORE the task (clears any popup blockers)
        if task_name != 'Dismiss Junk Offers':
            self._daily_dismiss_junk()

        # Run the task (blocking on main thread — same as individual Run buttons)
        try:
            task_func = self._daily_get_task_func(task_name)
            task_func()
        except Exception as e:
            import traceback
            self.log(f'  [{task_name}] ERROR: {e}')
            for line in traceback.format_exc().split('\n'):
                self.log(f'    {line}')

        self.log(f'  << {task_name} done')

        if not self.daily_loop_running:
            self._daily_loop_finished()
            return

        # Move to next task
        self.daily_loop_task_index += 1

        # Schedule next task with a brief pause (keeps UI responsive)
        QTimer.singleShot(1000, self._daily_run_next_task)

    def _daily_get_task_func(self, task_name):
        """Map task name to its function."""
        mapping = {
            'Dismiss Junk Offers': self._daily_dismiss_junk,
            'Collect Gem': self._daily_collect_gem,
            'Free Shop Items': self._daily_free_shop,
            'Menu Rewards': self._daily_menu_rewards,
            'Playtime Rewards': self._daily_playtime_rewards,
            'Guardian Ring': self._daily_guardian_ring,
            'Check Market': self._daily_check_market,
            'CB Main': self._daily_cb_main,
            'Iron Twins': self._daily_iron_twins,
            'Classic Arena': self._daily_classic_arena,
            'Quests': self._daily_quests,
        }
        return mapping[task_name]

    # Tasks that can become available again during the cycle (e.g. playtime
    # reward unlocks after time passes, new gem appears, etc.). These are
    # re-run once at the end of the cycle to catch anything that unlocked
    # while later tasks were running.
    RECHECK_TASKS = [
        'Dismiss Junk Offers',
        'Collect Gem',
        'Free Shop Items',
        'Menu Rewards',
        'Playtime Rewards',
    ]

    def _daily_recheck_pass(self):
        """
        Re-run high-priority collection tasks that may have become
        available while later tasks (arena, dungeons, etc.) were running.
        """
        if not self.daily_loop_running:
            self._daily_loop_finished()
            return

        self.log('')
        self.log('  --- Re-check pass (catching newly available items) ---')
        self.daily_status_label.setText('Status: re-check pass')
        QApplication.processEvents()

        for task_name in self.RECHECK_TASKS:
            if not self.daily_loop_running or self.is_stop_requested():
                break

            # Dismiss junk before each re-check
            if task_name != 'Dismiss Junk Offers':
                self._daily_dismiss_junk()

            self.log(f'  >> {task_name} (re-check)')
            try:
                task_func = self._daily_get_task_func(task_name)
                task_func()
            except Exception as e:
                import traceback
                self.log(f'  [{task_name}] re-check ERROR: {e}')
                for line in traceback.format_exc().split('\n'):
                    self.log(f'    {line}')
            self.log(f'  << {task_name} re-check done')

        self.log('  --- Re-check pass complete ---')

        # Now proceed to end-of-cycle handling
        self._daily_cycle_complete()

    def _daily_cycle_complete(self):
        """Handle end of a daily cycle."""
        if not self.daily_loop_running:
            self._daily_loop_finished()
            return

        cycle = self.daily_loop_cycle

        if not self.daily_loop_hourly_cb.isChecked():
            self.log('')
            self.log(f'  Cycle {cycle} complete — "Loop every hour" is off, stopping')
            self._daily_loop_finished()
            return

        # Wait 60 minutes before next cycle
        self.log('')
        self.log(f'  Cycle {cycle} complete — waiting 60 min before next cycle')
        self.daily_status_label.setText('Status: waiting (60min)')

        # Use QTimer for the wait (non-blocking, main thread)
        self._daily_wait_elapsed = 0
        self.daily_wait_timer = QTimer()
        self.daily_wait_timer.setInterval(1000)  # tick every second
        self.daily_wait_timer.timeout.connect(self._daily_wait_tick)
        self.daily_wait_timer.start()

    def _daily_wait_tick(self):
        """Called every second during the 60-minute wait."""
        if not self.daily_loop_running:
            if self.daily_wait_timer:
                self.daily_wait_timer.stop()
                self.daily_wait_timer = None
            self._daily_loop_finished()
            return

        self._daily_wait_elapsed += 1

        # Log every 10 minutes
        if self._daily_wait_elapsed % 600 == 0:
            remaining = 60 - self._daily_wait_elapsed // 60
            self.log(f'  {remaining} min remaining...')

        # After 60 minutes, start next cycle
        if self._daily_wait_elapsed >= 60 * 60:
            self.daily_wait_timer.stop()
            self.daily_wait_timer = None
            self._daily_start_cycle()

    def _daily_loop_finished(self):
        """UI cleanup when daily loop stops."""
        cycle = self.daily_loop_cycle
        self.log('')
        self.log(f'  Daily Loop stopped after {cycle} cycle(s)')
        self.daily_loop_running = False
        self.stop_requested = False
        self.daily_loop_btn.setText('Start Daily Loop')
        self.daily_loop_btn.setStyleSheet('background-color: #4488cc; color: white; font-weight: bold;')
        self.daily_status_label.setText('Status: idle')
        self.stop_btn.setEnabled(False)

    # ── Daily task wrappers (run on main thread) ──────────────

    def _daily_dismiss_junk(self):
        seq = DismissJunkOffersSequence(
            self.window_capture, self.template_matcher,
            self._daily_log, stop_check=self.is_stop_requested
        )
        seq.run()

    def _daily_collect_gem(self):
        seq = CollectGemSequence(
            self.window_capture, self.template_matcher,
            self._daily_log, stop_check=self.is_stop_requested
        )
        seq.run()

    def _daily_free_shop(self):
        seq = FreeShopItemsSequence(
            self.window_capture, self.template_matcher,
            self._daily_log, stop_check=self.is_stop_requested,
            dry_run=False
        )
        seq.run()

    def _daily_menu_rewards(self):
        seq = MenuRewardsSequence(
            self.window_capture, self.template_matcher,
            self._daily_log, stop_check=self.is_stop_requested
        )
        seq.run()

    def _daily_playtime_rewards(self):
        seq = PlaytimeRewardsSequence(
            self.window_capture, self.template_matcher,
            self._daily_log, stop_check=self.is_stop_requested
        )
        seq.run()

    def _daily_guardian_ring(self):
        seq = GuardianRingSequence(
            self.window_capture, self.template_matcher,
            self._daily_log, stop_check=self.is_stop_requested
        )
        seq.run()

    def _daily_check_market(self):
        seq = CheckMarketSequence(
            self.window_capture, self.template_matcher,
            self._daily_log, stop_check=self.is_stop_requested
        )
        seq.run()

    def _daily_cb_main(self):
        seq = ClanBossSequence(
            self.window_capture, self.template_matcher,
            self._daily_log, stop_check=self.is_stop_requested,
        )
        seq.run()

    def _daily_iron_twins(self):
        # Check key availability (daily reset already checked at cycle start)
        if not self._it_keys_available():
            self._daily_log('  Iron Twins: skipped (no keys)')
            return

        macro_name = self.it_macro_combo.currentText()
        if macro_name == '(None)':
            macro_name = None

        seq = IronTwinsSequence(
            self.window_capture, self.template_matcher,
            self._daily_log, stop_check=self.is_stop_requested,
            gear_macro=macro_name,
        )
        result = seq.run()

        if result and isinstance(result, dict) and result.get('keys_exhausted'):
            self._mark_it_keys_exhausted()
            self._daily_log('  Iron Twins: keys exhausted (resets at 7 PM EST)')

    def _daily_quests(self):
        seq = QuestsSequence(
            self.window_capture, self.template_matcher,
            self._daily_log, stop_check=self.is_stop_requested
        )
        seq.run()

    def _daily_classic_arena(self):
        """Navigate to Classic Arena and run the battle sequence."""
        self._daily_log('')
        self._daily_log('  Navigating to Classic Arena...')

        steps = [
            ("Battle", TEMPLATE_BATTLE),
            ("Arena", TEMPLATE_ARENA),
            ("Classic Arena", TEMPLATE_CLASSIC_ARENA),
        ]

        for step_name, template_path in steps:
            if self.is_stop_requested():
                return

            self._daily_log(f'  Looking for "{step_name}"...')
            success, message = self.template_matcher.find_and_click(
                template_path, wait_after=CLICK_DELAY
            )
            if success:
                self._daily_log(f'  Clicked "{step_name}"')
            else:
                self._daily_log(f'  Failed to find "{step_name}" — skipping arena')
                return

        self._daily_log('  Reached Classic Arena')

        v2 = ClassicArenaSequenceV2(
            self.window_capture, self.template_matcher,
            self.text_recognizer, self._daily_log,
            stop_check=self.is_stop_requested
        )
        v2.run()

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
    # Global exception hook — prevents silent crashes
    def exception_hook(exc_type, exc_value, exc_tb):
        import traceback
        lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        msg = ''.join(lines)
        print(f'UNHANDLED EXCEPTION:\n{msg}', flush=True)
        # Also write to log file so it survives a crash
        try:
            from utils import _get_file_logger
            logger = _get_file_logger()
            logger.error(f'UNHANDLED EXCEPTION:\n{msg}')
            for handler in logger.handlers:
                handler.flush()
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = exception_hook

    app = QApplication(sys.argv)
    window = DreamerApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
