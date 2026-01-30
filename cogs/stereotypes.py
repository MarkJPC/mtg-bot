"""Stereotypes cog for MTG Commander Tracker Bot."""

import discord
from discord import app_commands
from discord.ext import commands

from config import EMBED_COLOR
from utils.helpers import create_error_embed, create_info_embed, create_success_embed


class Stereotypes(commands.Cog):
    """Cog for stereotype management and viewing."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stereotypes", description="View the Hall of Shame")
    async def stereotypes(self, interaction: discord.Interaction) -> None:
        """Display the stereotype leaderboard (Hall of Shame)."""
        db = self.bot.db
        leaderboard = await db.get_stereotype_leaderboard()

        if not leaderboard:
            await interaction.response.send_message(
                embed=create_info_embed(
                    "Hall of Shame",
                    "No stereotypes have been assigned yet!"
                )
            )
            return

        embed = create_info_embed("Hall of Shame")

        # Group by player
        player_stereotypes = {}
        for username, stereotype, count in leaderboard:
            if username not in player_stereotypes:
                player_stereotypes[username] = []
            player_stereotypes[username].append((stereotype, count))

        # Build display
        shame_text = ""
        for username, stereotypes in player_stereotypes.items():
            total = sum(count for _, count in stereotypes)
            shame_text += f"\n**{username}** ({total} total):\n"
            for stereotype, count in stereotypes[:5]:  # Top 5 per player
                shame_text += f"  - {stereotype}: {count}x\n"

        embed.description = shame_text if shame_text else "No shame to report... yet."

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="mystereotypes", description="View a player's stereotype history")
    @app_commands.describe(player="The player to view stereotypes for")
    async def my_stereotypes(
        self,
        interaction: discord.Interaction,
        player: discord.Member
    ) -> None:
        """Display a player's stereotype history."""
        db = self.bot.db
        stereotypes = await db.get_player_stereotypes(str(player.id))

        if not stereotypes:
            await interaction.response.send_message(
                embed=create_info_embed(
                    f"Stereotypes for {player.display_name}",
                    "This player has no stereotypes assigned... are they even playing?"
                )
            )
            return

        embed = create_info_embed(f"Stereotypes for {player.display_name}")
        embed.set_thumbnail(url=player.display_avatar.url)

        # Calculate total
        total = sum(count for _, count in stereotypes)
        embed.description = f"**Total:** {total} stereotype(s) earned\n\n"

        for stereotype, count in stereotypes:
            bar_length = min(count, 10)  # Cap visual bar at 10
            bar = "" * bar_length
            embed.description += f"{stereotype}: {bar} ({count})\n"

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="addstereotype", description="Add a new stereotype to the list")
    @app_commands.describe(name="The name of the new stereotype")
    async def add_stereotype(
        self,
        interaction: discord.Interaction,
        name: str
    ) -> None:
        """Add a new stereotype."""
        if len(name) > 100:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Name Too Long",
                    "Stereotype name must be 100 characters or less."
                ),
                ephemeral=True
            )
            return

        if len(name) < 3:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Name Too Short",
                    "Stereotype name must be at least 3 characters."
                ),
                ephemeral=True
            )
            return

        db = self.bot.db
        stereotype = await db.add_stereotype(name)

        if stereotype:
            await interaction.response.send_message(
                embed=create_success_embed(
                    "Stereotype Added",
                    f"**{name}** has been added to the stereotype list!"
                )
            )
        else:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Already Exists",
                    f"**{name}** is already a stereotype!"
                ),
                ephemeral=True
            )

    @app_commands.command(name="liststereotypes", description="List all available stereotypes")
    async def list_stereotypes(self, interaction: discord.Interaction) -> None:
        """List all available stereotypes."""
        db = self.bot.db
        stereotypes = await db.get_all_stereotypes()

        if not stereotypes:
            await interaction.response.send_message(
                embed=create_info_embed(
                    "Available Stereotypes",
                    "No stereotypes have been created yet!"
                )
            )
            return

        embed = create_info_embed("Available Stereotypes")

        stereotype_list = "\n".join(f"- {s.name}" for s in stereotypes)
        embed.description = stereotype_list

        embed.set_footer(text=f"{len(stereotypes)} stereotype(s) available")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Set up the stereotypes cog."""
    await bot.add_cog(Stereotypes(bot))
