from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from bot.main import GuildBot, extension_setup


class XPCommandGroup(commands.Cog):
    __slots__ = ["bot", "xp_commands", "admin_xp_commands"]

    def __init__(self, bot: GuildBot):
        self.bot = bot

        self.xp_commands: Optional[app_commands.Group] = None
        self.admin_xp_commands: Optional[app_commands.Group] = None

    def cog_load(self) -> None:
        self.create_command_groups()

    def create_command_groups(self) -> None:
        self.xp_commands = app_commands.Group(name="xp",
                                              description="Member xp commands.",
                                              guild_only=True)

        self.admin_xp_commands = app_commands.Group(name="xp-admin",
                                                    description="Priveleged xp commands.",
                                                    default_permissions=discord.Permissions(manage_guild=True),
                                                    guild_only=True)

        self.__cog_app_commands__.append(self.xp_commands)
        self.__cog_app_commands__.append(self.admin_xp_commands)


setup = extension_setup(XPCommandGroup)
