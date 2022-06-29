import discord
from discord.ext import commands
from bot.main import GuildBot, basic_extension_setup


class XPListeners(commands.Cog):
    def __init__(self, bot: GuildBot):
        self.bot = bot


setup = basic_extension_setup(XPListeners)
