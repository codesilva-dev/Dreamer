from config import TEMPLATE_BATTLE, TEMPLATE_ARENA, TEMPLATE_CLASSIC_ARENA, CLICK_DELAY
from sequences.battle_sequence import ClassicArenaSequence
from text_recognition import TextRecognizer


class ArenasSequence:
    def __init__(self, window_capture, template_matcher, log_func):
        self.window_capture = window_capture
        self.template_matcher = template_matcher
        self.log = log_func
        
        # Initialize text recognizer for classic arena (debug=False for reduced logging)
        self.text_recognizer = TextRecognizer(window_capture, log_func, debug=False)
        
        # Initialize classic arena sub-sequence
        self.classic_arena = ClassicArenaSequence(
            window_capture, 
            template_matcher, 
            self.text_recognizer,
            log_func
        )

    def run(self):
        self.log('\n--- Starting Arenas Sequence ---')
        self.window_capture.get_window()
        
        # Navigation steps to reach Classic Arena
        steps = [
            ("Battle", TEMPLATE_BATTLE),
            ("Arena", TEMPLATE_ARENA),
            ("Classic Arena", TEMPLATE_CLASSIC_ARENA)
        ]
        
        for step_name, template_path in steps:
            self.log(f'Looking for "{step_name}"...')
            success, message = self.template_matcher.find_and_click(template_path, wait_after=CLICK_DELAY)
            if success:
                self.log(f'✓ Clicked "{step_name}" - {message}')
            else:
                self.log(f'✗ Failed to find "{step_name}" - {message}')
                self.log('--- Sequence Aborted ---\n')
                return False
        
        self.log('✓ Navigated to Classic Arena')
        
        # Now run the Classic Arena sequence
        self.log('\n--- Starting Classic Arena Battle Sequence ---')
        result = self.classic_arena.run()
        
        if result:
            self.log('--- Arena Sequence Complete ---\n')
        else:
            self.log('--- Arena Sequence Failed ---\n')
        
        return result
    
    def run_navigation_only(self):
        """Just navigate to Classic Arena without starting battles"""
        self.log('\n--- Navigating to Classic Arena ---')
        self.window_capture.get_window()
        
        steps = [
            ("Battle", TEMPLATE_BATTLE),
            ("Arena", TEMPLATE_ARENA),
            ("Classic Arena", TEMPLATE_CLASSIC_ARENA)
        ]
        
        for step_name, template_path in steps:
            self.log(f'Looking for "{step_name}"...')
            success, message = self.template_matcher.find_and_click(template_path, wait_after=CLICK_DELAY)
            if success:
                self.log(f'✓ Clicked "{step_name}" - {message}')
            else:
                self.log(f'✗ Failed to find "{step_name}" - {message}')
                return False
        
        self.log('✓ Navigation complete')
        return True
    
    def run_scan_only(self):
        """Navigate to Classic Arena and scan opponents without attacking"""
        if not self.run_navigation_only():
            return None
        
        self.log('\n--- Scanning Opponents ---')
        self.classic_arena.reset()
        self.classic_arena.run_scan_phase()
        self.classic_arena.run_sort_phase()
        
        return self.classic_arena.sorted_opponents
