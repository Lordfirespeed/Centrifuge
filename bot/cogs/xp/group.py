from typing import Optional
from discord import app_commands
from discord.ext import commands
from bot.main import GuildBot, basic_extension_setup


class XPCommandGroup(commands.Cog):
    def __init__(self, bot: GuildBot):
        self.bot = bot

        self.xp_commands: Optional[app_commands.Group] = None

    def cog_load(self) -> None:
        self.create_command_groups()

    def create_command_groups(self) -> None:
        self.xp_commands = app_commands.Group(name="xp",
                                              description="Member xp commands.",
                                              guild_only=True)

        self.__cog_app_commands__.append(self.xp_commands)


setup = basic_extension_setup(XPCommandGroup)
