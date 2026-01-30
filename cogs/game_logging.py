"""Game logging cog for MTG Commander Tracker Bot."""

import discord
from discord import app_commands, ui
from discord.ext import commands
from typing import Optional

from config import WIN_CONDITIONS, EMBED_COLOR
from utils import Colors, log
from utils.helpers import (
    parse_mentions,
    parse_player_names,
    create_error_embed,
    create_info_embed,
    format_placement,
    format_stereotype_narrative,
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
        original_message = self.view.original_message
        modal = GameLogModal(game_type, original_message)
        await interaction.response.send_modal(modal)


class GameTypeView(ui.View):
    """View containing game type selection."""

    def __init__(self):
        super().__init__(timeout=300)
        self.original_message = None  # Will be set after sending
        self.add_item(GameTypeSelect())


class GameLogModal(ui.Modal):
    """Modal for logging game details."""

    def __init__(self, game_type: str, original_message: Optional[discord.Message] = None):
        super().__init__(title=f"Log {game_type.upper()} Game")
        self.game_type = game_type
        self.original_message = original_message

        min_players = 2 if game_type == "1v1" else 3
        max_players = 2 if game_type == "1v1" else 4

        self.players = ui.TextInput(
            label=f"Players (in placement order, {min_players}-{max_players})",
            placeholder="Player1 Player2 (1st place to last - use Discord usernames)",
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
        log("GAME_LOG", f"Modal submitted by {interaction.user}", Colors.MAGENTA)
        log("GAME_LOG", f"  game_type: {self.game_type}", Colors.MAGENTA)
        log("GAME_LOG", f"  players raw input: '{self.players.value}'", Colors.MAGENTA)
        log("GAME_LOG", f"  decks raw input: '{self.decks.value}'", Colors.MAGENTA)
        log("GAME_LOG", f"  win_condition: '{self.win_condition.value}'", Colors.MAGENTA)
        log("GAME_LOG", f"  duration: '{self.duration.value}'", Colors.MAGENTA)

        # Get the bot's database
        bot = interaction.client
        db = bot.db

        # Parse player names/mentions
        player_inputs = parse_player_names(self.players.value)
        log("GAME_LOG", f"  parsed player_inputs: {player_inputs}", Colors.MAGENTA)

        # Validate player count
        min_players = 2 if self.game_type == "1v1" else 3
        max_players = 2 if self.game_type == "1v1" else 4

        if len(player_inputs) < min_players or len(player_inputs) > max_players:
            log("GAME_LOG", f"  ERROR: Invalid player count. Got {len(player_inputs)}, need {min_players}-{max_players}", Colors.RED)
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Invalid Player Count",
                    f"{self.game_type} requires {min_players}-{max_players} players. "
                    f"You provided {len(player_inputs)} players.\n\n"
                    "**Tip:** Enter player names separated by spaces or commas:\n"
                    "`Player1 Player2` or `Player1, Player2`"
                ),
                ephemeral=True
            )
            return

        # Parse decks
        deck_names = [d.strip() for d in self.decks.value.split(",")]
        log("GAME_LOG", f"  parsed deck_names: {deck_names}", Colors.MAGENTA)

        if len(deck_names) != len(player_inputs):
            log("GAME_LOG", f"  ERROR: Deck count mismatch. {len(player_inputs)} players, {len(deck_names)} decks", Colors.RED)
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Deck Count Mismatch",
                    f"You provided {len(player_inputs)} players but {len(deck_names)} decks. "
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

        # Resolve player names/IDs to Discord users
        resolved_users = []
        guild = interaction.guild

        for input_type, input_value in player_inputs:
            log("GAME_LOG", f"  Resolving player: type={input_type}, value={input_value}", Colors.MAGENTA)

            if input_type == "id":
                # It's a Discord user ID from a mention
                try:
                    user = await interaction.client.fetch_user(int(input_value))
                    resolved_users.append((str(user.id), user.display_name))
                    log("GAME_LOG", f"    Resolved by ID: {user.display_name}", Colors.GREEN)
                except discord.NotFound:
                    await interaction.response.send_message(
                        embed=create_error_embed(
                            "User Not Found",
                            f"Could not find user with ID {input_value}"
                        ),
                        ephemeral=True
                    )
                    return
            else:
                # It's a username - search in the guild
                if not guild:
                    await interaction.response.send_message(
                        embed=create_error_embed(
                            "Error",
                            "This command must be used in a server, not DMs."
                        ),
                        ephemeral=True
                    )
                    return

                # Search for member by name (case-insensitive)
                member = None
                input_lower = input_value.lower()

                for m in guild.members:
                    if (m.name.lower() == input_lower or
                        m.display_name.lower() == input_lower or
                        (m.global_name and m.global_name.lower() == input_lower)):
                        member = m
                        break

                if not member:
                    log("GAME_LOG", f"    ERROR: Could not find member '{input_value}'", Colors.RED)
                    # List available members for debugging
                    available = [f"{m.name} ({m.display_name})" for m in guild.members[:10]]
                    log("GAME_LOG", f"    Available members (first 10): {available}", Colors.YELLOW)
                    await interaction.response.send_message(
                        embed=create_error_embed(
                            "Player Not Found",
                            f"Could not find player **{input_value}** in this server.\n\n"
                            "Make sure the name matches their Discord username or display name exactly."
                        ),
                        ephemeral=True
                    )
                    return

                resolved_users.append((str(member.id), member.display_name))
                log("GAME_LOG", f"    Resolved by name: {member.display_name} (ID: {member.id})", Colors.GREEN)

        log("GAME_LOG", f"  All resolved users: {resolved_users}", Colors.GREEN)

        # Register/lookup players and decks
        placements = []
        player_data = []  # For summary display

        for i, ((discord_id, username), deck_name) in enumerate(zip(resolved_users, deck_names)):
            log("GAME_LOG", f"  Processing: {username} with deck {deck_name}", Colors.MAGENTA)

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
        view = StereotypeAssignmentView(game.id, player_data, self.original_message)
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
            stereotypes=stereotypes,
            original_message=self.view.original_message
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
        stereotypes: list,
        original_message: Optional[discord.Message] = None
    ):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.player_id = player_id
        self.player_name = player_name
        self.players = players
        self.selected_stereotype_ids = []
        self.original_message = original_message

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
                view=StereotypeAssignmentView(self.game_id, self.players, self.original_message)
            )
        else:
            await interaction.response.edit_message(
                content="No stereotypes selected. Select another player or click Done.",
                view=StereotypeAssignmentView(self.game_id, self.players, self.original_message)
            )

    @ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: ui.Button) -> None:
        """Go back to player selection."""
        await interaction.response.edit_message(
            content="Select a player to assign stereotypes to, or click Done.",
            view=StereotypeAssignmentView(self.game_id, self.players, self.original_message)
        )


class StereotypeAssignmentView(ui.View):
    """View for the stereotype assignment flow after logging a game."""

    def __init__(self, game_id: int, players: list[dict], original_message: Optional[discord.Message] = None):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.players = players
        self.original_message = original_message
        self.add_item(PlayerSelectForStereotype(players))

    @ui.button(label="Done", style=discord.ButtonStyle.success, row=1)
    async def done(self, interaction: discord.Interaction, button: ui.Button) -> None:
        """Finish stereotype assignment."""
        db = interaction.client.db
        stereotypes = await db.get_game_stereotypes(self.game_id)

        if stereotypes:
            narrative = format_stereotype_narrative(stereotypes)
            content = f"Game logging complete!\n\n{narrative}"
        else:
            content = "Game logging complete!"

        await interaction.response.edit_message(
            content=content,
            view=None
        )

        # Delete the original "Log a Game" prompt to reduce clutter
        if self.original_message:
            try:
                await self.original_message.delete()
            except discord.NotFound:
                pass  # Already deleted

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
        await interaction.response.defer()

        embed = create_info_embed(
            "Log a Game",
            "Select the game type to continue:"
        )

        view = GameTypeView()
        message = await interaction.followup.send(embed=embed, view=view)
        view.original_message = message


async def setup(bot: commands.Bot) -> None:
    """Set up the game logging cog."""
    await bot.add_cog(GameLogging(bot))
