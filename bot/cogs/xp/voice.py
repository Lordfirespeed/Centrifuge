import discord
from discord.ext import commands
from bot.main import GuildBot, extension_setup


class VoiceXP(commands.Cog):
    def __init__(self, bot: GuildBot):
        self.bot = bot


setup = extension_setup(VoiceXP)
