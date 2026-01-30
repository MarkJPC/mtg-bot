"""Game logging cog for MTG Commander Tracker Bot."""

import discord
from discord import app_commands, ui
from discord.ext import commands
from typing import Optional

from config import WIN_CONDITIONS, EMBED_COLOR
from utils.helpers import (
    parse_mentions,
    create_error_embed,
    create_info_embed,
    format_placement,
)


class GameTypeSelect(ui.Select):
    """Select menu for choosing game type."""

    def __init__(self):
        options = [
            discord.SelectOption(
                label="1v1",
                value="1v1",
                description="Two player duel"
            ),
            discord.SelectOption(
                label="Multiplayer",
                value="multiplayer",
                description="3-4 player free-for-all"
            ),
        ]
        super().__init__(
            placeholder="Select game type...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        game_type = self.values[0]
        modal = GameLogModal(game_type)
        await interaction.response.send_modal(modal)


class GameTypeView(ui.View):
    """View containing game type selection."""

    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(GameTypeSelect())


class GameLogModal(ui.Modal):
    """Modal for logging game details."""

    def __init__(self, game_type: str):
        super().__init__(title=f"Log {game_type.upper()} Game")
        self.game_type = game_type

        min_players = 2 if game_type == "1v1" else 3
        max_players = 2 if game_type == "1v1" else 4

        self.players = ui.TextInput(
            label=f"Players (in placement order, {min_players}-{max_players})",
            placeholder="@Player1 @Player2 @Player3 @Player4 (1st to last)",
            style=discord.TextStyle.short,
            required=True
        )

        self.decks = ui.TextInput(
            label="Decks/Commanders (same order as players)",
            placeholder="Atraxa, Korvold, Urza, Yuriko",
            style=discord.TextStyle.short,
            required=True
        )

        self.win_condition = ui.TextInput(
            label="Win Condition",
            placeholder="Combat damage, Combo, Mill, Commander damage, etc.",
            style=discord.TextStyle.short,
            required=True
        )

        self.duration = ui.TextInput(
            label="Duration (minutes, optional)",
            placeholder="60",
            style=discord.TextStyle.short,
            required=False
        )

        self.add_item(self.players)
        self.add_item(self.decks)
        self.add_item(self.win_condition)
        self.add_item(self.duration)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Process the submitted game data."""
        # Get the bot's database
        bot = interaction.client
        db = bot.db

        # Parse player mentions
        player_ids = parse_mentions(self.players.value)

        # Validate player count
        min_players = 2 if self.game_type == "1v1" else 3
        max_players = 2 if self.game_type == "1v1" else 4

        if len(player_ids) < min_players or len(player_ids) > max_players:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Invalid Player Count",
                    f"{self.game_type} requires {min_players}-{max_players} players. "
                    f"You mentioned {len(player_ids)} players."
                ),
                ephemeral=True
            )
            return

        # Parse decks
        deck_names = [d.strip() for d in self.decks.value.split(",")]

        if len(deck_names) != len(player_ids):
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Deck Count Mismatch",
                    f"You mentioned {len(player_ids)} players but provided {len(deck_names)} decks. "
                    "Make sure to separate deck names with commas."
                ),
                ephemeral=True
            )
            return

        # Parse duration
        duration = None
        if self.duration.value:
            try:
                duration = int(self.duration.value)
                if duration <= 0:
                    raise ValueError()
            except ValueError:
                await interaction.response.send_message(
                    embed=create_error_embed(
                        "Invalid Duration",
                        "Duration must be a positive number (minutes)."
                    ),
                    ephemeral=True
                )
                return

        # Register/lookup players and decks
        placements = []
        player_data = []  # For summary display

        for i, (discord_id, deck_name) in enumerate(zip(player_ids, deck_names)):
            # Fetch user from Discord
            try:
                user = await interaction.client.fetch_user(int(discord_id))
                username = user.display_name
            except discord.NotFound:
                await interaction.response.send_message(
                    embed=create_error_embed(
                        "User Not Found",
                        f"Could not find user with ID {discord_id}"
                    ),
                    ephemeral=True
                )
                return

            # Get or create player
            player = await db.get_or_create_player(discord_id, username)

            # Get or create deck
            deck = await db.get_or_create_deck(player.id, deck_name)

            # Placement is index + 1 (1st, 2nd, 3rd, 4th)
            placement = i + 1
            placements.append((player.id, deck.id, placement))
            player_data.append({
                "username": username,
                "deck": deck_name,
                "placement": placement,
                "player_id": player.id
            })

        # Create the game
        game = await db.create_game(
            game_type=self.game_type,
            win_condition=self.win_condition.value,
            placements=placements,
            duration_minutes=duration
        )

        # Create summary embed
        embed = create_info_embed(
            f"Game #{game.id} Logged!",
            f"**Type:** {self.game_type}\n"
            f"**Win Condition:** {self.win_condition.value}\n"
            f"**Duration:** {duration or 'N/A'} minutes"
        )

        # Add placements
        placements_text = ""
        for p in player_data:
            place_str = format_placement(p["placement"])
            placements_text += f"{place_str}: **{p['username']}** ({p['deck']})\n"

        embed.add_field(name="Results", value=placements_text, inline=False)

        # Send response with stereotype assignment view
        view = StereotypeAssignmentView(game.id, player_data)
        await interaction.response.send_message(
            embed=embed,
            view=view
        )


class PlayerSelectForStereotype(ui.Select):
    """Select menu for choosing a player to assign stereotypes to."""

    def __init__(self, players: list[dict]):
        options = [
            discord.SelectOption(
                label=p["username"],
                value=str(p["player_id"]),
                description=f"Playing {p['deck']}"
            )
            for p in players
        ]
        super().__init__(
            placeholder="Select a player to assign stereotypes...",
            options=options,
            min_values=1,
            max_values=1
        )
        self.players = players

    async def callback(self, interaction: discord.Interaction) -> None:
        player_id = int(self.values[0])
        player_name = next(
            p["username"] for p in self.players if p["player_id"] == player_id
        )

        # Get stereotypes from database
        db = interaction.client.db
        stereotypes = await db.get_all_stereotypes()

        # Show stereotype selection
        view = StereotypeSelectionView(
            game_id=self.view.game_id,
            player_id=player_id,
            player_name=player_name,
            players=self.players,
            stereotypes=stereotypes
        )

        await interaction.response.edit_message(
            content=f"Select stereotypes for **{player_name}**:",
            view=view
        )


class StereotypeSelect(ui.Select):
    """Multi-select for stereotypes."""

    def __init__(self, stereotypes: list):
        options = [
            discord.SelectOption(label=s.name, value=str(s.id))
            for s in stereotypes[:25]  # Discord limit is 25 options
        ]
        super().__init__(
            placeholder="Select stereotypes...",
            options=options,
            min_values=0,
            max_values=min(len(options), 25)
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        # Store selected stereotypes in the view
        self.view.selected_stereotype_ids = [int(v) for v in self.values]
        await interaction.response.defer()


class StereotypeSelectionView(ui.View):
    """View for selecting stereotypes for a player."""

    def __init__(
        self,
        game_id: int,
        player_id: int,
        player_name: str,
        players: list[dict],
        stereotypes: list
    ):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.player_id = player_id
        self.player_name = player_name
        self.players = players
        self.selected_stereotype_ids = []

        self.add_item(StereotypeSelect(stereotypes))

    @ui.button(label="Confirm", style=discord.ButtonStyle.primary, row=1)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button) -> None:
        """Confirm stereotype assignment."""
        if self.selected_stereotype_ids:
            db = interaction.client.db
            await db.assign_stereotypes(
                self.game_id,
                self.player_id,
                self.selected_stereotype_ids
            )

            # Get stereotype names for confirmation
            stereotypes = await db.get_all_stereotypes()
            names = [
                s.name for s in stereotypes
                if s.id in self.selected_stereotype_ids
            ]

            await interaction.response.edit_message(
                content=f"Assigned to **{self.player_name}**: {', '.join(names)}\n\n"
                        "Select another player or click Done.",
                view=StereotypeAssignmentView(self.game_id, self.players)
            )
        else:
            await interaction.response.edit_message(
                content="No stereotypes selected. Select another player or click Done.",
                view=StereotypeAssignmentView(self.game_id, self.players)
            )

    @ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: ui.Button) -> None:
        """Go back to player selection."""
        await interaction.response.edit_message(
            content="Select a player to assign stereotypes to, or click Done.",
            view=StereotypeAssignmentView(self.game_id, self.players)
        )


class StereotypeAssignmentView(ui.View):
    """View for the stereotype assignment flow after logging a game."""

    def __init__(self, game_id: int, players: list[dict]):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.players = players
        self.add_item(PlayerSelectForStereotype(players))

    @ui.button(label="Done", style=discord.ButtonStyle.success, row=1)
    async def done(self, interaction: discord.Interaction, button: ui.Button) -> None:
        """Finish stereotype assignment."""
        await interaction.response.edit_message(
            content="Game logging complete!",
            view=None
        )

    async def on_timeout(self) -> None:
        """Handle view timeout."""
        # View timed out, nothing to do
        pass


class GameLogging(commands.Cog):
    """Cog for logging games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="log", description="Log a new Commander game")
    async def log_game(self, interaction: discord.Interaction) -> None:
        """Start the game logging flow."""
        embed = create_info_embed(
            "Log a Game",
            "Select the game type to continue:"
        )

        view = GameTypeView()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    """Set up the game logging cog."""
    await bot.add_cog(GameLogging(bot))
