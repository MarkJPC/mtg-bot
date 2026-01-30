"""Environment configuration for MTG Commander Tracker Bot."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Bot configuration loaded from environment variables."""

    discord_token: str
    database_path: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("DISCORD_TOKEN environment variable is required")

        database_path = os.getenv("DATABASE_PATH", "mtg_tracker.db")

        return cls(
            discord_token=token,
            database_path=database_path,
        )


# Default win conditions
WIN_CONDITIONS = [
    "Combat damage",
    "Commander damage",
    "Combo",
    "Mill",
    "Infect",
    "Alt wincon",
    "Concession/scoop",
]

# Default stereotypes seeded on first run
DEFAULT_STEREOTYPES = [
    "Claims to not be the threat",
    "Never swings",
    'Said "not optimal"',
    "Missed their triggers",
]

# Scoring system
SCORING = {
    "multiplayer": {1: 3, 2: 2, 3: 1, 4: 0},
    "1v1": {1: 3, 2: 0},
}

# Embed color (purple/MTG themed)
EMBED_COLOR = 0x7B68EE  # Medium slate blue
