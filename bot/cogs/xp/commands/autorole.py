from typing import Optional
import discord
from discord import app_commands
from bot.main import extension_setup
from bot.cogs.xp.main import XPCommandCog
from bot.exceptions import standard_error_handling


class AutoroleCommands(XPCommandCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.autorole_command_group: Optional[app_commands.Group] = None

    def create_groups(self) -> None:
        self.autorole_command_group = app_commands.Group(name="autorole",
                                                         description="Commands relating to automatically assigning roles based on user XP levels.",
                                                         guild_only=True,
                                                         parent=self.command_group_cog.xp_commands)

    def register_commands(self) -> None:
        @self.autorole_command_group.command(name="create")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def create_autorole(interaction: discord.Interaction,
                                  role: discord.Role,
                                  assign_at: int,
                                  remove_at: int):
            """Assign an XP scalar to a role.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            role : discord.Role
                The role that will be assigned.
            assign_at : int
                The XP level that the role will be assigned at.
            remove_at : int
                The XP level that the role will be removed at.
            """
            self.handler.create_autorole(role, assign_at, remove_at)
            await interaction.response.send_message(f"Successfully created autorole rule for {role.mention}.")

        @self.autorole_command_group.command(name="modify")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def modify_autorole(interaction: discord.Interaction,
                                  role: discord.Role,
                                  assign_at: Optional[int],
                                  remove_at: Optional[int]):
            """Modify an autorole rule.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            role : discord.Role
                The role that is assigned.
            assign_at : Optional[int]
                The XP level that the role will be assigned at.
            remove_at : Optional[int]
                The XP level that the role will be removed at.
            """
            self.handler.modify_autorole(role, assign_at, remove_at)
            await interaction.response.send_message(f"Successfully updated {role.mention}'s autorole rule.")

        @self.autorole_command_group.command(name="remove")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def remove_autorole(interaction: discord.Interaction,
                                  role: discord.Role):
            """Stop automatically assigning a role based upon users' XP levels.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            role : discord.Role
                The role to stop assigning.
            """
            self.handler.remove_autorole(role)
            await interaction.response.send_message(f"Successfully removed {role.mention}'s autorole rule.")


setup = extension_setup(AutoroleCommands)
