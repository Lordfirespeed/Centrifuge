from typing import Optional, Any
import logging
import discord
from discord import app_commands
from bot.main import extension_setup
from bot.exceptions import standard_error_handling
from bot.cogs.xp.main import XPCommandCog, ExperienceMember


class AutoroleCommands(XPCommandCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.autorole_command_group: Optional[app_commands.Group] = None

    async def cog_load(self, *args, **kwargs) -> None:
        await super().cog_load(*args, **kwargs)
        self.handler.level_up_event.subscribe(self.update_user_roles_on_level_up)
        self.handler.level_changed_event.subscribe(self.refresh_experience_member_autoroles)

    def create_groups(self) -> None:
        self.autorole_command_group = app_commands.Group(
            name="autorole",
            description="Commands relating to automatically assigning roles based on user XP levels.",
            guild_only=True,
            parent=self.command_group_cog.admin_xp_commands
        )

    def register_commands(self) -> None:
        @self.autorole_command_group.command(name="create")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def create_autorole(interaction: discord.Interaction,
                                  role: discord.Role,
                                  assign_at: int,
                                  remove_at: Optional[int]):
            """Create an XP level autorole rule.

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
            if remove_at is None:
                remove_at = 0
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

        @self.autorole_command_group.command(name="summary")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def summarise_autoroles(interaction: discord.Interaction):
            """Summarise all autorole info for the server.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            """
            raise NotImplementedError

        @self.autorole_command_group.command(name="show")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def show_autorole(interaction: discord.Interaction,
                              role: discord.Role):
            """Show the autorole info for a role, if any exists.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            role : discord.Role
                The role whose autorole info will be displayed.
            """
            raise NotImplementedError

        @self.command_group_cog.xp_commands.command(name="refreshmyroles")
        @standard_error_handling
        async def refresh_self(interaction: discord.Interaction):
            """Refresh your XP autoroles. Use this if you believe you're missing XP level roles."""
            await self.refresh_member_autoroles(interaction.user)
            await interaction.response.send_message(f"Successfully refreshed your XP level autoroles.", ephemeral=True)

        @self.autorole_command_group.command(name="refresh")
        @app_commands.default_permissions(manage_guild=True)
        async def refresh(interaction: discord.Interaction,
                          member: discord.Member):
            """Refresh a member's XP autoroles. Use this if you believe they're missing XP level roles."""
            await self.refresh_member_autoroles(member)
            await interaction.response.send_message(f"Successfully refreshed {member.mention}'s XP level autoroles.")

    def map_role_ids_to_roles(self, role_ids: [int]) -> [discord.Role]:
        return map(self.bot.guild.get_role, role_ids)

    def get_auto_role_ids_by_condition(self, condition: str, fields: tuple[Any, ...]) -> [int]:
        rows = self.handler.basic_database_query(self.handler.sql_commands.select_auto_roles_by_condition(("roleid",), condition), fields, -1)
        return map(lambda x: x["roleid"], rows)

    def get_comprehensive_role_ids_to_assign(self, at_level: int) -> [int]:
        """Returns all role IDs that some arbitrary user of XP level at_level should be assigned."""
        return self.get_auto_role_ids_by_condition("assign_at<=? AND (remove_at>? OR remove_at<=0)", (at_level, at_level))

    def get_comprehensive_role_ids_to_deassign(self, at_level: int) -> [int]:
        """Returns all role IDs that some arbitrary user of XP level at_level should be deassigned."""
        return self.get_auto_role_ids_by_condition("assign_at >? OR (remove_at<=? AND remove_at>0)", (at_level, at_level))

    def get_role_ids_to_assign(self, at_level: int) -> [int]:
        """Returns role IDs that should be newly assigned at at_level."""
        return self.get_auto_role_ids_by_condition("assign_at=?", (at_level,))

    def get_role_ids_to_deassign(self, at_level: int) -> [int]:
        """Returns role IDs that should be newly deassigned at at_level."""
        return self.get_auto_role_ids_by_condition("remove_at=?", (at_level,))

    def get_comprehensive_roles_to_assign(self, at_level: int) -> [discord.Role]:
        ids = self.get_comprehensive_role_ids_to_assign(at_level)
        return self.map_role_ids_to_roles(ids)

    def get_comprehensive_roles_to_deassign(self, at_level: int) -> [discord.Role]:
        ids = self.get_comprehensive_role_ids_to_deassign(at_level)
        return self.map_role_ids_to_roles(ids)

    def get_roles_to_assign(self, at_level: int) -> [discord.Role]:
        ids = self.get_role_ids_to_assign(at_level)
        return self.map_role_ids_to_roles(ids)

    def get_roles_to_deassign(self, at_level: int) -> [discord.Role]:
        ids = self.get_role_ids_to_deassign(at_level)
        return self.map_role_ids_to_roles(ids)

    async def update_user_roles_on_level_up(self, member: ExperienceMember, new_level: int) -> None:
        await member.add_roles(*self.get_roles_to_assign(new_level), reason="User leveled up")
        await member.remove_roles(*self.get_roles_to_deassign(new_level), reason="User leveled up")

    async def refresh_member_autoroles(self, member: discord.Member) -> None:
        experience_member = self.handler.convert_to_experience_member(member)
        await self.refresh_experience_member_autoroles(experience_member)

    async def refresh_experience_member_autoroles(self, member: ExperienceMember, member_level: Optional[int] = None) -> None:
        # iterate through all autorole rules, separate them into bins of "should" and "shouldn't" be assigned at x level
        should_be_assigned = set(self.get_comprehensive_roles_to_assign(member.level))
        should_not_be_assigned = set(self.get_comprehensive_roles_to_deassign(member.level))
        # figure out which ones the member already has (remove them from the "should assign" bin)
        set_member_roles = set(member.roles)
        to_assign = should_be_assigned.difference(set_member_roles)
        # figure out which of the "shouldn't" ones the member doesn't have (remove them from the "shouldn't be assigned" bin)
        to_deassign = should_not_be_assigned.intersection(set(member.roles))
        # do the assigning / deassigning of whatever is left
        await member.add_roles(*to_assign, reason="Refreshed user's XP autoroles")
        await member.remove_roles(*to_deassign, reason="Refreshed user's XP autoroles")


setup = extension_setup(AutoroleCommands)
