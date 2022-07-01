from typing import Any, Optional
from contextlib import closing as contextlib_closing
from collections import defaultdict
from discord.ext import commands, tasks
from bot.main import GuildBot, basic_extension_setup
from bot.cogs.xp.group import XPCommandGroup as XPCommandGroupCog
import sqlite3
from math import exp, log, floor


def SafeCursor(conn: sqlite3.Connection) -> contextlib_closing[sqlite3.Cursor]:
    return contextlib_closing(conn.cursor())


class XPHandling(commands.Cog):
    data_directory = "data/xp/"
    database_filename = "experience.sql"

    default_curve_scalar = 100
    default_curve_power = 2

    default_message_reward = 50
    default_reply_reward = 50
    default_react_reward = 35
    default_voice_reward = 15

    default_xp_gain_cap = 150

    class Math:
        @staticmethod
        def nth_root_of_x(n: float, x: float):
            """Calculate the nth root of X using exponent and natural log.
            exp(log(x) / n) = x^(1/n)
            exp(1/n * log(x) ) = x^(1/n)
            The 1/n can be brought within the log, at which point the exp(log()) cancel one another out.
            x^(1/n) = x^(1/n)

            Parameters
            ----------
            n : float
                The root index.
            x : float
                The value being rooted.
            """
            return exp(log(x) / n)

    def __init__(self, bot: GuildBot):
        self.bot = bot

        self.database_path = self.data_directory + self.database_filename

        self.database_connection: Optional[sqlite3.Connection] = None
        self.database_schema: str = f"Guild{self.bot.guild.id}"

        self.level_curve_scalar = self.default_curve_scalar
        self.level_curve_power = self.default_curve_power

        self.reward_xp_message = self.default_message_reward
        self.reward_xp_reply = self.default_reply_reward
        self.reward_xp_react = self.default_react_reward
        self.reward_xp_voice = self.default_voice_reward

        self.xp_gain_cap = self.default_xp_gain_cap

        self.action_rewards = {}

        self._xp_additions = defaultdict(lambda x: 0)

    def cog_load(self) -> None:
        self.database_connection = sqlite3.connect(self.database_path)
        self.database_connection.row_factory = sqlite3.Row

        with self.database_connection, SafeCursor(self.database_connection) as cursor:
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {self.database_schema} (userid INTEGER PRIMARY KEY, experience FLOAT, experience_level INTEGER);")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS GuildData (guildid INTEGER PRIMARY KEY, curve_scalar FLOAT, curve_power FLOAT, reward_voice FLOAT, reward_message FLOAT, reward_reply FLOAT, reward_react FLOAT, xp_gain_cap FLOAT)")
            cursor.execute(f"INSERT OR IGNORE INTO GuildData (guildid) VALUES (?)", (self.bot.guild.id,))

        self.load_all_guild_data()

        self.do_experience_additions.start()

    async def cog_unload(self) -> None:
        self.save_all_guild_data()
        self.do_experience_additions.cancel()
        await self.do_experience_additions()
        self.database_connection.close()

    def save_all_guild_data(self):
        with self.database_connection, SafeCursor(self.database_connection) as cursor:
            cursor.execute(f"UPDATE GuildData SET curve_scalar=?, curve_power=?, reward_voice=?, reward_message=?, reward_reply=?, reward_react=?, xp_gain_cap=? WHERE guildid=?", (self.level_curve_scalar, self.level_curve_power, self.reward_xp_voice, self.reward_xp_message, self.reward_xp_reply, self.reward_xp_react, self.xp_gain_cap, self.bot.guild.id,))

    def load_all_guild_data(self):
        with SafeCursor(self.database_connection) as cursor:
            cursor.execute(f"SELECT * FROM GuildData WHERE guildid=?", (self.bot.guild.id,))
            guild_data: sqlite3.Row = cursor.fetchone()

        if guild_data is None:
            return

        self.level_curve_scalar = guild_data["curve_scalar"]
        self.level_curve_power = guild_data["curve_power"]
        self.reward_xp_message = guild_data["reward_message"]
        self.reward_xp_reply = guild_data["reward_reply"]
        self.reward_xp_react = guild_data["reward_react"]
        self.reward_xp_voice = guild_data["reward_voice"]
        self.xp_gain_cap = guild_data["xp_gain_cap"]

    def basic_database_query(self, query: str, fields: Optional[tuple[Any, ...]] = tuple(), quantity: Optional[int] = 1) -> [sqlite3.Row] or sqlite3.Row:
        """Basic experience database query.
        When Quantity is 1, returns a tuple representing a database entry.
        When Quantity is a positive integer or -1, returns a list of tuples, each tuple representing a database entry.

        Parameters
        ----------
        query : str
            The SQLite3 query to execute.
        fields : Optional[tuple[Any, ...]]
            Fields to fill into the SQLite command.
        quantity : Optional[int]
            Number of results to fetch. -1 fetches all.
        """
        if query[:6].upper() != "SELECT":
            raise TypeError("SQLite command provided is not a query.")

        if quantity < -1:
            raise ValueError("Quantity cannot be negative (except -1).")

        with SafeCursor(self.database_connection) as cursor:
            cursor.execute(query, fields)
            if quantity == 1:
                result = cursor.fetchone()
            elif quantity == -1:
                result = cursor.fetchall()
            else:
                result = cursor.fetchmany(quantity)
            return result

    def database_get_by_userid_command(self, field_names):
        return f"SELECT {', '.join(field_names)} FROM {self.database_schema} WHERE userid=?"

    def database_get_by_userid(self, user_id: int, field_names: [str]) -> sqlite3.Row:
        """Query the experience database for a user's fields.

        Parameters
        ----------
        user_id : int
            Discord User ID to lookup in the database.
        field_names : [str]
            Array of field names to query.
        """
        return self.basic_database_query(self.database_get_by_userid_command(field_names), (user_id,), 1)

    def database_get_many_by_userid(self, user_ids: [int], field_names: [str]) -> [sqlite3.Row]:
        """Query the experience database for some users' fields.

        Parameters
        ----------
        user_ids : [int]
            Discord User ID array to lookup in the database.
        field_names : [str]
            Array of field names to query.
        """
        return self.basic_database_query(self.database_get_by_userid_command(field_names), (user_ids,), -1)

    def basic_database_update(self, update: str, fields: Optional[tuple[Any, ...]] = tuple()):
        if update[:6].upper() != "UPDATE":
            raise TypeError("SQLite command provided is not an UPDATE.")

        with self.database_connection, SafeCursor(self.database_connection) as cursor:
            cursor.execute(update, fields)

    def basic_database_update_many(self, update: str, fields_array: [tuple[Any, ...]]):
        if update[:6].upper() != "UPDATE":
            raise TypeError("SQLite command provided is not an UPDATE.")

        with self.database_connection, SafeCursor(self.database_connection) as cursor:
            cursor.executemany(update, fields_array)

    def database_update_by_userid_command(self, field_names: [str]) -> str:
        return f"UPDATE {self.database_schema} SET {', '.join([field_name + '=?' for field_name in field_names])} WHERE userid=? LIMIT 1"

    def database_update_by_userid(self, user_id: int, fields: dict[str, Any]):
        self.basic_database_update(self.database_update_by_userid_command(fields.keys()), tuple(fields.values()) + (user_id,))

    def update_level_curve(self, scalar: float, power: float, maintain_level: bool):
        """Update the level XP requirement curve.
        Level XP Requirement = scalar * Level ** power

        Parameters
        ----------
        scalar : float
            The scalar in the requirement curve expression.
        power : float
            The power in the requirement curve expression.
        maintain_level : bool
            Whether to change users' XP quantities to keep their levels the same.
            If this is false, users' levels will be changed instead.
        """
        pass

    def get_floored_level_from_experience(self, xp_quantity: float) -> int:
        """Query what experience level (rounded down) an arbitrary user would be based on an XP quantity."""
        return floor(self.get_level_from_experience(xp_quantity))

    def get_level_experience_requirement(self, level: int) -> float:
        """Query what total XP quantity is required for an experience level."""
        return self.level_curve_scalar * level ** self.level_curve_power

    def get_relative_level_experience_requirement(self, level: int) -> float:
        """Query what XP quantity is required to level up from the previous level, to the level specified."""
        return self.get_level_experience_requirement(level) - self.get_level_experience_requirement(level - 1)

    def get_level_progress_from_experience(self, xp_quantity: float) -> float:
        """Query progress from the previous to the next level based upon an XP quantity."""
        return self.get_level_from_experience(xp_quantity) % 1

    def get_level_from_experience(self, xp_quantity: float) -> float:
        """Query the exact experience level (as float) of an arbitrary user based on XP quantity."""
        return self.Math.nth_root_of_x(self.level_curve_power, (xp_quantity / self.level_curve_scalar))

    def _execute_add_experience_to_many(self, xp_additions: dict[int, float]):
        """Add experience to a bunch of users, check for level ups, and handle accordingly.

        Parameters
        ----------
        xp_additions : dict[int, float]
            A dictionary of user_id to xp_quantity to add.
        """
        current_data = self.database_get_many_by_userid(xp_additions.keys(), ("user_id", "experience", "experience_level"))

        for row in current_data:
            new_experience = row["experience"] + min(xp_additions[row["user_id"]], self.xp_gain_cap)
            new_level = self.get_floored_level_from_experience(new_experience)
            self.database_update_by_userid(row["user_id"], {"experience": new_experience, "level": new_level})

            if row["level"] != new_level:
                self.bot.loop.create_task(self.on_level_up(row["user_id"], new_level))

    def add_experience(self, user_id: int, xp_quantity: float):
        self._xp_additions[user_id] += xp_quantity

    async def on_level_up(self, user_id: int, new_level: int):
        pass

    @tasks.loop(seconds=60.0)
    async def do_experience_additions(self):
        cached_xp_additions = self._xp_additions.copy()
        self._xp_additions.clear()
        self._execute_add_experience_to_many(cached_xp_additions)

    @do_experience_additions.before_loop
    async def before_do_experience_additions(self):
        await self.bot.wait_until_ready()


class XPCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.handler: Optional[XPHandling] = None
        self.command_group_cog: Optional[XPCommandGroupCog] = None

    def cog_load(self) -> None:
        self.handler = self.bot.get_cog("XPHandling")
        self.command_group_cog = self.bot.get_cog("XPCommandGroup")


class XPCommandCog(XPCog):
    def cog_load(self) -> None:
        super().cog_load()
        self.register_commands()

    def register_commands(self) -> None:
        pass


setup = basic_extension_setup(XPHandling)
