"""
Constants used throughout the anime-bot application.

This module centralizes all magic numbers and configuration constants
to improve maintainability and make the code more self-documenting.
"""

# UI Constants
MAX_SEARCH_RESULTS: int = 8
MAX_EPISODE_BUTTONS: int = 20
MAX_TITLE_LENGTH: int = 30
TITLE_TRUNCATE_LENGTH: int = 27
EPISODES_PER_ROW: int = 5
MAX_MESSAGE_LENGTH: int = 4000
TRUNCATED_MESSAGE_LENGTH: int = 3800
MAX_EPISODE_LIST_LENGTH: int = 3000
TRUNCATED_EPISODE_LIST_LENGTH: int = 2900

# Download/Upload Constants
DEFAULT_QUALITY: str = "360"
DEFAULT_AUDIO: str = "jpn"
DEFAULT_NUM_THREADS: int = 50
PROGRESS_UPDATE_INTERVAL: int = 5  # seconds

# Database Constants
DEFAULT_QUERY_LIMIT: int = 50
EXTENDED_QUERY_LIMIT: int = 200
MAX_QUERY_LIMIT: int = 1000

# Fuzzy Search Scoring
EXACT_MATCH_SCORE: int = 1000
POSITION_PENALTY: int = 2
CHAR_MATCH_SCORE: int = 10
