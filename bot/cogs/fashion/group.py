from typing import Optional

from discord import app_commands
from discord.ext import commands
from bot.main import GuildBot, extension_setup


class FashionCommandGroup(commands.Cog):
    __slots__ = ["bot", "fashion_commands"]

    def __init__(self, bot: GuildBot):
        self.bot = bot

        self.fashion_commands: Optional[app_commands.Group] = None

    def cog_load(self) -> None:
        self.create_command_groups()

    def create_command_groups(self) -> None:
        self.fashion_commands = app_commands.Group(name="xp",
                                                   description="Destiny Fashion contest commands",
                                                   guild_only=True)

        self.__cog_app_commands__.append(self.fashion_commands)


setup = extension_setup(FashionCommandGroup)
