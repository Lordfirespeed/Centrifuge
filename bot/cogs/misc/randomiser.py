import discord
from discord import app_commands
from discord.ext import commands
from bot.main import extension_setup
from bot.exceptions import ContextError, standard_error_handling
from typing import Optional, Any
from random import choice as random_choice


class RandomiserCommands(commands.Cog, name="Randomiser Commands"):
    def __init__(self, bot):
        self.bot = bot
        self.command_group: Optional[app_commands.Group] = None

    async def cog_load(self) -> None:
        self.command_group = app_commands.Group(
            name="random",
            description="Commands relating to picking random players",
            guild_only=True
        )

        self.__cog_app_commands__.append(self.command_group)

        self.register_commands()

    @staticmethod
    async def send_response(interaction: discord.Interaction, choices: [Any]) -> None:
        selected = random_choice(choices)
        await interaction.response.send_message(f"{selected.mention}, you have been selected!")

    def register_commands(self) -> None:
        @self.command_group.command(name="party")
        @standard_error_handling
        async def party(interaction: discord.Interaction):
            """Pick a random member from your voice channel.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            """

            if interaction.user.voice is None or interaction.user.voice.channel is None:
                raise ContextError("You're not in a voice channel!")

            if interaction.user.voice.channel.guild.id != interaction.guild_id:
                raise ContextError("You're in a voice channel, but not in this server!")

            voice_channel = interaction.user.voice.channel
            await self.send_response(interaction, voice_channel.members)

        # @self.command_group.command(name="list")
        # @standard_error_handling
        # async def list_of_members(interaction: discord.Interaction,
        #                           members: [discord.Member]):
        #     """Pick a random member from a specified list.
        #
        #     Parameters
        #     ----------
        #     interaction : discord.Interaction
        #         The interaction object.
        #     members: [discord.Member]
        #         List of members to choose from.
        #     """
        #
        #     self.send_response(interaction, members)


setup = extension_setup(RandomiserCommands)
