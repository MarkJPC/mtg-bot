"""Utility modules for MTG Commander Tracker Bot."""

# ANSI color codes for console output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

def log(source: str, message: str, color: str = Colors.WHITE):
    """Print colored log with source tag."""
    print(f"{color}[{source}]{Colors.RESET} {message}")

from utils.helpers import (
    parse_mentions,
    format_placement,
    format_win_rate,
    create_error_embed,
    create_success_embed,
    truncate_string,
)

__all__ = [
    "Colors",
    "log",
    "parse_mentions",
    "format_placement",
    "format_win_rate",
    "create_error_embed",
    "create_success_embed",
    "truncate_string",
]
