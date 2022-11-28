from typing import Optional
import discord
import logging
from discord.ext import commands, tasks
from bot.main import GuildBot, extension_setup
import bot.exceptions as exceptions
from bot.cogs.fashion.group import FashionCommandGroup as FashionCommandGroupCog
from bot.cogs.fashion.database import FashionDatabaseAccessor


class FashionHandler(commands.Cog):
    __slots__ = ["database"]

    def __init__(self):
        self.database = FashionDatabaseAccessor()


class FashionCog(commands.Cog):
    def __init__(self, bot: GuildBot):
        self.bot = bot
        self.handler: Optional[FashionCog] = None
        self.command_group_cog: Optional[FashionCommandGroupCog] = None

    async def cog_load(self) -> None:
        self.handler = self.bot.get_cog("FashionHandler")
        self.command_group_cog = self.bot.get_cog("FashionCommandGroup")


class FashionCommandCog(FashionCog):
    async def cog_load(self) -> None:
        await super().cog_load()
        self.create_groups()
        self.register_commands()

    def create_groups(self) -> None:
        pass

    def register_commands(self) -> None:
        pass


setup = extension_setup(FashionHandler)
