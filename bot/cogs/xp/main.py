from discord.ext import commands
from bot.main import GuildBot, basic_extension_setup
import sqlite3
import json


class XPHandling(commands.Cog):
    data_directory = "bot/data/xp/"
    database_filename = "experience.sql"
    rewards_filename = "rewards.json"

    def __init__(self, bot: GuildBot):
        self.bot = bot

    async def cog_load(self) -> None:
        pass

    def add_experience(self, user_id: int, xp_quantity: float):
        set_to = self.get_experience(user_id) + xp_quantity
        self.set_experience(user_id, set_to)

    def set_experience(self, user_id: int, xp_quantity: float):
        pass

    def get_experience(self, user_id: int) -> float:
        pass


class XPCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.handler: XPHandling = None
        self.command_group_cog: commands.Cog = None

    def cog_load(self) -> None:
        self.handler = self.bot.get_cog("XPHandling")
        self.command_group_cog = self.bot.get_cog("XPCommandGroup")


setup = basic_extension_setup(XPHandling)
