from typing import Optional
import discord
from discord import app_commands
from bot.main import extension_setup
from bot.cogs.xp.main import XPCommandCog
from bot.exceptions import standard_error_handling


class ScalarCommands(XPCommandCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scalar_command_group: Optional[app_commands.Group] = None

    def create_groups(self) -> None:
        self.scalar_command_group = app_commands.Group(name="rolescalar",
                                                       description="Commands relating to role XP scalars.",
                                                       guild_only=True,
                                                       parent=self.command_group_cog.xp_commands)

    def register_commands(self) -> None:
        @self.scalar_command_group.command(name="assign")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def assign_scalar(interaction: discord.Interaction,
                                role: discord.Role,
                                power: float,
                                priority: int):
            """Assign an XP scalar to a role.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            role : discord.Role
                The role that will apply the XP scalar.
            power : float
                The XP scalar to apply.
            priority : int
                The priority of the XP scalar. Higher priorities will be applied in place of lower priorities.
            """
            self.handler.assign_role_scalar(role, power, priority)
            await interaction.response.send_message(f"Successfully assigned XP scalar `{power}` to {role.mention} with priority `{priority}`.")

        @self.scalar_command_group.command(name="modify")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def modify_scalar(interaction: discord.Interaction,
                                role: discord.Role,
                                power: Optional[float],
                                priority: Optional[int]):
            """Modify an existing role XP scalar.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            role : discord.Role
                The role that will apply the XP scalar.
            power : float
                The XP scalar to apply.
            priority : int
                The priority of the XP scalar. Higher priorities will be applied in place of lower priorities.
            """
            self.handler.modify_role_scalar(role, power, priority)
            await interaction.response.send_message(f"Successfully updated {role.mention}'s XP scalar.")

        @self.scalar_command_group.command(name="remove")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def remove_scalar(interaction: discord.Interaction,
                                role: discord.Role):
            """Remove an existing role XP scalar.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            role : discord.Role
                The role whose XP scalar will be removed.
            """
            self.handler.remove_role_scalar(role)
            await interaction.response.send_message(f"Successfully removed {role.mention}'s XP scalar.")


setup = extension_setup(ScalarCommands)
