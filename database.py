"""Database setup and async helpers for MTG Commander Tracker Bot."""

import aiosqlite
from datetime import datetime
from typing import Optional

from config import DEFAULT_STEREOTYPES, SCORING
from models import (
    Player, Deck, Game, GamePlacement, Stereotype,
    PlayerStats, DeckStats, HeadToHeadStats
)

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


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Establish database connection and initialize schema."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()
        await self._seed_stereotypes()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def conn(self) -> aiosqlite.Connection:
        """Get the active connection."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        await self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS decks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                commander_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players(id),
                UNIQUE(player_id, commander_name)
            );

            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_type TEXT NOT NULL CHECK (game_type IN ('1v1', 'multiplayer')),
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration_minutes INTEGER,
                win_condition TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS game_placements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                deck_id INTEGER NOT NULL,
                placement INTEGER NOT NULL CHECK (placement BETWEEN 1 AND 4),
                FOREIGN KEY (game_id) REFERENCES games(id),
                FOREIGN KEY (player_id) REFERENCES players(id),
                FOREIGN KEY (deck_id) REFERENCES decks(id),
                UNIQUE(game_id, player_id)
            );

            CREATE TABLE IF NOT EXISTS stereotypes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS game_stereotypes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                stereotype_id INTEGER NOT NULL,
                FOREIGN KEY (game_id) REFERENCES games(id),
                FOREIGN KEY (player_id) REFERENCES players(id),
                FOREIGN KEY (stereotype_id) REFERENCES stereotypes(id)
            );
        """)
        await self.conn.commit()

    async def _seed_stereotypes(self) -> None:
        """Seed default stereotypes if table is empty."""
        async with self.conn.execute("SELECT COUNT(*) FROM stereotypes") as cursor:
            row = await cursor.fetchone()
            if row[0] == 0:
                for name in DEFAULT_STEREOTYPES:
                    await self.conn.execute(
                        "INSERT INTO stereotypes (name) VALUES (?)",
                        (name,)
                    )
                await self.conn.commit()

    # Player operations
    async def get_or_create_player(self, discord_id: str, username: str) -> Player:
        """Get existing player or create new one."""
        async with self.conn.execute(
            "SELECT * FROM players WHERE discord_id = ?",
            (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                # Update username if changed
                if row["username"] != username:
                    await self.conn.execute(
                        "UPDATE players SET username = ? WHERE id = ?",
                        (username, row["id"])
                    )
                    await self.conn.commit()
                return Player(
                    id=row["id"],
                    discord_id=row["discord_id"],
                    username=username,
                    created_at=datetime.fromisoformat(row["created_at"])
                )

        # Create new player
        async with self.conn.execute(
            "INSERT INTO players (discord_id, username) VALUES (?, ?)",
            (discord_id, username)
        ) as cursor:
            player_id = cursor.lastrowid
        await self.conn.commit()

        return Player(
            id=player_id,
            discord_id=discord_id,
            username=username,
            created_at=datetime.now()
        )

    async def get_player_by_discord_id(self, discord_id: str) -> Optional[Player]:
        """Get player by Discord ID."""
        log("DB", f"get_player_by_discord_id({discord_id})", Colors.BLUE)
        async with self.conn.execute(
            "SELECT * FROM players WHERE discord_id = ?",
            (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                player = Player(
                    id=row["id"],
                    discord_id=row["discord_id"],
                    username=row["username"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )
                log("DB", f"  Found player: {player.username} (db_id={player.id})", Colors.BLUE)
                return player
        log("DB", f"  No player found for discord_id={discord_id}", Colors.YELLOW)
        return None

    # Deck operations
    async def get_or_create_deck(self, player_id: int, commander_name: str) -> Deck:
        """Get existing deck or create new one."""
        commander_name = commander_name.strip()

        async with self.conn.execute(
            "SELECT * FROM decks WHERE player_id = ? AND commander_name = ?",
            (player_id, commander_name)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Deck(
                    id=row["id"],
                    player_id=row["player_id"],
                    commander_name=row["commander_name"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )

        # Create new deck
        async with self.conn.execute(
            "INSERT INTO decks (player_id, commander_name) VALUES (?, ?)",
            (player_id, commander_name)
        ) as cursor:
            deck_id = cursor.lastrowid
        await self.conn.commit()

        return Deck(
            id=deck_id,
            player_id=player_id,
            commander_name=commander_name,
            created_at=datetime.now()
        )

    # Game operations
    async def create_game(
        self,
        game_type: str,
        win_condition: str,
        placements: list[tuple[int, int, int]],  # [(player_id, deck_id, placement), ...]
        duration_minutes: Optional[int] = None
    ) -> Game:
        """Create a new game with placements."""
        async with self.conn.execute(
            "INSERT INTO games (game_type, win_condition, duration_minutes) VALUES (?, ?, ?)",
            (game_type, win_condition, duration_minutes)
        ) as cursor:
            game_id = cursor.lastrowid

        for player_id, deck_id, placement in placements:
            await self.conn.execute(
                "INSERT INTO game_placements (game_id, player_id, deck_id, placement) VALUES (?, ?, ?, ?)",
                (game_id, player_id, deck_id, placement)
            )

        await self.conn.commit()

        return Game(
            id=game_id,
            game_type=game_type,
            played_at=datetime.now(),
            duration_minutes=duration_minutes,
            win_condition=win_condition
        )

    async def get_recent_games(self, limit: int = 5) -> list[dict]:
        """Get recent games with details."""
        async with self.conn.execute("""
            SELECT
                g.id,
                g.game_type,
                g.played_at,
                g.win_condition,
                g.duration_minutes
            FROM games g
            ORDER BY g.played_at DESC
            LIMIT ?
        """, (limit,)) as cursor:
            games = []
            async for row in cursor:
                game_data = {
                    "id": row["id"],
                    "game_type": row["game_type"],
                    "played_at": row["played_at"],
                    "win_condition": row["win_condition"],
                    "duration_minutes": row["duration_minutes"],
                    "players": []
                }

                # Get placements for this game
                async with self.conn.execute("""
                    SELECT
                        p.username,
                        d.commander_name,
                        gp.placement
                    FROM game_placements gp
                    JOIN players p ON gp.player_id = p.id
                    JOIN decks d ON gp.deck_id = d.id
                    WHERE gp.game_id = ?
                    ORDER BY gp.placement
                """, (row["id"],)) as placement_cursor:
                    async for placement_row in placement_cursor:
                        game_data["players"].append({
                            "username": placement_row["username"],
                            "commander": placement_row["commander_name"],
                            "placement": placement_row["placement"]
                        })

                games.append(game_data)

            return games

    # Stats operations
    async def get_leaderboard(self) -> list[PlayerStats]:
        """Get leaderboard sorted by points."""
        async with self.conn.execute("""
            SELECT
                p.id as player_id,
                p.username,
                COUNT(gp.id) as total_games,
                SUM(CASE WHEN gp.placement = 1 THEN 1 ELSE 0 END) as wins
            FROM players p
            LEFT JOIN game_placements gp ON p.id = gp.player_id
            GROUP BY p.id
            HAVING total_games > 0
        """) as cursor:
            stats = []
            async for row in cursor:
                # Calculate points
                points = await self._calculate_player_points(row["player_id"])
                win_rate = (row["wins"] / row["total_games"] * 100) if row["total_games"] > 0 else 0

                stats.append(PlayerStats(
                    player_id=row["player_id"],
                    username=row["username"],
                    total_games=row["total_games"],
                    wins=row["wins"],
                    points=points,
                    win_rate=win_rate,
                    favorite_deck=None,
                    best_deck=None,
                    current_streak=0
                ))

            # Sort by points descending
            stats.sort(key=lambda x: x.points, reverse=True)
            return stats

    async def _calculate_player_points(self, player_id: int) -> int:
        """Calculate total points for a player."""
        points = 0
        async with self.conn.execute("""
            SELECT g.game_type, gp.placement
            FROM game_placements gp
            JOIN games g ON gp.game_id = g.id
            WHERE gp.player_id = ?
        """, (player_id,)) as cursor:
            async for row in cursor:
                game_type = row["game_type"]
                placement = row["placement"]
                points += SCORING.get(game_type, {}).get(placement, 0)
        return points

    async def get_player_stats(self, discord_id: str) -> Optional[PlayerStats]:
        """Get detailed stats for a specific player."""
        player = await self.get_player_by_discord_id(discord_id)
        if not player:
            return None

        # Basic stats
        async with self.conn.execute("""
            SELECT
                COUNT(gp.id) as total_games,
                SUM(CASE WHEN gp.placement = 1 THEN 1 ELSE 0 END) as wins
            FROM game_placements gp
            WHERE gp.player_id = ?
        """, (player.id,)) as cursor:
            row = await cursor.fetchone()
            total_games = row["total_games"] or 0
            wins = row["wins"] or 0

        points = await self._calculate_player_points(player.id)
        win_rate = (wins / total_games * 100) if total_games > 0 else 0

        # Favorite deck (most played)
        favorite_deck = None
        async with self.conn.execute("""
            SELECT d.commander_name, COUNT(*) as play_count
            FROM game_placements gp
            JOIN decks d ON gp.deck_id = d.id
            WHERE gp.player_id = ?
            GROUP BY d.id
            ORDER BY play_count DESC
            LIMIT 1
        """, (player.id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                favorite_deck = row["commander_name"]

        # Best deck (highest win rate, min 3 games)
        best_deck = None
        async with self.conn.execute("""
            SELECT
                d.commander_name,
                COUNT(*) as games,
                SUM(CASE WHEN gp.placement = 1 THEN 1 ELSE 0 END) as wins
            FROM game_placements gp
            JOIN decks d ON gp.deck_id = d.id
            WHERE gp.player_id = ?
            GROUP BY d.id
            HAVING games >= 3
            ORDER BY (CAST(wins AS FLOAT) / games) DESC
            LIMIT 1
        """, (player.id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                best_deck = row["commander_name"]

        # Current win streak
        current_streak = 0
        async with self.conn.execute("""
            SELECT gp.placement
            FROM game_placements gp
            JOIN games g ON gp.game_id = g.id
            WHERE gp.player_id = ?
            ORDER BY g.played_at DESC
        """, (player.id,)) as cursor:
            async for row in cursor:
                if row["placement"] == 1:
                    current_streak += 1
                else:
                    break

        return PlayerStats(
            player_id=player.id,
            username=player.username,
            total_games=total_games,
            wins=wins,
            points=points,
            win_rate=win_rate,
            favorite_deck=favorite_deck,
            best_deck=best_deck,
            current_streak=current_streak
        )

    async def get_head_to_head(self, discord_id1: str, discord_id2: str) -> Optional[HeadToHeadStats]:
        """Get head-to-head stats between two players."""
        log("DB", f"get_head_to_head({discord_id1}, {discord_id2})", Colors.BLUE)
        player1 = await self.get_player_by_discord_id(discord_id1)
        player2 = await self.get_player_by_discord_id(discord_id2)

        log("DB", f"  player1 lookup result: {player1}", Colors.BLUE)
        log("DB", f"  player2 lookup result: {player2}", Colors.BLUE)

        if not player1 or not player2:
            log("DB", f"  Returning None - missing player(s)", Colors.YELLOW)
            return None

        # Games where both players participated
        async with self.conn.execute("""
            SELECT g.id, g.game_type
            FROM games g
            WHERE g.id IN (
                SELECT game_id FROM game_placements WHERE player_id = ?
            )
            AND g.id IN (
                SELECT game_id FROM game_placements WHERE player_id = ?
            )
        """, (player1.id, player2.id)) as cursor:
            shared_games = await cursor.fetchall()

        games_together = len(shared_games)
        player1_wins = 0
        player2_wins = 0
        one_v_one_p1 = 0
        one_v_one_p2 = 0

        for game in shared_games:
            # Get winner of this game
            async with self.conn.execute("""
                SELECT player_id FROM game_placements
                WHERE game_id = ? AND placement = 1
            """, (game["id"],)) as cursor:
                winner_row = await cursor.fetchone()
                if winner_row:
                    winner_id = winner_row["player_id"]
                    if winner_id == player1.id:
                        player1_wins += 1
                        if game["game_type"] == "1v1":
                            one_v_one_p1 += 1
                    elif winner_id == player2.id:
                        player2_wins += 1
                        if game["game_type"] == "1v1":
                            one_v_one_p2 += 1

        return HeadToHeadStats(
            player1_name=player1.username,
            player2_name=player2.username,
            player1_wins=player1_wins,
            player2_wins=player2_wins,
            games_together=games_together,
            one_v_one_record=(one_v_one_p1, one_v_one_p2)
        )

    async def get_deck_stats(self, commander_name: Optional[str] = None) -> list[DeckStats]:
        """Get stats for a specific deck or top decks."""
        if commander_name:
            # Stats for specific commander
            async with self.conn.execute("""
                SELECT
                    d.commander_name,
                    COUNT(gp.id) as games,
                    SUM(CASE WHEN gp.placement = 1 THEN 1 ELSE 0 END) as wins,
                    GROUP_CONCAT(DISTINCT p.username) as players
                FROM decks d
                JOIN game_placements gp ON d.id = gp.deck_id
                JOIN players p ON d.player_id = p.id
                WHERE LOWER(d.commander_name) LIKE LOWER(?)
                GROUP BY d.commander_name
            """, (f"%{commander_name}%",)) as cursor:
                stats = []
                async for row in cursor:
                    win_rate = (row["wins"] / row["games"] * 100) if row["games"] > 0 else 0
                    stats.append(DeckStats(
                        commander_name=row["commander_name"],
                        total_games=row["games"],
                        wins=row["wins"],
                        win_rate=win_rate,
                        players=row["players"].split(",") if row["players"] else []
                    ))
                return stats
        else:
            # Top 10 decks by win rate (min 3 games)
            async with self.conn.execute("""
                SELECT
                    d.commander_name,
                    COUNT(gp.id) as games,
                    SUM(CASE WHEN gp.placement = 1 THEN 1 ELSE 0 END) as wins,
                    GROUP_CONCAT(DISTINCT p.username) as players
                FROM decks d
                JOIN game_placements gp ON d.id = gp.deck_id
                JOIN players p ON d.player_id = p.id
                GROUP BY d.commander_name
                HAVING games >= 3
                ORDER BY (CAST(wins AS FLOAT) / games) DESC
                LIMIT 10
            """) as cursor:
                stats = []
                async for row in cursor:
                    win_rate = (row["wins"] / row["games"] * 100) if row["games"] > 0 else 0
                    stats.append(DeckStats(
                        commander_name=row["commander_name"],
                        total_games=row["games"],
                        wins=row["wins"],
                        win_rate=win_rate,
                        players=row["players"].split(",") if row["players"] else []
                    ))
                return stats

    # Stereotype operations
    async def get_all_stereotypes(self) -> list[Stereotype]:
        """Get all available stereotypes."""
        async with self.conn.execute(
            "SELECT * FROM stereotypes ORDER BY name"
        ) as cursor:
            return [
                Stereotype(
                    id=row["id"],
                    name=row["name"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )
                async for row in cursor
            ]

    async def add_stereotype(self, name: str) -> Optional[Stereotype]:
        """Add a new stereotype. Returns None if it already exists."""
        try:
            async with self.conn.execute(
                "INSERT INTO stereotypes (name) VALUES (?)",
                (name.strip(),)
            ) as cursor:
                stereotype_id = cursor.lastrowid
            await self.conn.commit()

            return Stereotype(
                id=stereotype_id,
                name=name.strip(),
                created_at=datetime.now()
            )
        except aiosqlite.IntegrityError:
            return None

    async def assign_stereotypes(
        self,
        game_id: int,
        player_id: int,
        stereotype_ids: list[int]
    ) -> None:
        """Assign stereotypes to a player for a specific game."""
        for stereotype_id in stereotype_ids:
            await self.conn.execute(
                "INSERT INTO game_stereotypes (game_id, player_id, stereotype_id) VALUES (?, ?, ?)",
                (game_id, player_id, stereotype_id)
            )
        await self.conn.commit()

    async def get_stereotype_leaderboard(self) -> list[tuple[str, str, int]]:
        """Get stereotype counts per player (hall of shame)."""
        async with self.conn.execute("""
            SELECT
                p.username,
                s.name as stereotype_name,
                COUNT(*) as count
            FROM game_stereotypes gs
            JOIN players p ON gs.player_id = p.id
            JOIN stereotypes s ON gs.stereotype_id = s.id
            GROUP BY p.id, s.id
            ORDER BY count DESC
        """) as cursor:
            return [(row["username"], row["stereotype_name"], row["count"]) async for row in cursor]

    async def get_player_stereotypes(self, discord_id: str) -> list[tuple[str, int]]:
        """Get stereotype counts for a specific player."""
        player = await self.get_player_by_discord_id(discord_id)
        if not player:
            return []

        async with self.conn.execute("""
            SELECT s.name, COUNT(*) as count
            FROM game_stereotypes gs
            JOIN stereotypes s ON gs.stereotype_id = s.id
            WHERE gs.player_id = ?
            GROUP BY s.id
            ORDER BY count DESC
        """, (player.id,)) as cursor:
            return [(row["name"], row["count"]) async for row in cursor]

    async def get_game_stereotypes(self, game_id: int) -> list[tuple[str, str]]:
        """Get all stereotypes assigned in a specific game.

        Returns list of (player_name, stereotype_name) tuples.
        """
        async with self.conn.execute("""
            SELECT p.username, s.name as stereotype_name
            FROM game_stereotypes gs
            JOIN players p ON gs.player_id = p.id
            JOIN stereotypes s ON gs.stereotype_id = s.id
            WHERE gs.game_id = ?
            ORDER BY p.username, s.name
        """, (game_id,)) as cursor:
            return [(row["username"], row["stereotype_name"]) async for row in cursor]
