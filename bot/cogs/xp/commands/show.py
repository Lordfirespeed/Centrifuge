import discord
from discord import app_commands
from bot.main import extension_setup
from bot.cogs.xp.main import XPCommandCog
from bot.cogs.xp.card_generator import UserDisplayCard, UserDisplayCardType
from bot.exceptions import standard_error_handling


class ShowCommand(XPCommandCog):
    def register_commands(self):
        @self.command_group_cog.xp_commands.command(name="show")
        @standard_error_handling
        async def show(interaction: discord.Interaction,
                       member: discord.Member):
            """Show XP and level of a member.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            member : discord.Member
                The member to query.
            """

            experience_member = self.handler.convert_to_experience_member(member)

            display_card = UserDisplayCard(experience_member, UserDisplayCardType.DisplayProgress)
            with display_card.get_png_card() as png_card:
                await interaction.response.send_message(file=discord.File(png_card.file))


setup = extension_setup(ShowCommand)
