import os

# Window/game title
GAME_WINDOW_TITLE = 'Raid: Shadow Legends'

# Template directory (relative to this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(SCRIPT_DIR, 'templates')

# Template names
TEMPLATE_BATTLE = os.path.join(TEMPLATES_DIR, 'Battle.png')
TEMPLATE_ARENA = os.path.join(TEMPLATES_DIR, 'Arena.png')
TEMPLATE_CLASSIC_ARENA = os.path.join(TEMPLATES_DIR, 'Classic Arena.png')
TEMPLATE_ARENA_BATTLE_BUTTON = os.path.join(TEMPLATES_DIR, 'ArenaBattleButton.png')
TEMPLATE_START_FIGHT = os.path.join(TEMPLATES_DIR, 'Start Fight.png')
TEMPLATE_BATTLE_COMPLETE = os.path.join(TEMPLATES_DIR, 'Battle Complete.png')
TEMPLATE_RETURN_ARENA = os.path.join(TEMPLATES_DIR, 'Return Arena.png')
TEMPLATE_FREE_REFRESH = os.path.join(TEMPLATES_DIR, 'Free Refresh.png')
TEMPLATE_PAY_REFRESH = os.path.join(TEMPLATES_DIR, 'Pay Refresh.png')
TEMPLATE_EMPTY_ATOKENS = os.path.join(TEMPLATES_DIR, 'Empty Atokens.png')
TEMPLATE_FREE_ATOKENS = os.path.join(TEMPLATES_DIR, 'Free Atokens.png')
TEMPLATE_BACK = os.path.join(TEMPLATES_DIR, 'Back.png')

# Other constants
MIN_SELECTION_SIZE = 10
CLICK_DELAY = 2.0  # seconds between clicks

# =============================================================================
# Classic Arena Settings
# =============================================================================

# Timing
ARENA_SCAN_DELAY = 0.5          # Delay between scanning operations
ARENA_SCROLL_DELAY = 1.0        # Delay after scrolling (allow screen to settle)
ARENA_BATTLE_DELAY = 3.0        # Delay after clicking battle (for battle to load)
ARENA_POST_BATTLE_DELAY = 2.0   # Delay after battle completes

# Scrolling (uses ARENA_LIST_REGION percentages for scroll distance)
ARENA_SCROLL_DURATION = 0.5     # Duration of scroll drag animation
ARENA_MAX_SCROLL_ATTEMPTS = 6   # Max scroll attempts to find all opponents

# OCR Region (percentages of window dimensions)
# These define where to look for Team Power text
# FULL region used for initial scan - covers all 4 visible opponents
ARENA_OCR_REGION = {
    'x_start': 0.65,    # Start X - where "Team Power:" text appears
    'y_start': 0.24,    # Start Y - slightly above first opponent to catch all text
    'width': 0.25,      # Width - just the Team Power text area
    'height': 0.74,     # Height - extend fully to bottom (ends at 98%)
}

# BOTTOM BAND - used after scrolling to only capture newly revealed opponents
# Only scans the bottom opponent slot - bottom edge aligns with FULL region
ARENA_OCR_BOTTOM_BAND = {
    'x_start': 0.65,    # Same X as main region
    'y_start': 0.82,    # Start at 4th opponent position
    'width': 0.25,      # Same width
    'height': 0.16,     # Extend to bottom (~98%, same as FULL)
}

# Battle button region (approximate X position as % of window width)
ARENA_BATTLE_BUTTON_X = 0.90

# Opponent list region (for scrolling)
ARENA_LIST_REGION = {
    'x_center': 0.50,   # Center X for scroll drag
    'y_start': 0.50,    # Top of list area (scroll destination)
    'y_end': 0.68,      # Bottom of list area (scroll start) - 16% = ~1.6 opponent heights
}

# Maximum battles per session (matches "Battles: X/20" limit)
ARENA_MAX_BATTLES = 20

# Team power threshold - skip opponents above this power (0 = no limit)
ARENA_MAX_OPPONENT_POWER = 0

# Sort order for attacking (True = weakest first)
ARENA_ATTACK_WEAKEST_FIRST = True
