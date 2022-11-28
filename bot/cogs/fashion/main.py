from typing import Optional
import discord
import logging
from discord.ext import commands, tasks
from bot.main import GuildBot, extension_setup, FeatureCog
import bot.exceptions as exceptions
from bot.cogs.fashion.group import FashionCommandGroup as FashionCommandGroupCog
from bot.cogs.fashion.database import FashionDatabaseAccessor


class FashionHandler(FeatureCog):
    __slots__ = ["database"]

    def __init__(self, bot: GuildBot):
        super().__init__(bot)
        self.database = FashionDatabaseAccessor()


class FashionCog(FeatureCog):
    def __init__(self, bot: GuildBot):
        super().__init__(bot)
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
