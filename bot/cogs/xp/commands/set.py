import discord
from discord import app_commands
from bot.main import extension_setup
from bot.exceptions import standard_error_handling
from bot.cogs.xp.main import ExperienceQuantityType, XPCommandCog


class SetExperienceCommand(XPCommandCog):
    def register_commands(self) -> None:
        set_type_choices = [app_commands.Choice(name=set_type.name, value=set_type.value) for set_type in ExperienceQuantityType]

        @self.command_group_cog.admin_xp_commands.command(name="set")
        @app_commands.choices(set_type=set_type_choices)
        @standard_error_handling
        async def set_experience(interaction: discord.Interaction,
                                 member: discord.Member,
                                 set_type: app_commands.Choice[int],
                                 coefficient: app_commands.Range[float, 0, None]):
            """Set a member's experience quantity or level to a coefficient.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            member : discord.Member
                The user whose XP will be set.
            set_type : app_commands.Choice[int]
                Whether to set the user's total XP quantity or XP level.
            coefficient : app_commands.Range[float, 0, None]
                The positive coefficient that the user's XP will be set to.
            """
            set_type = ExperienceQuantityType(set_type.value)
            self.handler.set_member_experience(member, coefficient, set_type)
            await interaction.response.send_message(
                f"Successfully set {member.mention}'s {set_type.name} to `{coefficient}`.")

        @self.command_group_cog.admin_xp_commands.command(name="add")
        @app_commands.choices(add_type=set_type_choices)
        @standard_error_handling
        async def set_experience(interaction: discord.Interaction,
                                 member: discord.Member,
                                 add_type: app_commands.Choice[int],
                                 coefficient: app_commands.Range[float, 0, None]):
            """Set a member's experience quantity or level to a coefficient.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            member : discord.Member
                The user whose XP will be added to.
            add_type : app_commands.Choice[int]
                Whether to add an XP quantity or some XP levels.
            coefficient : app_commands.Range[float, 0, None]
                The coefficient to add to the user's XP level/quantity.
            """
            add_type = ExperienceQuantityType(add_type.value)
            self.handler.add_member_experience(member, coefficient, add_type)
            await interaction.response.send_message(
                f"Successfully added `{coefficient}` {add_type.name} to {member.mention}.")


setup = extension_setup(SetExperienceCommand)
