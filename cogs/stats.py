"""Statistics cog for MTG Commander Tracker Bot."""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from config import EMBED_COLOR
from utils import Colors, log
from utils.helpers import (
    create_error_embed,
    create_info_embed,
    format_leaderboard_row,
    format_win_rate,
    format_game_summary,
    format_head_to_head,
    format_duration,
    format_placement,
    format_stereotype_narrative,
)


class Stats(commands.Cog):
    """Cog for viewing statistics."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="View the points leaderboard")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        """Display the leaderboard sorted by points."""
        log("STATS", f"leaderboard command invoked by {interaction.user}", Colors.CYAN)
        db = self.bot.db
        stats = await db.get_leaderboard()
        log("STATS", f"leaderboard got {len(stats)} players from DB", Colors.CYAN)

        if not stats:
            await interaction.response.send_message(
                embed=create_info_embed(
                    "Leaderboard",
                    "No games have been played yet!"
                )
            )
            return

        embed = create_info_embed("Commander Leaderboard")

        leaderboard_text = ""
        for i, player_stats in enumerate(stats[:15], 1):  # Top 15
            leaderboard_text += format_leaderboard_row(
                rank=i,
                username=player_stats.username,
                wins=player_stats.wins,
                games=player_stats.total_games,
                points=player_stats.points,
                win_rate=player_stats.win_rate
            ) + "\n"

        embed.description = leaderboard_text

        embed.set_footer(text="Points: 1st=3, 2nd=2, 3rd=1, 4th=0 (multiplayer) | Win=3, Loss=0 (1v1)")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stats", description="View a player's statistics")
    @app_commands.describe(player="The player to view stats for")
    async def stats(
        self,
        interaction: discord.Interaction,
        player: discord.Member
    ) -> None:
        """Display detailed stats for a specific player."""
        log("STATS", f"stats command invoked by {interaction.user}", Colors.CYAN)
        log("STATS", f"  player param: {player} (id={player.id}, type={type(player).__name__})", Colors.CYAN)
        db = self.bot.db
        player_stats = await db.get_player_stats(str(player.id))
        log("STATS", f"  player_stats from DB: {player_stats}", Colors.CYAN)

        if not player_stats:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Player Not Found",
                    f"{player.display_name} hasn't played any games yet!"
                ),
                ephemeral=True
            )
            return

        embed = create_info_embed(f"Stats for {player_stats.username}")

        # General stats
        embed.add_field(
            name="Overview",
            value=(
                f"**Total Games:** {player_stats.total_games}\n"
                f"**Wins:** {player_stats.wins}\n"
                f"**Win Rate:** {format_win_rate(player_stats.win_rate)}\n"
                f"**Total Points:** {player_stats.points}"
            ),
            inline=True
        )

        # Deck stats
        deck_info = ""
        if player_stats.favorite_deck:
            deck_info += f"**Favorite Deck:** {player_stats.favorite_deck}\n"
        if player_stats.best_deck:
            deck_info += f"**Best Deck:** {player_stats.best_deck} (min 3 games)\n"

        if deck_info:
            embed.add_field(name="Decks", value=deck_info, inline=True)

        # Streaks
        if player_stats.current_streak > 0:
            embed.add_field(
                name="Current Win Streak",
                value=f"{player_stats.current_streak} game(s)",
                inline=True
            )

        embed.set_thumbnail(url=player.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="headtohead", description="Compare two players")
    @app_commands.describe(
        player1="First player",
        player2="Second player"
    )
    async def head_to_head(
        self,
        interaction: discord.Interaction,
        player1: discord.Member,
        player2: discord.Member
    ) -> None:
        """Display head-to-head statistics between two players."""
        log("STATS", f"headtohead command invoked by {interaction.user}", Colors.GREEN)
        log("STATS", f"  player1 param: {player1} (id={player1.id}, type={type(player1).__name__})", Colors.GREEN)
        log("STATS", f"  player2 param: {player2} (id={player2.id}, type={type(player2).__name__})", Colors.GREEN)

        if player1.id == player2.id:
            log("STATS", f"  ERROR: player1 == player2", Colors.RED)
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Invalid Comparison",
                    "You can't compare a player to themselves!"
                ),
                ephemeral=True
            )
            return

        db = self.bot.db
        log("STATS", f"  Calling db.get_head_to_head({player1.id}, {player2.id})", Colors.GREEN)
        h2h_stats = await db.get_head_to_head(str(player1.id), str(player2.id))
        log("STATS", f"  h2h_stats result: {h2h_stats}", Colors.GREEN)

        if not h2h_stats:
            log("STATS", f"  ERROR: h2h_stats is None/empty", Colors.RED)
            await interaction.response.send_message(
                embed=create_error_embed(
                    "No Data",
                    "One or both players haven't played any games yet!"
                ),
                ephemeral=True
            )
            return

        if h2h_stats.games_together == 0:
            log("STATS", f"  No games together", Colors.YELLOW)
            await interaction.response.send_message(
                embed=create_info_embed(
                    "Head to Head",
                    f"**{player1.display_name}** and **{player2.display_name}** "
                    "haven't played in any games together yet!"
                )
            )
            return

        log("STATS", f"  SUCCESS: Sending h2h embed", Colors.GREEN)
        embed = create_info_embed("Head to Head")
        embed.description = format_head_to_head(h2h_stats)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="deckstats", description="View deck/commander statistics")
    @app_commands.describe(commander="Commander name to search for (optional)")
    async def deck_stats(
        self,
        interaction: discord.Interaction,
        commander: str = None
    ) -> None:
        """Display statistics for decks/commanders."""
        db = self.bot.db
        deck_stats = await db.get_deck_stats(commander)

        if not deck_stats:
            if commander:
                await interaction.response.send_message(
                    embed=create_info_embed(
                        "Deck Stats",
                        f"No decks found matching '{commander}'"
                    )
                )
            else:
                await interaction.response.send_message(
                    embed=create_info_embed(
                        "Deck Stats",
                        "No decks with at least 3 games played yet!"
                    )
                )
            return

        if commander:
            # Specific commander search
            embed = create_info_embed(f"Deck Stats: {commander}")

            for stats in deck_stats:
                embed.add_field(
                    name=stats.commander_name,
                    value=(
                        f"**Games:** {stats.total_games}\n"
                        f"**Wins:** {stats.wins}\n"
                        f"**Win Rate:** {format_win_rate(stats.win_rate)}\n"
                        f"**Played by:** {', '.join(stats.players)}"
                    ),
                    inline=True
                )
        else:
            # Top decks leaderboard
            embed = create_info_embed("Top Decks (min 3 games)")

            deck_text = ""
            for i, stats in enumerate(deck_stats, 1):
                deck_text += (
                    f"`{i}.` **{stats.commander_name}** - "
                    f"{format_win_rate(stats.win_rate)} "
                    f"({stats.wins}W/{stats.total_games}G)\n"
                )

            embed.description = deck_text if deck_text else "No decks qualify yet."

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="recentgames", description="View recent games")
    @app_commands.describe(count="Number of games to show (default 5, max 10)")
    async def recent_games(
        self,
        interaction: discord.Interaction,
        count: int = 5
    ) -> None:
        """Display recent games."""
        count = max(1, min(count, 10))  # Clamp between 1 and 10

        db = self.bot.db
        games = await db.get_recent_games(count)

        if not games:
            await interaction.response.send_message(
                embed=create_info_embed(
                    "Recent Games",
                    "No games have been played yet!"
                )
            )
            return

        embed = create_info_embed(f"Last {len(games)} Game(s)")

        for game in games:
            # Format date
            played_at = game["played_at"]
            if isinstance(played_at, str):
                played_at = datetime.fromisoformat(played_at)
            date_str = played_at.strftime("%m/%d/%Y") if isinstance(played_at, datetime) else str(played_at)[:10]

            # Format players
            players_str = ""
            for p in game["players"]:
                place_str = format_placement(p["placement"])
                players_str += f"{place_str}: **{p['username']}** ({p['commander']})\n"

            duration_str = format_duration(game.get("duration_minutes"))

            # Get stereotypes for this game
            stereotypes = await db.get_game_stereotypes(game["id"])
            stereotype_str = ""
            if stereotypes:
                narrative = format_stereotype_narrative(stereotypes)
                stereotype_str = f"{narrative}\n"

            embed.add_field(
                name=f"Game #{game['id']} - {date_str}",
                value=(
                    f"**Type:** {game['game_type']} | "
                    f"**Win Con:** {game['win_condition']} | "
                    f"**Duration:** {duration_str}\n"
                    f"{players_str}"
                    f"{stereotype_str}"
                ),
                inline=False
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Set up the stats cog."""
    await bot.add_cog(Stats(bot))
