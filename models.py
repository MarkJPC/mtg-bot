"""Data models for MTG Commander Tracker Bot."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Player:
    """Represents a player in the database."""

    id: int
    discord_id: str
    username: str
    created_at: datetime


@dataclass
class Deck:
    """Represents a deck (commander) in the database."""

    id: int
    player_id: int
    commander_name: str
    created_at: datetime


@dataclass
class Game:
    """Represents a game in the database."""

    id: int
    game_type: str  # '1v1' or 'multiplayer'
    played_at: datetime
    duration_minutes: Optional[int]
    win_condition: str


@dataclass
class GamePlacement:
    """Represents a player's placement in a game."""

    id: int
    game_id: int
    player_id: int
    deck_id: int
    placement: int


@dataclass
class Stereotype:
    """Represents a stereotype that can be assigned to players."""

    id: int
    name: str
    created_at: datetime


@dataclass
class GameStereotype:
    """Links a stereotype to a player in a specific game."""

    id: int
    game_id: int
    player_id: int
    stereotype_id: int


@dataclass
class PlayerStats:
    """Computed statistics for a player."""

    player_id: int
    username: str
    total_games: int
    wins: int
    points: int
    win_rate: float
    favorite_deck: Optional[str]
    best_deck: Optional[str]
    current_streak: int


@dataclass
class DeckStats:
    """Computed statistics for a deck/commander."""

    commander_name: str
    total_games: int
    wins: int
    win_rate: float
    players: list[str]


@dataclass
class HeadToHeadStats:
    """Head-to-head statistics between two players."""

    player1_name: str
    player2_name: str
    player1_wins: int
    player2_wins: int
    games_together: int
    one_v_one_record: tuple[int, int]  # (player1_wins, player2_wins)
