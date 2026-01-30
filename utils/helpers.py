"""Helper utilities for MTG Commander Tracker Bot."""

import re
import discord
from typing import Optional

from config import EMBED_COLOR


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


def parse_mentions(text: str) -> list[str]:
    """
    Extract Discord user IDs from mention strings.

    Supports formats:
    - <@123456789> (standard mention)
    - <@!123456789> (nickname mention)
    """
    log("HELPERS", f"parse_mentions called with: '{text}'", Colors.YELLOW)
    pattern = r"<@!?(\d+)>"
    result = re.findall(pattern, text)
    log("HELPERS", f"  regex pattern: {pattern}", Colors.YELLOW)
    log("HELPERS", f"  result: {result}", Colors.YELLOW)
    return result


def parse_player_names(text: str) -> list[str]:
    """
    Parse player names/mentions from text input.

    Supports:
    - Plain usernames separated by spaces, commas, or newlines
    - @username format (strips the @)
    - <@123456789> Discord mention format
    """
    log("HELPERS", f"parse_player_names called with: '{text}'", Colors.YELLOW)

    # First try to extract Discord mention IDs
    mention_pattern = r"<@!?(\d+)>"
    mention_ids = re.findall(mention_pattern, text)
    if mention_ids:
        log("HELPERS", f"  Found mention IDs: {mention_ids}", Colors.YELLOW)
        return [("id", mid) for mid in mention_ids]

    # Otherwise, parse as plain text usernames
    # Split by commas, spaces, or newlines
    # Remove @ prefix if present
    text = text.replace(",", " ").replace("\n", " ")
    names = []
    for part in text.split():
        part = part.strip()
        if part:
            # Remove @ prefix if present
            if part.startswith("@"):
                part = part[1:]
            names.append(("name", part))

    log("HELPERS", f"  Parsed names: {names}", Colors.YELLOW)
    return names


def format_placement(placement: int, game_type: str = "multiplayer") -> str:
    """Format placement number as ordinal with emoji."""
    if placement == 1:
        return "1st"
    elif placement == 2:
        return "2nd"
    elif placement == 3:
        return "3rd"
    elif placement == 4:
        return "4th"
    return f"{placement}th"


def format_win_rate(win_rate: float) -> str:
    """Format win rate as percentage string."""
    return f"{win_rate:.1f}%"


def format_duration(minutes: Optional[int]) -> str:
    """Format duration in minutes to human-readable string."""
    if minutes is None:
        return "N/A"
    if minutes < 60:
        return f"{minutes}min"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}min"


def create_error_embed(title: str, description: str) -> discord.Embed:
    """Create a standardized error embed."""
    return discord.Embed(
        title=f"Error: {title}",
        description=description,
        color=discord.Color.red()
    )


def create_success_embed(title: str, description: str) -> discord.Embed:
    """Create a standardized success embed."""
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green()
    )


def create_info_embed(title: str, description: str = "") -> discord.Embed:
    """Create a standardized info embed with MTG theming."""
    return discord.Embed(
        title=title,
        description=description,
        color=EMBED_COLOR
    )


def truncate_string(text: str, max_length: int = 100) -> str:
    """Truncate string with ellipsis if too long."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_leaderboard_row(
    rank: int,
    username: str,
    wins: int,
    games: int,
    points: int,
    win_rate: float
) -> str:
    """Format a single leaderboard row."""
    # Pad values for alignment
    rank_str = f"{rank}."
    win_rate_str = format_win_rate(win_rate)
    record = f"{wins}W/{games}G"

    return f"`{rank_str:3}` **{username}** - {points} pts ({record}, {win_rate_str})"


def format_game_summary(game_data: dict) -> str:
    """Format a game summary for display."""
    players_str = ""
    for p in game_data["players"]:
        place = format_placement(p["placement"])
        players_str += f"\n  {place}: **{p['username']}** ({p['commander']})"

    duration_str = format_duration(game_data.get("duration_minutes"))

    return (
        f"**Game #{game_data['id']}** ({game_data['game_type']})\n"
        f"Win Condition: {game_data['win_condition']} | Duration: {duration_str}"
        f"{players_str}"
    )


def get_medal_emoji(placement: int) -> str:
    """Get medal emoji for placement."""
    medals = {1: "", 2: "", 3: ""}
    return medals.get(placement, "")


def format_stereotype_narrative(stereotypes: list[tuple[str, str]]) -> str:
    """Format stereotypes as a silly narrative.

    Input: [(player_name, stereotype_name), ...]
    Output: 'Player1 "stereotype1" while Player2 "stereotype2"...'
    """
    if not stereotypes:
        return ""

    # Group by player
    player_stereotypes: dict[str, list[str]] = {}
    for player_name, stereotype_name in stereotypes:
        if player_name not in player_stereotypes:
            player_stereotypes[player_name] = []
        player_stereotypes[player_name].append(stereotype_name)

    # Build narrative parts
    parts = []
    for player_name, stereotype_list in player_stereotypes.items():
        quoted = [f'"{s}"' for s in stereotype_list]
        parts.append(f"{player_name} {', '.join(quoted)}")

    return " while ".join(parts) + "..."


def format_head_to_head(stats) -> str:
    """Format head-to-head stats for display."""
    total = stats.player1_wins + stats.player2_wins
    p1_pct = (stats.player1_wins / total * 100) if total > 0 else 0
    p2_pct = (stats.player2_wins / total * 100) if total > 0 else 0

    lines = [
        f"**{stats.player1_name}** vs **{stats.player2_name}**",
        "",
        f"Games Together: {stats.games_together}",
        "",
        f"**Overall Record:**",
        f"  {stats.player1_name}: {stats.player1_wins} wins ({p1_pct:.1f}%)",
        f"  {stats.player2_name}: {stats.player2_wins} wins ({p2_pct:.1f}%)",
    ]

    if stats.one_v_one_record[0] > 0 or stats.one_v_one_record[1] > 0:
        lines.extend([
            "",
            f"**1v1 Record:**",
            f"  {stats.player1_name}: {stats.one_v_one_record[0]} wins",
            f"  {stats.player2_name}: {stats.one_v_one_record[1]} wins",
        ])

    return "\n".join(lines)
