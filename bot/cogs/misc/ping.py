import discord
from discord import app_commands
from discord.ext import commands
from bot.main import basic_extension_setup


class PingCommand(commands.Cog, name="Ping Command"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping")
    async def ping(self, interaction: discord.Interaction):
        """Checks bot latency.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        await interaction.response.send_message(content=f"Pong! (`{round(self.bot.latency * 1000)}ms`)")


setup = basic_extension_setup(PingCommand)
