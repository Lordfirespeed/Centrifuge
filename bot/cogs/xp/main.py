from __future__ import annotations
from typing import Any, Optional, Callable
from contextlib import closing as contextlib_closing
from collections import defaultdict
import discord
import logging
from discord import Member as DiscordMember
from discord.ext import commands, tasks
from bot.common import FeatureCog, GuildBot, extension_setup
import bot.exceptions as exceptions
from bot.subscribable import SubscribableEvent
from .group import XPCommandGroup as XPCommandGroupCog
import sqlite3
from enum import Enum
from math import exp, log, floor


def SafeCursor(conn: sqlite3.Connection) -> contextlib_closing[sqlite3.Cursor]:
    return contextlib_closing(conn.cursor())


class ExperienceQuantityType(Enum):
    level = 1
    xp = 2


class ExperienceMember(discord.Member):
    __slots__ = (
        "xp_handler",
        "level",
        "xp_quantity",
        "rank"
    )

    def __init__(self, handler: XPHandling, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.xp_handler = handler
        self.level: int
        self.xp_quantity: float
        self.rank: int

    @classmethod
    def _copy(cls, member: ExperienceMember) -> ExperienceMember:
        self = super()._copy(member)
        self.xp_handler = member.xp_handler
        self.level = member.level
        self.xp_quantity = member.xp_quantity
        self.rank = member.rank

        return self

    @classmethod
    def cast_from_member(cls, member: discord.Member, handler: XPHandling) -> ExperienceMember:
        casted_obj = super()._copy(member)
        casted_obj.fill_experience_slots(handler)

        return casted_obj

    def fill_experience_slots(self, handler: XPHandling):
        self.xp_handler = handler

    def get_experience_above_level(self) -> float:
        """Query how much XP the user has above their current level."""
        return self.xp_handler.level_curve.get_experience_above_level(self.xp_quantity, self.level)

    def get_current_level_requirement(self) -> float:
        """Query how much total XP the user needed to level up to their current level."""
        return self.xp_handler.level_curve.get_level_experience_requirement(self.level)

    def get_next_level_requirement(self) -> float:
        """Query how much total XP the user will need to level up to their next level."""
        return self.xp_handler.level_curve.get_level_experience_requirement(self.level + 1)

    def get_level_progress(self) -> float:
        """Query the user's progress from their current to their next level."""
        return self.xp_handler.level_curve.get_level_progress_from_experience(self.xp_quantity)

    def get_level_float_from_xp_quantity(self) -> float:
        return self.xp_handler.level_curve.get_level_from_experience(self.xp_quantity)


class XPHandling(FeatureCog):
    dependencies = ["bot.cogs.xp.group"]
    features = ["bot.cogs.xp.listeners",
                "bot.cogs.xp.voice",
                "bot.cogs.xp.commands.autorole",
                "bot.cogs.xp.commands.announce",
                "bot.cogs.xp.commands.curve",
                "bot.cogs.xp.commands.leaderboard",
                "bot.cogs.xp.commands.reward",
                "bot.cogs.xp.commands.rolescalar",
                "bot.cogs.xp.commands.set",
                "bot.cogs.xp.commands.show"
                ]

    data_directory = "data/xp/"
    database_filename = "experience.sql"

    defaults = {"level_curve_scalar": 100,
                "level_curve_power": 2,
                "reward_xp_message": 50,
                "reward_xp_reply": 50,
                "reward_xp_react": 35,
                "reward_xp_voice": 15,
                "xp_gain_cap": 150}

    class SQLMethods:
        rank_field = "ROW_NUMBER() OVER(ORDER BY experience DESC) as rank"

        def __init__(self, guild_id: int):
            self.experience_schema: str = f"Guild{guild_id}"
            self.roles_schema: str = f"Roles{guild_id}"
            self.role_scalars_schema: str = f"Scalars{guild_id}"

        @staticmethod
        def generic_delete(table, condition):
            return f"DELETE FROM {table} WHERE {condition}"

        @staticmethod
        def generic_update(table, fields_to_set, condition):
            return f"UPDATE {table} SET {', '.join([field_name + '=?' for field_name in fields_to_set])} WHERE {condition}"

        @staticmethod
        def generic_select(table, fields_to_select, condition):
            return f"SELECT {', '.join(fields_to_select)} FROM {table} WHERE {condition}"

        @staticmethod
        def select_all(table):
            return f"SELECT * FROM {table}"

        @staticmethod
        def create_guild_data_schema():
            return f"""CREATE TABLE IF NOT EXISTS GuildData (guildid INTEGER PRIMARY KEY, 
                announce_level_up_channel_id INTEGER, 
                curve_scalar REAL, 
                curve_power REAL, 
                reward_voice REAL, 
                reward_message REAL, 
                reward_reply REAL, 
                reward_react REAL, 
                xp_gain_cap REAL);"""

        def create_experience_schema(self):
            return f"CREATE TABLE IF NOT EXISTS {self.experience_schema} (userid INTEGER PRIMARY KEY, experience REAL, experience_level INTEGER);"

        def create_roles_schema(self):
            return f"CREATE TABLE IF NOT EXISTS {self.roles_schema} (roleid INTEGER PRIMARY KEY, assign_at INTEGER, remove_at INTEGER);"

        def create_scalars_schema(self):
            return f"CREATE TABLE IF NOT EXISTS {self.role_scalars_schema} (roleid INTEGER PRIMARY KEY, scalar REAL, priority INTEGER);"

        def experience_schema_with_rank_subquery(self):
            return f"(SELECT userid, experience, experience_level, {self.rank_field} from {self.experience_schema})"

        def select_member_by_userid(self, field_names):
            return self.generic_select(self.experience_schema_with_rank_subquery(), field_names, "userid=?")

        def select_many_members_by_userid(self, field_names, number_of_user_ids):
            return self.generic_select(self.experience_schema_with_rank_subquery(), field_names,
                                       f"userid IN ({', '.join(['?'] * number_of_user_ids)})")

        def select_many_members_by_condition(self, field_names, condition):
            return self.generic_select(self.experience_schema_with_rank_subquery(), field_names, condition)

        def update_by_userid(self, field_names: [str]) -> str:
            return f"UPDATE {self.experience_schema} SET {', '.join([field_name + '=?' for field_name in field_names])} WHERE userid=? LIMIT 1"

        def insert_userid(self):
            return f"INSERT INTO {self.experience_schema} (userid, experience, experience_level) VALUES (?, 0, 0)"

        def insert_auto_role(self):
            return f"INSERT INTO {self.roles_schema} (roleid, assign_at, remove_at) VALUES (?, ?, ?)"

        def insert_role_scalar(self):
            return f"INSERT INTO {self.role_scalars_schema} (roleid, scalar, priority) VALUES (?, ?, ?)"

        def delete_auto_role(self):
            return self.generic_delete(self.roles_schema, "roleid=?")

        def delete_role_scalar(self):
            return self.generic_delete(self.role_scalars_schema, "roleid=?")

        def update_auto_role(self, changed_fields):
            return self.generic_update(self.roles_schema, changed_fields, "roleid=?")

        def update_role_scalar(self, changed_fields):
            return self.generic_update(self.role_scalars_schema, changed_fields, "roleid=?")

        def select_auto_roles(self, fields_to_select):
            return f"SELECT {', '.join(fields_to_select)} FROM {self.roles_schema}"

        def select_role_scalars(self, fields_to_select):
            return f"SELECT {', '.join(fields_to_select)} FROM {self.role_scalars_schema}"

        def select_auto_role_by_id(self, fields_to_select):
            return f"{self.select_auto_roles(fields_to_select)} WHERE roleid=?"

        def select_role_scalar_by_id(self, fields_to_select):
            return f"{self.select_role_scalars(fields_to_select)} WHERE roleid=?"

        def select_auto_roles_by_condition(self, fields_to_select, condition):
            return f"{self.select_auto_roles(fields_to_select)} WHERE {condition}"

    class XPCurve:

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

        def __init__(self, scalar: float, power: float):
            self.scalar = scalar
            self.power = power

        def get_floored_level_from_experience(self, xp_quantity: float) -> int:
            """Query what experience level (rounded down) an arbitrary user would be based on an XP quantity."""
            return floor(self.get_level_from_experience(xp_quantity))

        def get_level_experience_requirement(self, level: float) -> float:
            """Query what total XP quantity is required for an experience level."""
            return self.scalar * level ** self.power

        def get_experience_above_level(self, xp_quantity: float, level: int) -> float:
            """Query how much XP is 'overflow' above a certain level's requirement."""
            return xp_quantity - self.get_level_experience_requirement(level)

        def get_relative_level_experience_requirement(self, level: int) -> float:
            """Query what XP quantity is required to level up from the previous level, to the level specified."""
            return self.get_level_experience_requirement(level) - self.get_level_experience_requirement(level - 1)

        def get_level_progress_from_experience(self, xp_quantity: float) -> float:
            """Query progress from the previous to the next level based upon an XP quantity."""
            from_level = self.get_floored_level_from_experience(xp_quantity)
            return self.get_experience_above_level(xp_quantity,
                                                   from_level) / self.get_relative_level_experience_requirement(
                from_level + 1)

        def get_level_from_experience(self, xp_quantity: float) -> float:
            """Query the exact experience level (as float) of an arbitrary user based on XP quantity."""
            try:
                return self.Math.nth_root_of_x(self.power, (xp_quantity / self.scalar))
            except ValueError:
                return 0

    def __init__(self, bot: GuildBot):
        self.bot = bot

        self.database_path = self.data_directory + self.database_filename

        self.database_connection: Optional[sqlite3.Connection] = None
        self.sql_commands = self.SQLMethods(self.bot.guild.id)

        self.level_curve_scalar: float = None
        self.level_curve_power: float = None
        self.reward_xp_message = None
        self.reward_xp_reply = None
        self.reward_xp_react = None
        self.reward_xp_voice = None
        self.xp_gain_cap = None

        self.announce_level_up_channel_id: Optional[int] = None

        self.apply_defaults()
        self.level_curve = self.XPCurve(self.level_curve_scalar, self.level_curve_power)

        self.level_up_event = SubscribableEvent()
        self.level_changed_event = SubscribableEvent()
        self._xp_additions = defaultdict(lambda: 0)

    def cog_load(self) -> None:
        self.database_connection = sqlite3.connect(self.database_path)
        self.database_connection.row_factory = sqlite3.Row

        with self.database_connection, SafeCursor(self.database_connection) as cursor:
            cursor.execute(self.sql_commands.create_guild_data_schema())
            cursor.execute(f"INSERT OR IGNORE INTO GuildData (guildid) VALUES (?)", (self.bot.guild.id,))
            cursor.execute(self.sql_commands.create_experience_schema())
            cursor.execute(self.sql_commands.create_roles_schema())
            cursor.execute(self.sql_commands.create_scalars_schema())

        self.load_all_guild_data()

        self.do_experience_additions.start()

    async def cog_unload(self) -> None:
        self.save_all_guild_data()
        self.do_experience_additions.cancel()
        await self.do_experience_additions()
        self.database_connection.close()

    def save_all_guild_data(self):
        with self.database_connection, SafeCursor(self.database_connection) as cursor:
            cursor.execute(
                f"UPDATE GuildData SET announce_level_up_channel_id=?, curve_scalar=?, curve_power=?, reward_voice=?, reward_message=?, reward_reply=?, reward_react=?, xp_gain_cap=? WHERE guildid=?",
                (self.announce_level_up_channel_id, self.level_curve_scalar, self.level_curve_power,
                 self.reward_xp_voice, self.reward_xp_message, self.reward_xp_reply, self.reward_xp_react,
                 self.xp_gain_cap, self.bot.guild.id,))

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

        self.announce_level_up_channel_id = guild_data["announce_level_up_channel_id"]

        self.apply_defaults_if_none()

        self.level_curve = self.XPCurve(self.level_curve_scalar, self.level_curve_power)

    def apply_defaults(self, when: Optional[Callable[[str], bool]] = lambda attr_name: True):
        for attr_name, default_value in self.defaults.items():
            if not when(attr_name):
                continue
            self.__setattr__(attr_name, default_value)

    def apply_defaults_if_none(self):
        self.apply_defaults(lambda attr_name: self.__getattribute__(attr_name) is None)

    def set_xp_reward_for_action(self, action_name: str, reward: float):
        attribute_name = "reward_xp_" + action_name
        self.__setattr__(attribute_name, reward)
        self.save_all_guild_data()

    def set_xp_gain_cap(self, cap: float):
        self.xp_gain_cap = cap
        self.save_all_guild_data()

    def basic_database_query(self, query: str, fields: Optional[tuple[Any, ...]] = tuple(),
                             quantity: Optional[int] = 1) -> [sqlite3.Row] or sqlite3.Row or None:
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

    def database_get_by_userid(self, user_id: int, field_names: [str]) -> Optional[sqlite3.Row]:
        """Query the experience database for a user's fields.

        Parameters
        ----------
        user_id : int
            Discord User ID to lookup in the database.
        field_names : [str]
            Array of field names to query.
        """
        return self.basic_database_query(self.sql_commands.select_member_by_userid(field_names), (user_id,), 1)

    def database_get_many_by_userid(self, user_ids: [int], field_names: [str]) -> [sqlite3.Row]:
        """Query the experience database for some users' fields.

        Parameters
        ----------
        user_ids : [int]
            Discord User ID array to lookup in the database.
        field_names : [str]
            Array of field names to query.
        """
        return self.basic_database_query(self.sql_commands.select_many_members_by_userid(field_names, len(user_ids)),
                                         tuple(user_ids), -1)

    def basic_database_execute(self, command: str, fields: tuple[Any, ...] = tuple()):
        with self.database_connection, SafeCursor(self.database_connection) as cursor:
            logging.debug(f"SQL EXECUTE {command}")
            cursor.execute(command, fields)

    def basic_database_execute_many(self, command: str, fields_array: [tuple[Any, ...]]):
        if len(fields_array) == 0:
            return

        with self.database_connection, SafeCursor(self.database_connection) as cursor:
            logging.debug(f"SQL EXECUTEMANY {command} ... {fields_array}")
            cursor.executemany(command, fields_array)

    def database_update_by_userid(self, user_id: int, fields: dict[str, Any]):
        self.basic_database_execute(self.sql_commands.update_by_userid(fields.keys()),
                                    tuple(fields.values()) + (user_id,))

    def database_update_many_by_userid(self, data: dict[int, tuple[Any, ...]], field_names: tuple[str, ...]):
        self.basic_database_execute_many(self.sql_commands.update_by_userid(field_names),
                                         tuple([values + (user_id,) for user_id, values in data.items()]))

    def database_insert_userid(self, user_id: int):
        self.basic_database_execute(self.sql_commands.insert_userid(), (user_id,))

    def database_insert_many_userids(self, user_ids: [int]):
        self.basic_database_execute_many(self.sql_commands.insert_userid(), tuple([(user_id,) for user_id in user_ids]))

    def database_insert_autorole(self, role_id: int, assign_at: int, remove_at: int):
        self.basic_database_execute(self.sql_commands.insert_auto_role(), (role_id, assign_at, remove_at))

    def database_modify_autorole(self, role_id: int, assign_at: Optional[int], remove_at: Optional[int]):
        fields = {}
        if assign_at is not None:
            fields["assign_at"] = assign_at
        if remove_at is not None:
            fields["remove_at"] = remove_at
        self.basic_database_execute(self.sql_commands.update_auto_role(fields.keys()),
                                    tuple(fields.values()) + (role_id,))

    def database_delete_autorole(self, role_id: int):
        self.basic_database_execute(self.sql_commands.delete_auto_role(), (role_id,))

    def database_autorole_exists(self, role_id: int):
        database_entry = self.basic_database_query(self.sql_commands.select_auto_role_by_id(("roleid",)), (role_id,))
        return database_entry is not None

    def create_autorole(self, role: discord.Role, assign_at: int, remove_at: int):
        try:
            self.database_insert_autorole(role.id, assign_at, remove_at)
        except sqlite3.IntegrityError:
            raise exceptions.ConflictError(f"{role.mention} is already a level-assigned role.")

    def modify_autorole(self, role: discord.Role, assign_at: Optional[int], remove_at: Optional[int]):
        if not self.database_autorole_exists(role.id):
            raise exceptions.NotFoundError(f"{role.mention} is not a level-assigned role.")
        self.database_modify_autorole(role.id, assign_at, remove_at)

    def remove_autorole(self, role: discord.Role):
        if not self.database_autorole_exists(role.id):
            raise exceptions.NotFoundError(f"{role.mention} is not a level-assigned role.")
        self.database_delete_autorole(role.id)

    def database_insert_role_scalar(self, role_id: int, scalar: float, priority: int):
        self.basic_database_execute(self.sql_commands.insert_role_scalar(), (role_id, scalar, priority))

    def database_modify_role_scalar(self, role_id: int, scalar: Optional[float], priority: Optional[int]):
        fields = {}
        if scalar is not None:
            fields["scalar"] = scalar
        if priority is not None:
            fields["priority"] = priority
        self.basic_database_execute(self.sql_commands.update_role_scalar(fields.keys()),
                                    tuple(fields.values()) + (role_id,))

    def database_delete_role_scalar(self, role_id: int):
        self.basic_database_execute(self.sql_commands.delete_role_scalar(), (role_id,))

    def database_role_scalar_exists(self, role_id: int):
        database_entry = self.basic_database_query(self.sql_commands.select_role_scalar_by_id(("roleid",)), (role_id,))
        return database_entry is not None

    def assign_role_scalar(self, role: discord.Role, scalar: float, priority: int):
        try:
            self.database_insert_role_scalar(role.id, scalar, priority)
        except sqlite3.IntegrityError:
            raise exceptions.ConflictError(f"{role.mention} is already assigned a scalar.")

    def modify_role_scalar(self, role: discord.Role, scalar: Optional[float], priority: Optional[int]):
        if not self.database_role_scalar_exists(role.id):
            raise exceptions.NotFoundError(f"{role.mention} does not have a role scalar assigned.")
        self.database_modify_role_scalar(role.id, scalar, priority)

    def remove_role_scalar(self, role: discord.Role):
        if not self.database_role_scalar_exists(role.id):
            raise exceptions.NotFoundError(f"{role.mention} does not have a role scalar assigned.")
        self.database_delete_role_scalar(role.id)

    def _adjust_xp_quantities_to_curve(self, curve: XPCurve):
        with SafeCursor(self.database_connection) as cursor:
            cursor.execute(f"SELECT userid, experience FROM {self.sql_commands.experience_schema}")
            update_by_userid_command = self.sql_commands.update_by_userid(("experience",))
            while True:
                experience_data = cursor.fetchone()
                if experience_data is None:
                    break

                level = self.level_curve.get_level_from_experience(experience_data["experience"])
                new_experience = curve.get_level_experience_requirement(level)

                self.basic_database_execute(update_by_userid_command, (new_experience, experience_data["userid"]))

    def _adjust_xp_levels_to_curve(self, curve: XPCurve):
        with SafeCursor(self.database_connection) as cursor:
            cursor.execute(f"SELECT userid, experience from {self.sql_commands.experience_schema}")
            update_by_userid_command = self.sql_commands.update_by_userid(("experience_level",))
            while True:
                experience_data = cursor.fetchone()
                if experience_data is None:
                    break

                new_level = curve.get_floored_level_from_experience(experience_data["experience"])

                self.basic_database_execute(update_by_userid_command, (new_level, experience_data["userid"]))
                self.bot.loop.create_task(self.on_level_changed(experience_data["userid"], new_level))

    def update_level_curve(self, scalar: Optional[float], power: Optional[float], maintain_level: bool):
        """Update the level XP requirement curve.
        Level XP Requirement = scalar * Level ** power

        Parameters
        ----------
        scalar : optional[float]
            The scalar in the requirement curve expression.
        power : Optional[float]
            The power in the requirement curve expression.
        maintain_level : bool
            Whether to change users' XP quantities to keep their levels the same.
            If this is false, users' levels will be changed instead.
        """
        if scalar is None:
            scalar = self.level_curve_scalar
        if power is None:
            power = self.level_curve_power
        if scalar == self.level_curve_scalar and power == self.level_curve_power:
            return

        new_curve = self.XPCurve(scalar, power)

        if maintain_level:
            self._adjust_xp_quantities_to_curve(new_curve)
        else:
            self._adjust_xp_levels_to_curve(new_curve)

        self.level_curve = new_curve
        self.level_curve_scalar = scalar
        self.level_curve_power = power
        self.save_all_guild_data()

    def _execute_add_experience(self, user_id: int, xp_quantity: float):
        """Add experience to a single user, check for level up, and handle accordingly.

        Parameters
        ----------
        user_id : int
            The user ID to add xp to.
        xp_quantity : float
            The xp quantity to attribute.
        """
        current_data = self.database_get_by_userid(user_id, ("experience", "experience_level"))

        if current_data is None:
            self.database_insert_userid(user_id)
            old_experience, old_level = 0, 0
        else:
            old_experience, old_level = current_data["experience"], current_data["experience_level"]
        new_experience = old_experience + min(xp_quantity, self.xp_gain_cap)
        new_level = self.level_curve.get_floored_level_from_experience(new_experience)

        self.database_update_by_userid(user_id, {"experience": new_experience, "experience_level": new_level})

        if new_level != old_level:
            self.create_level_up_task(user_id, new_level)

    async def _execute_add_experience_to_many(self, xp_additions: dict[int, float]):
        """Add experience to a bunch of users, check for level ups, and handle accordingly.

        Parameters
        ----------
        xp_additions : dict[int, float]
            A dictionary of user_id to xp_quantity to add.
        """
        current_data = self.database_get_many_by_userid(xp_additions.keys(),
                                                        ("userid", "experience", "experience_level"))

        to_write = {}
        to_insert = []
        with SafeCursor(self.database_connection) as cursor:
            cursor.execute(f"SELECT * FROM {self.sql_commands.role_scalars_schema}")
            scalar_roles_data = cursor.fetchall()
            scalar_roles = {data["roleid"]: (data["scalar"], data["priority"]) for data in scalar_roles_data}
            del scalar_roles_data

        async def process_addition(user_id: int, old_experience: float, old_level):
            to_add_experience = min(xp_additions[user_id], self.xp_gain_cap)
            try:
                member = await self.bot.lookup_member(user_id)
            except discord.errors.NotFound:
                logging.error(f"Failed to add some XP to user with id {user_id} in guild {self.bot.guild.id} as they could not be found.")
                return
            except Exception as error:
                logging.error(f"Failed to add some XP to user with id {user_id} in guild {self.bot.guild.id} for reason: {error}")
                return

            this_member_scalars = {}
            for role in member.roles:
                try:
                    this_role_scalar_data = scalar_roles[role.id]
                    this_member_scalars[this_role_scalar_data[1]] = this_role_scalar_data[0]
                except KeyError:
                    pass

            if this_member_scalars:
                experience_scalar = this_member_scalars[max(this_member_scalars.keys())]
            else:
                experience_scalar = 1
            del this_member_scalars
            new_experience = old_experience + (experience_scalar * to_add_experience)
            new_level = self.level_curve.get_floored_level_from_experience(new_experience)

            to_write[user_id] = (new_experience, new_level)

            if new_level != old_level:
                self.create_level_up_task(user_id, new_level)

        for row in current_data:
            await process_addition(row["userid"], row["experience"], row["experience_level"])
            del xp_additions[row["userid"]]

        for user_id, xp_to_add in xp_additions.items():
            to_insert.append(user_id)
            await process_addition(user_id, 0, 0)

        self.database_insert_many_userids(to_insert)
        self.database_update_many_by_userid(to_write, ("experience", "experience_level"))
        del to_insert
        del to_write

    def add_experience_from_action(self, user_id: int, xp_quantity: float):
        self._xp_additions[user_id] += xp_quantity

    def _set_experience(self, user_id: int, xp_quantity: float):
        current_data = self.database_get_by_userid(user_id, ("experience", "experience_level"))

        if current_data is None:
            self.database_insert_userid(user_id)

        new_level = self.level_curve.get_floored_level_from_experience(xp_quantity)
        self.database_update_by_userid(user_id, {"experience": xp_quantity, "experience_level": new_level})
        self.bot.loop.create_task(self.on_level_changed(user_id, new_level))

    def _set_experience_level(self, user_id: int, xp_level: float):
        new_xp_quantity = self.level_curve.get_level_experience_requirement(xp_level)
        self._set_experience(user_id, new_xp_quantity)

    def set_member_experience(self, member: discord.Member, coefficient: float, set_type: ExperienceQuantityType):
        """Method used for setting a member's experience quantity via a command."""
        if coefficient < 0:
            raise exceptions.ValueErrorWithMessage("Coefficient must be positive.")
        if coefficient == 0:
            set_type = ExperienceQuantityType.xp

        if set_type.value == ExperienceQuantityType.xp.value:
            self._set_experience(member.id, coefficient)
        elif set_type.value == ExperienceQuantityType.level.value:
            self._set_experience_level(member.id, coefficient)
        else:
            raise ValueError

    def _add_experience(self, experience_member: ExperienceMember, xp_quantity: float):
        new_xp_quantity = experience_member.xp_quantity + xp_quantity
        self._set_experience(experience_member.id, new_xp_quantity)

    def _add_experience_levels(self, experience_member: ExperienceMember, xp_levels: float):
        new_xp_level = experience_member.get_level_float_from_xp_quantity() + xp_levels
        new_xp_quantity = int(self.level_curve.get_level_experience_requirement(new_xp_level)) + 1
        self._set_experience(experience_member.id, new_xp_quantity)

    def add_member_experience(self, member: discord.Member, coefficient: float, add_type: ExperienceQuantityType):
        """Method used for adding experience to a member via a command."""
        if coefficient == 0:
            return

        experience_member = self.convert_to_experience_member(member)

        if add_type.value == ExperienceQuantityType.xp.value:
            self._add_experience(experience_member, coefficient)
        elif add_type.value == ExperienceQuantityType.level.value:
            self._add_experience_levels(experience_member, coefficient)
        else:
            raise ValueError

    def get_member_experience_info(self, user_id: int) -> sqlite3.Row or dict:
        result = self.database_get_by_userid(user_id, ("experience", "experience_level", "rank"))

        if result is None:
            return {"experience": 0, "experience_level": 0, "rank": "N/A"}

        return result

    async def get_experience_member(self, user_id: int):
        member = await self.bot.lookup_member(user_id)
        if member is None:
            return None
        return self.convert_to_experience_member(member)

    def convert_to_experience_member(self, member: DiscordMember):
        experience_info = self.get_member_experience_info(member.id)

        experience_member = ExperienceMember.cast_from_member(member, self)
        experience_member.level = experience_info["experience_level"]
        experience_member.xp_quantity = experience_info["experience"]
        experience_member.rank = experience_info["rank"]

        return experience_member

    @staticmethod
    def format_xp_quantity(xp_quantity):
        if xp_quantity < 0:
            return "<0"
        if xp_quantity < 1_000:
            return round(xp_quantity)
        if xp_quantity < 1_000_000:
            return f"{round(xp_quantity / 1_000, 1)}K"
        return f"{round(xp_quantity / 1_000_000, 1)}M"

    def create_level_up_task(self, user_id: int, new_level: int):
        self.bot.loop.create_task(self.on_level_up(user_id, new_level))

    async def on_level_changed(self, user_id: int, new_level: int) -> None:
        member = await(self.get_experience_member(user_id))
        await self.level_changed_event.fire(member, new_level)

    async def on_level_up(self, user_id: int, new_level: int) -> None:
        member = await self.get_experience_member(user_id)
        await self.level_up_event.fire(member, new_level)

    async def do_experience_additions_for_user_id(self, user_id: int):
        to_add = self._xp_additions.pop(user_id)
        if to_add > 0:
            self._execute_add_experience(user_id, to_add)

    @tasks.loop(seconds=60.0)
    async def do_experience_additions(self):
        cached_xp_additions = self._xp_additions.copy()
        self._xp_additions.clear()
        await self._execute_add_experience_to_many(cached_xp_additions)

    @do_experience_additions.before_loop
    async def before_do_experience_additions(self):
        await self.bot.wait_until_ready()


class XPCog(commands.Cog):
    def __init__(self, bot: GuildBot):
        self.bot = bot
        self.handler: Optional[XPHandling] = None
        self.command_group_cog: Optional[XPCommandGroupCog] = None

    async def cog_load(self) -> None:
        self.handler = self.bot.get_cog("XPHandling")
        self.command_group_cog = self.bot.get_cog("XPCommandGroup")


class XPCommandCog(XPCog):
    async def cog_load(self) -> None:
        await super().cog_load()
        self.create_groups()
        self.register_commands()

    def create_groups(self) -> None:
        pass

    def register_commands(self) -> None:
        pass


setup = extension_setup(XPHandling)
