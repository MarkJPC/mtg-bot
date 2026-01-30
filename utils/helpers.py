"""Helper utilities for MTG Commander Tracker Bot."""

import re
import discord
from typing import Optional

from config import EMBED_COLOR


def parse_mentions(text: str) -> list[str]:
    """
    Extract Discord user IDs from mention strings.

    Supports formats:
    - <@123456789> (standard mention)
    - <@!123456789> (nickname mention)
    """
    pattern = r"<@!?(\d+)>"
    return re.findall(pattern, text)


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
