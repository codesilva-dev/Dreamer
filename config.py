import os

# Window/game title
GAME_WINDOW_TITLE = 'Raid: Shadow Legends'

# Template directory (relative to this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(SCRIPT_DIR, 'templates')
MACROS_DIR = os.path.join(SCRIPT_DIR, 'macros')

# Template names
TEMPLATE_BATTLE = os.path.join(TEMPLATES_DIR, 'Battle.png')
TEMPLATE_ARENA = os.path.join(TEMPLATES_DIR, 'Arena.png')
TEMPLATE_CLASSIC_ARENA = os.path.join(TEMPLATES_DIR, 'Classic Arena.png')
TEMPLATE_ARENA_BATTLE_BUTTON = os.path.join(TEMPLATES_DIR, 'ArenaBattleButton.png')
TEMPLATE_START_FIGHT = os.path.join(TEMPLATES_DIR, 'Start Fight.png')
TEMPLATE_BATTLE_COMPLETE = os.path.join(TEMPLATES_DIR, 'Battle Complete.png')
TEMPLATE_CONTINUE = os.path.join(TEMPLATES_DIR, 'continue.png')
TEMPLATE_CB_VIC_SCREEN = os.path.join(TEMPLATES_DIR, 'CBVicScreen.png')
TEMPLATE_RETURN_ARENA = os.path.join(TEMPLATES_DIR, 'Return Arena.png')
TEMPLATE_FREE_REFRESH = os.path.join(TEMPLATES_DIR, 'Free Refresh.png')
TEMPLATE_PAY_REFRESH = os.path.join(TEMPLATES_DIR, 'Pay Refresh.png')
TEMPLATE_EMPTY_ATOKENS = os.path.join(TEMPLATES_DIR, 'Empty Atokens.png')
TEMPLATE_FREE_ATOKENS = os.path.join(TEMPLATES_DIR, 'Free Atokens.png')
TEMPLATE_BACK = os.path.join(TEMPLATES_DIR, 'Back.png')

# Shop templates
TEMPLATE_FREE_SHOP_BUTTON = os.path.join(TEMPLATES_DIR, 'FreeShopButton.png')
TEMPLATE_CLAIM_GIFT = os.path.join(TEMPLATES_DIR, 'ClaimGift.png')
TEMPLATE_CLAIM_PACK = os.path.join(TEMPLATES_DIR, 'ClaimPack.png')
TEMPLATE_LIMITED_OFFERS = os.path.join(TEMPLATES_DIR, 'LimitedOffers.png')
TEMPLATE_SMALL_PACK = os.path.join(TEMPLATES_DIR, 'SmallPack.png')
TEMPLATE_SMALL_PACK_2 = os.path.join(TEMPLATES_DIR, 'smallpack2.png')
TEMPLATE_FREE_ICON = os.path.join(TEMPLATES_DIR, 'Free Icon.png')
TEMPLATE_REG_PACK = os.path.join(TEMPLATES_DIR, 'regPack.png')
TEMPLATE_JUNK_OFFER = os.path.join(TEMPLATES_DIR, 'junkoffer.png')
TEMPLATE_CLOSE_OFFER = os.path.join(TEMPLATES_DIR, 'closeoffer.png')

# Guardian templates
TEMPLATE_GUARDIAN_RING = os.path.join(TEMPLATES_DIR, 'guardianRing.png')
TEMPLATE_UPGRADE_LVL = os.path.join(TEMPLATES_DIR, 'UpgradeLvl.png')

# Gem templates
TEMPLATE_COLLECT_GEM = os.path.join(TEMPLATES_DIR, 'collectGem.png')
TEMPLATE_GEM_CLAIM = os.path.join(TEMPLATES_DIR, 'gemClaim.png')

# Clan Boss templates
TEMPLATE_CB_STAGES = os.path.join(TEMPLATES_DIR, 'CBStages.png')
TEMPLATE_CB1 = os.path.join(TEMPLATES_DIR, 'CB1.png')
TEMPLATE_CB_RED_SWORD = os.path.join(TEMPLATES_DIR, 'CBRedSword.png')

# CB difficulty templates (user provides PNGs)
TEMPLATE_CB_EASY = os.path.join(TEMPLATES_DIR, 'CBEasy.png')
TEMPLATE_CB_NORMAL = os.path.join(TEMPLATES_DIR, 'CBNormal.png')
TEMPLATE_CB_HARD = os.path.join(TEMPLATES_DIR, 'CBHard.png')
TEMPLATE_CB_BRUTAL = os.path.join(TEMPLATES_DIR, 'CBBrutal.png')
TEMPLATE_CB_NIGHTMARE = os.path.join(TEMPLATES_DIR, 'CBNightmare.png')
TEMPLATE_CB_ULTRA_NIGHTMARE = os.path.join(TEMPLATES_DIR, 'CBUltraNightmare.png')

# Menu templates
TEMPLATE_CHECK_MENU = os.path.join(TEMPLATES_DIR, 'checkMenu.png')
TEMPLATE_DAILY_LOGIN = os.path.join(TEMPLATES_DIR, 'dailyLogin.png')
TEMPLATE_COLLECT = os.path.join(TEMPLATES_DIR, 'collect.png')
TEMPLATE_PPP = os.path.join(TEMPLATES_DIR, 'PPP.png')
TEMPLATE_PPP_RED_DOT = os.path.join(TEMPLATES_DIR, 'pppRedDot.png')
TEMPLATE_FREE_DRAW = os.path.join(TEMPLATES_DIR, 'FreeDraw.png')

# Playtime rewards templates
TEMPLATE_ACCRUED_REWARDS = os.path.join(TEMPLATES_DIR, 'AccruedRewards.png')
TEMPLATE_PLAYTIME_REWARD = os.path.join(TEMPLATES_DIR, 'playtimeReward.png')
TEMPLATE_CLAIM_ALL_REWARDS = os.path.join(TEMPLATES_DIR, 'claimAllRewards.png')
TEMPLATE_PT1 = os.path.join(TEMPLATES_DIR, 'PT1.png')
TEMPLATE_PT2 = os.path.join(TEMPLATES_DIR, 'PT2.png')
TEMPLATE_PT3 = os.path.join(TEMPLATES_DIR, 'PT3.png')
TEMPLATE_PT4 = os.path.join(TEMPLATES_DIR, 'PT4.png')
TEMPLATE_PT5 = os.path.join(TEMPLATES_DIR, 'PT5.png')
TEMPLATE_PT6 = os.path.join(TEMPLATES_DIR, 'PT6.png')
TEMPLATE_PT7 = os.path.join(TEMPLATES_DIR, 'PT7.png')
TEMPLATE_PT8 = os.path.join(TEMPLATES_DIR, 'PT8.png')
TEMPLATE_PT9 = os.path.join(TEMPLATES_DIR, 'PT9.png')

# Market templates
TEMPLATE_FRESH_MARKET = os.path.join(TEMPLATES_DIR, 'freshMarket.png')
TEMPLATE_BUY_SHARD = os.path.join(TEMPLATES_DIR, 'BuyShard.png')
TEMPLATE_GET_SHARD = os.path.join(TEMPLATES_DIR, 'getShard.png')

# Quest templates
TEMPLATE_QUEST_ICON = os.path.join(TEMPLATES_DIR, 'questIcon.png')
TEMPLATE_CLAIM_QUESTS = os.path.join(TEMPLATES_DIR, 'claimQuests.png')
TEMPLATE_SUM3_CHAMPS = os.path.join(TEMPLATES_DIR, 'sum3Champs.png')
TEMPLATE_DAILY_TAB = os.path.join(TEMPLATES_DIR, 'dailyTab.png')

# Dungeon templates
TEMPLATE_DUNGEONS = os.path.join(TEMPLATES_DIR, 'Dungeons.png')

# Dungeon stage battle button (text-only crop, reusable across all bosses)
TEMPLATE_PVE_BATTLE = os.path.join(TEMPLATES_DIR, 'PVEBattle.png')
TEMPLATE_START = os.path.join(TEMPLATES_DIR, 'start.png')
TEMPLATE_CB_QB_TRUE = os.path.join(TEMPLATES_DIR, 'CB_QB_True.png')
TEMPLATE_CB_NO_KEY = os.path.join(TEMPLATES_DIR, 'CBNoKey.png')

# Iron Twins templates
TEMPLATE_IRON_TWINS = os.path.join(TEMPLATES_DIR, 'ironTwins.png')
TEMPLATE_IT_ICON = os.path.join(TEMPLATES_DIR, 'ITIcon.png')
TEMPLATE_EMPTY_IT_KEYS = os.path.join(TEMPLATES_DIR, 'emptyITKeys.png')
TEMPLATE_IT_NO_KEY = os.path.join(TEMPLATES_DIR, 'ITNoKey.png')
TEMPLATE_IT_NO_KEY_STAGES = os.path.join(TEMPLATES_DIR, 'ITNoKeyStages.png')
TEMPLATE_IT_REPLAY = os.path.join(TEMPLATES_DIR, 'ITReplay.png')
TEMPLATE_BASTION = os.path.join(TEMPLATES_DIR, 'bastion.png')
TEMPLATE_SUP_RAID_OFF = os.path.join(TEMPLATES_DIR, 'SupRaidOff.png')

# Summon templates
TEMPLATE_SUMMON_PORTAL = os.path.join(TEMPLATES_DIR, 'summonPortal.png')
TEMPLATE_MYSTERY_SHARD = os.path.join(TEMPLATES_DIR, 'mysteryShard.png')
TEMPLATE_SUM_BTN = os.path.join(TEMPLATES_DIR, 'sumBtn.png')
TEMPLATE_SUM_BTN_V2 = os.path.join(TEMPLATES_DIR, 'sumBtnV2.png')

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
ARENA_SCROLL_DURATION = 0.6     # Duration of scroll drag animation
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
    'y_start': 0.49,    # Top of list area (scroll destination)
    'y_end': 0.69,      # Bottom of list area (scroll start) - 20% = ~2 opponent heights
}

# Maximum battles per session (matches "Battles: X/20" limit)
ARENA_MAX_BATTLES = 20

# Team power threshold - skip opponents above this power (0 = no limit)
ARENA_MAX_OPPONENT_POWER = 0

# Player level threshold - skip opponents above this level (0 = no limit)
ARENA_MAX_OPPONENT_LEVEL = 0

# OR power threshold - always fight opponents at or below this power,
# regardless of level. Catches easy wins from high-level players with
# weak teams. (0 = disabled)
ARENA_OR_POWER = 0

# Sort order for attacking (True = weakest first)
ARENA_ATTACK_WEAKEST_FIRST = True

# =============================================================================
# Fluid Scan Settings (V2 async scanning)
# =============================================================================

# V2 OCR region — taller than v1 to capture all 4 visible opponents
# Extends lower to catch the bottom-most "Team Power:" text
FLUID_OCR_REGION = {
    'x_start': 0.72,    # Start X - includes "Power:" colon for row detection
    'y_start': 0.24,    # Start Y - below header/nav UI
    'width': 0.14,      # Width - through number+K, stops before "Battle" (to ~86%)
    'height': 0.76,     # Height - ends at 100% to fully cover bottom opponent
}

# V2 level OCR region — player level number inside circular badge on portrait
# The player account level (e.g. 66, 72, 86) appears in a small colored circle
# at the bottom of each opponent's portrait, to the right of the sidebar nav.
FLUID_LEVEL_REGION = {
    'x_start': 0.1672,  # Start X - 3px further left to capture leading digit of "100"
    'y_start': 0.24,    # Start Y - same as power region (below header/nav)
    'width': 0.0202,    # Width - 5px wider to ensure full 3-digit numbers fit
    'height': 0.76,     # Height - same as power region
}

# Duration of the scroll drag for fluid scanning
FLUID_SCROLL_DRAG_DURATION = 0.6

# Broader scroll region for fluid scanning (covers more list area per scroll)
FLUID_SCROLL_REGION = {
    'x_center': 0.50,   # Center X for scroll drag
    'y_start': 0.35,    # Scroll destination (higher up = broader scroll)
    'y_end': 0.80,      # Scroll start (lower down = broader scroll)
}

# =============================================================================
# Iron Twins Settings
# =============================================================================

# Default stage to fight (1-15)
IRON_TWINS_STAGE = 15

# Timing
IRON_TWINS_SCAN_DELAY = 1.0       # Delay between OCR scans for stage number
IRON_TWINS_SCROLL_DELAY = 1.0     # Delay after scrolling
IRON_TWINS_BATTLE_TIMEOUT = 600   # Max seconds to wait for battle to complete (10 min)

# Scrolling region for dungeon stage list
IRON_TWINS_SCROLL_REGION = {
    'x_center': 0.50,   # Center X for scroll drag
    'y_start': 0.35,    # Scroll destination (higher up)
    'y_end': 0.75,      # Scroll start (lower down)
}

# Max scroll attempts to find the target stage
IRON_TWINS_MAX_SCROLL_ATTEMPTS = 10

# =============================================================================
# Clan Boss Settings
# =============================================================================

# Default difficulty to fight (starting difficulty)
CB_DIFFICULTY = 'ultranightmare'

# Player name to look for on leaderboard
CB_PLAYER_NAME = 'YourNameHere'  # Set this to your in-game name

# Valid difficulties (ordered hardest to easiest for cascading)
CB_DIFFICULTIES = ['ultranightmare', 'nightmare', 'brutal', 'hard', 'normal', 'easy']

# Max damage thresholds for top chest rewards (damage needed per difficulty)
CB_MAX_DAMAGE_THRESHOLDS = {
    'ultranightmare': 70_280_000,  # 70.28M
    'nightmare': 39_170_000,        # 39.17M
    'brutal': 21_700_000,           # 21.7M
    'hard': 11_650_000,             # 11.65M
    'normal': 3_640_000,            # 3.64M
    'easy': 1_150_000,              # 1.15M
}

# Scrolling region for difficulty list (right side of screen)
CB_SCROLL_REGION = {
    'x_center': 0.75,   # Right side of screen for difficulty list
    'y_start': 0.35,    # Scroll destination (higher up)
    'y_end': 0.75,      # Scroll start (lower down)
}

# Scrolling region for leaderboard (left side of screen)
CB_LEADERBOARD_SCROLL_REGION = {
    'x_center': 0.25,   # Left side of screen for leaderboard
    'y_start': 0.35,    # Scroll destination (higher up)
    'y_end': 0.75,      # Scroll start (lower down)
}

# Max scroll attempts
CB_MAX_SCROLL_ATTEMPTS = 6

# Timing
CB_SCROLL_DELAY = 1.0  # Delay after scrolling to let screen settle
CB_BATTLE_TIMEOUT = 600  # Max seconds to wait for battle (10 min)
