"""Main bot entry point for MTG Commander Tracker."""

import asyncio
import logging
from dotenv import load_dotenv
load_dotenv()

import discord
from discord import app_commands
from discord.ext import commands

from config import Config, EMBED_COLOR
from database import Database

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

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mtg-bot")


class MTGBot(commands.Bot):
    """MTG Commander Tracker Discord Bot."""

    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

        self.config = config
        self.db = Database(config.database_path)

    async def setup_hook(self) -> None:
        """Called when the bot is starting up."""
        log("BOT", "setup_hook starting...", Colors.GREEN)
        # Connect to database
        await self.db.connect()
        log("BOT", "Database connected", Colors.GREEN)

        # Load cogs
        await self.load_extension("cogs.game_logging")
        log("BOT", "  Loaded cogs.game_logging", Colors.GREEN)
        await self.load_extension("cogs.stats")
        log("BOT", "  Loaded cogs.stats", Colors.GREEN)
        await self.load_extension("cogs.stereotypes")
        log("BOT", "  Loaded cogs.stereotypes", Colors.GREEN)

        # Sync commands
        log("BOT", "Syncing commands...", Colors.GREEN)
        await self.tree.sync()
        log("BOT", "Commands synced!", Colors.GREEN)

    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        log("BOT", f"Logged in as {self.user} (ID: {self.user.id})", Colors.GREEN)
        log("BOT", f"Connected to {len(self.guilds)} guild(s)", Colors.GREEN)
        for guild in self.guilds:
            log("BOT", f"  - {guild.name} (ID: {guild.id})", Colors.GREEN)

    async def close(self) -> None:
        """Clean up on shutdown."""
        await self.db.close()
        await super().close()


# Create bot instance
bot: MTGBot = None


def get_bot() -> MTGBot:
    """Get the bot instance."""
    global bot
    return bot


@app_commands.command(name="help", description="Get help with MTG Commander Tracker commands")
async def help_command(interaction: discord.Interaction) -> None:
    """Display help information about all commands."""
    embed = discord.Embed(
        title="MTG Commander Tracker - Help",
        description="Track your Commander games and stats with your friends!",
        color=EMBED_COLOR
    )

    embed.add_field(
        name="Game Logging",
        value=(
            "**/log** - Log a new game (opens a form)\n"
        ),
        inline=False
    )

    embed.add_field(
        name="Statistics",
        value=(
            "**/leaderboard** - View the points leaderboard\n"
            "**/stats** `@player` - View a player's stats\n"
            "**/headtohead** `@player1` `@player2` - Compare two players\n"
            "**/deckstats** `[commander]` - View deck statistics\n"
            "**/recentgames** `[count]` - View recent games"
        ),
        inline=False
    )

    embed.add_field(
        name="Stereotypes",
        value=(
            "**/stereotypes** - View the Hall of Shame\n"
            "**/mystereotypes** `@player` - View a player's stereotypes\n"
            "**/addstereotype** `name` - Add a new stereotype"
        ),
        inline=False
    )

    embed.add_field(
        name="Scoring System",
        value=(
            "**Multiplayer:** 1st = 3pts, 2nd = 2pts, 3rd = 1pt, 4th = 0pts\n"
            "**1v1:** Winner = 3pts, Loser = 0pts"
        ),
        inline=False
    )

    embed.set_footer(text="May your draws be lucky!")

    await interaction.response.send_message(embed=embed)


async def main() -> None:
    """Main entry point."""
    global bot

    config = Config.from_env()
    bot = MTGBot(config)

    # Add help command to tree
    bot.tree.add_command(help_command)

    async with bot:
        await bot.start(config.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
