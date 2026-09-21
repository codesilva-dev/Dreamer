"""
Macro Recorder - Records and replays mouse click macros relative to the game window.

Recording captures click positions as fractions of the window dimensions (0.0-1.0)
so macros work regardless of window position. Timing between clicks and click hold
durations are recorded and replayed with slight natural variance.
"""

import json
import os
import random
import time
import threading
from datetime import datetime

import pyautogui
from pynput import mouse as pynput_mouse

from config import MACROS_DIR


class MacroRecorder:
    """
    Records mouse clicks and drags inside the game window.

    Captures:
      - Click/drag start position as fraction of window width/height
      - Drag end position (rel_end_x, rel_end_y) if mouse moved during hold
      - Delay between consecutive actions
      - Hold duration (mouseDown to mouseUp)
    """

    def __init__(self, window_capture, log_func=None):
        self.window_capture = window_capture
        self.log = log_func or print

        self.recording = False
        self.clicks = []
        self._pending_down = None
        self._last_click_time = None
        self._listener = None
        self._window_rect = None  # (left, top, width, height)

    def start(self):
        """Begin recording. Locks to the game window and starts listening."""
        self._window_rect = self.window_capture.get_window()
        if not self._window_rect:
            raise RuntimeError("Could not find game window")

        self.clicks = []
        self._pending_down = None
        self._last_click_time = None
        self.recording = True

        self._listener = pynput_mouse.Listener(on_click=self._on_click)
        self._listener.start()

        left, top, w, h = self._window_rect
        self.log(f"  Locked to window at ({left}, {top}) size {w}x{h}")

    def stop(self):
        """Stop recording and return the list of recorded clicks."""
        self.recording = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        return self.clicks

    def _on_click(self, x, y, button, pressed):
        """pynput callback — runs on the listener thread."""
        if not self.recording:
            return

        # Only record left clicks
        if button != pynput_mouse.Button.left:
            return

        left, top, w, h = self._window_rect

        if pressed:
            # Mouse down — check if inside game window
            if not (left <= x < left + w and top <= y < top + h):
                self._pending_down = None
                return

            self._pending_down = {
                'abs_x': x,
                'abs_y': y,
                'down_time': time.perf_counter(),
            }
        else:
            # Mouse up — pair with pending down
            if self._pending_down is None:
                return

            up_time = time.perf_counter()
            hold_duration = up_time - self._pending_down['down_time']

            # Delay since previous click finished
            if self._last_click_time is None:
                delay_before = 0.0
            else:
                delay_before = self._pending_down['down_time'] - self._last_click_time

            # Convert start position to relative coordinates
            rel_x = (self._pending_down['abs_x'] - left) / w
            rel_y = (self._pending_down['abs_y'] - top) / h

            # Convert end position (where mouse was released)
            rel_end_x = (x - left) / w
            rel_end_y = (y - top) / h

            click_data = {
                'rel_x': round(rel_x, 6),
                'rel_y': round(rel_y, 6),
                'delay_before': round(max(0.0, delay_before), 4),
                'hold_duration': round(hold_duration, 4),
            }

            # Only include end position if the mouse actually moved (drag)
            drag_dist = ((rel_end_x - rel_x) ** 2 + (rel_end_y - rel_y) ** 2) ** 0.5
            if drag_dist > 0.01:  # More than 1% of window = a drag
                click_data['rel_end_x'] = round(rel_end_x, 6)
                click_data['rel_end_y'] = round(rel_end_y, 6)

            self.clicks.append(click_data)

            self._last_click_time = up_time
            self._pending_down = None

            idx = len(self.clicks)
            if 'rel_end_x' in click_data:
                self.log(
                    f"  Drag #{idx}: "
                    f"({click_data['rel_x']:.3f}, {click_data['rel_y']:.3f}) → "
                    f"({click_data['rel_end_x']:.3f}, {click_data['rel_end_y']:.3f}) "
                    f"delay={click_data['delay_before']:.3f}s "
                    f"hold={click_data['hold_duration']*1000:.0f}ms"
                )
            else:
                self.log(
                    f"  Click #{idx}: "
                    f"({click_data['rel_x']:.3f}, {click_data['rel_y']:.3f}) "
                    f"delay={click_data['delay_before']:.3f}s "
                    f"hold={click_data['hold_duration']*1000:.0f}ms"
                )

    def save(self, name):
        """Save recorded clicks to a JSON macro file."""
        os.makedirs(MACROS_DIR, exist_ok=True)

        macro_data = {
            'name': name,
            'created': datetime.now().isoformat(),
            'window_size': [self._window_rect[2], self._window_rect[3]],
            'clicks': self.clicks,
        }

        filepath = os.path.join(MACROS_DIR, f'{name}.json')
        with open(filepath, 'w') as f:
            json.dump(macro_data, f, indent=2)

        return filepath

    # --- Static utility methods for managing saved macros ---

    @staticmethod
    def list_macros():
        """Return sorted list of saved macro names."""
        if not os.path.isdir(MACROS_DIR):
            return []
        names = []
        for fname in sorted(os.listdir(MACROS_DIR)):
            if fname.endswith('.json'):
                names.append(fname[:-5])
        return names

    @staticmethod
    def load_macro(name):
        """Load a macro from disk. Returns the dict or None on error."""
        filepath = os.path.join(MACROS_DIR, f'{name}.json')
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def delete_macro(name):
        """Delete a saved macro file."""
        filepath = os.path.join(MACROS_DIR, f'{name}.json')
        if os.path.isfile(filepath):
            os.remove(filepath)


class MacroPlayer:
    """
    Replays a recorded macro with natural timing variance.

    - Inter-click delays get standard proportional jitter (~5% for long delays)
    - Click hold durations get very tight variance (sigma ~3ms) per user request
    """

    def __init__(self, window_capture, log_func=None):
        self.window_capture = window_capture
        self.log = log_func or print
        self.playing = False
        self._stop_event = threading.Event()

    def play(self, macro_data, loop=False):
        """
        Play a macro. Intended to be called from a daemon thread.

        Args:
            macro_data: Dict loaded from a macro JSON file.
            loop: If True, repeat until stop() is called.
        """
        self._stop_event.clear()
        self.playing = True

        try:
            if loop:
                cycle = 0
                while not self._stop_event.is_set():
                    cycle += 1
                    self.log(f"  Loop cycle #{cycle}")
                    self._play_once(macro_data)
            else:
                self._play_once(macro_data)
        finally:
            self.playing = False

    def stop(self):
        """Signal playback to stop. Returns immediately; playback ends soon."""
        self._stop_event.set()

    def _play_once(self, macro_data):
        """Execute one full pass of the macro."""
        # Refresh window position at start of each pass
        window_rect = self.window_capture.get_window()
        if not window_rect:
            self.log("  Could not find game window for playback")
            self._stop_event.set()
            return

        left, top, w, h = window_rect
        clicks = macro_data.get('clicks', [])

        for i, click in enumerate(clicks):
            if self._stop_event.is_set():
                return

            # Wait the inter-click delay with natural jitter
            delay = click['delay_before']
            if delay > 0:
                jittered = self._jittered_delay(delay)
                if self._stop_event.wait(timeout=jittered):
                    return  # Stop was signaled

            if self._stop_event.is_set():
                return

            # Convert relative coords to absolute screen position
            abs_x = left + int(click['rel_x'] * w)
            abs_y = top + int(click['rel_y'] * h)

            is_drag = 'rel_end_x' in click and 'rel_end_y' in click

            if is_drag:
                abs_end_x = left + int(click['rel_end_x'] * w)
                abs_end_y = top + int(click['rel_end_y'] * h)
                hold = self._varied_hold(click['hold_duration'])

                # Move to start, press, drag to end, release
                pyautogui.moveTo(abs_x, abs_y)
                pyautogui.mouseDown(button='left')
                pyautogui.moveTo(abs_end_x, abs_end_y, duration=hold)
                pyautogui.mouseUp(button='left')

                self.log(
                    f"  Drag #{i+1}/{len(clicks)}: "
                    f"({abs_x}, {abs_y}) → ({abs_end_x}, {abs_end_y}) "
                    f"delay={delay:.3f}s "
                    f"hold={hold*1000:.0f}ms"
                )
            else:
                # Simple click with varied hold
                pyautogui.moveTo(abs_x, abs_y)
                hold = self._varied_hold(click['hold_duration'])
                pyautogui.mouseDown(button='left')
                time.sleep(hold)
                pyautogui.mouseUp(button='left')

                self.log(
                    f"  Click #{i+1}/{len(clicks)}: "
                    f"({abs_x}, {abs_y}) "
                    f"delay={delay:.3f}s "
                    f"hold={hold*1000:.0f}ms"
                )

    def _jittered_delay(self, target_delay):
        """
        Add proportional jitter to a delay, matching natural_delay behavior.

        Same jitter algorithm as NaturalClick.natural_delay but returns the
        value without sleeping (we use Event.wait for interruptible sleep).
        """
        if target_delay <= 0:
            return 0.0

        if target_delay < 0.3:
            jitter = random.gauss(0, 0.008)
        elif target_delay < 1.0:
            jitter = random.gauss(0, 0.025)
        else:
            jitter = random.gauss(0, target_delay * 0.025)

        actual = target_delay + jitter
        return max(target_delay * 0.5, actual)

    def _varied_hold(self, base_hold):
        """
        Add very minimal variance to the recorded hold duration.

        Sigma of 3ms with hard clamp of +/-15ms. A 100ms recorded hold
        replays as roughly 85-115ms — nearly imperceptible difference.
        """
        variance = random.gauss(0, 0.003)
        result = base_hold + variance
        result = max(0.040, result)  # Never below 40ms
        result = max(base_hold - 0.015, min(base_hold + 0.015, result))
        return round(result, 4)
