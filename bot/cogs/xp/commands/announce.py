from typing import Optional
import discord
from discord import app_commands
from bot.common import extension_setup
from bot.exceptions import standard_error_handling
from bot.cogs.xp.main import XPCommandCog, ExperienceMember
from bot.cogs.xp.card_generator import UserDisplayCard, UserDisplayCardType


class AnnounceLevelUps(XPCommandCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.announce_command_group: Optional[app_commands.Group] = None
        self.level_up_channel: Optional[discord.abc.MessageableChannel] = None

    async def cog_load(self) -> None:
        await super().cog_load()
        try:
            self.level_up_channel = await self.bot.lookup_channel(self.handler.announce_level_up_channel_id)
        except TypeError:
            self.level_up_channel = None
        self.handler.level_up_event.subscribe(self.level_up_announcement)

    def create_groups(self) -> None:
        self.announce_command_group = app_commands.Group(name="announce",
                                                         description="Commands relating to level-up announcements.",
                                                         guild_only=True,
                                                         parent=self.command_group_cog.admin_xp_commands)

    def register_commands(self) -> None:
        @self.announce_command_group.command(name="channel")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def set_announcement_channel(interaction: discord.Interaction,
                                           channel: discord.TextChannel):
            """Select a channel to send level-up announcements to.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            channel : discord.abc.MessageableChannel
                The channel that level-up announcements will be sent to."""

            if self.level_up_channel == channel:
                await interaction.response.send_message(f"Level-up announcements are already being posted to {channel.mention}.")
                return

            previous_channel = self.level_up_channel
            self.set_level_up_channel(channel)

            if previous_channel is None:
                await interaction.response.send_message(f"Enabled level-up announcements, will post to {channel.mention}.")
                return

            await interaction.response.send_message(f"Moved level-up announcements from {previous_channel.mention} to {channel.mention}.")

        @self.announce_command_group.command(name="disable")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def disable_announcements(interaction: discord.Interaction):
            """Disable level-up announcements.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object."""

            if self.level_up_channel is None:
                await interaction.response.send_message(f"Level-up announcements are already disabled.")
                return

            self.set_level_up_channel(None)

            await interaction.response.send_message("Level-up announcements have been disabled.")

    def set_level_up_channel(self, channel: Optional[discord.TextChannel]):
        self.level_up_channel = channel
        if channel:
            self.handler.announce_level_up_channel_id = channel.id
        else:
            self.handler.announce_level_up_channel_id = None
        self.handler.save_all_guild_data()

    async def level_up_announcement(self, member: ExperienceMember, leveled_to: int) -> None:
        if not self.level_up_channel:
            return
        member.level = leveled_to
        display_card = UserDisplayCard(member, UserDisplayCardType.LevelUp)
        with display_card.get_png_card() as png_card:
            await self.level_up_channel.send(file=discord.File(png_card.file))


setup = extension_setup(AnnounceLevelUps)
