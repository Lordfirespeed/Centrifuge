import discord
from discord import app_commands
from discord.ext import commands
from bot.main import extension_setup


class BadgerCommand(commands.Cog, name="Badger Command"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="badger")
    async def badger(self, interaction: discord.Interaction):
        """Tells Badger he is cool.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        await interaction.response.send_message(content=f"Badger is cool.")


setup = extension_setup(BadgerCommand)
