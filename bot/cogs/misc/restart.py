import os
import discord
from discord import app_commands
from discord.ext import commands
from bot.common import extension_setup
from asyncio import Lock


class RestartCommand(commands.Cog, name="Restart Command"):
    def __init__(self, bot):
        self.bot = bot
        self.restarting = Lock()

    @app_commands.command(name="restart")
    @app_commands.default_permissions(administrator=True)
    async def _restart(self, interaction: discord.Interaction):
        """Restart the bot. Locked to developer.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object.
        """
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(f"You don't have permission to use this.", ephemeral=True)
            return
        if self.restarting.locked():
            await interaction.response.send_message(f"Already restarting.", ephemeral=True)
            return

        async with self.restarting:
            path_to_start = os.path.join(os.getcwd(), "start_bot.sh")
            if not (os.path.exists(path_to_start) and os.path.isfile(path_to_start)):
                await interaction.response.send_message(f"Failed to find bot start script.", ephemeral=True)
                return

            await interaction.response.send_message(f"Restarting...", ephemeral=True)
            os.chdir(os.path.join(os.path.dirname(__file__), ".."))
            os.execv(path_to_start, [" "])
            await self.bot.close()


setup = extension_setup(RestartCommand)
