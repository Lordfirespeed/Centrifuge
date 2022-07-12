import os
import discord
from discord import app_commands
from discord.ext import commands
from bot.main import extension_setup


class RestartCommand(commands.Cog, name="Restart Command"):
    def __init__(self, bot):
        self.bot = bot
        self.restarting = False

    @app_commands.command(name="restart")
    async def _restart(self, interaction: discord.Interaction):
        """Restart the bot. Locked to developer.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(f"You don't have permission to use this.")
            return
        if self.restarting:
            await interaction.response.send_message(f"Already restarting.")
            return

        self.restarting = True
        path_to_start = os.path.join(os.getcwd(), "..", "start_bot.sh")
        if not (os.path.exists(path_to_start) and os.path.isfile(path_to_start)):
            await interaction.response.send_message(f"Failed to find bot start script.")
            return

        await interaction.response.send_message(f"Restarting...")
        await self.bot.close()
        os.chdir(os.path.join(os.path.dirname(__file__), ".."))
        os.execv(path_to_start, [" "])


setup = extension_setup(RestartCommand)
