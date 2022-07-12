import discord
from discord import app_commands
from bot.main import extension_setup
from bot.exceptions import standard_error_handling
from bot.cogs.xp.main import SetExperienceType, XPCommandCog


class SetExperienceCommand(XPCommandCog):
    def register_commands(self) -> None:
        set_type_choices = [app_commands.Choice(name=set_type.name, value=set_type.value) for set_type in SetExperienceType]

        @self.command_group_cog.xp_commands.command(name="set")
        @app_commands.choices(set_type=set_type_choices)
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def set_experience(interaction: discord.Interaction,
                                 member: discord.Member,
                                 set_type: app_commands.Choice[int],
                                 coefficient: float):
            """Set a member's experience quantity or level to a coefficient.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            member : discord.Member
                The user whose XP will be set.
            set_type : app_commands.Choice[int]
                Whether to set the user's total XP quantity or XP level.
            coefficient : float
                The coefficient that the user's XP will be set to.
            """
            set_type = SetExperienceType(set_type.value)
            self.handler.set_member_experience(member, coefficient, set_type)
            await interaction.response.send_message(
                f"Successfully set {member.mention}'s {set_type.name} to `{coefficient}`.")


setup = extension_setup(SetExperienceCommand)
