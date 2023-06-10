from typing import Optional
import sqlite3
from math import ceil
import discord
from discord import app_commands
from bot.common import extension_setup
from bot.cogs.xp.main import XPCommandCog, ExperienceMember


class LeaderboardCommands(XPCommandCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.leaderboard_command_group: Optional[app_commands.Group] = None

    def create_groups(self) -> None:
        self.leaderboard_command_group = app_commands.Group(name="leaderboard",
                                                            description="Commands for viewing the server XP leaderboard.",
                                                            guild_only=True,
                                                            parent=self.command_group_cog.xp_commands)

    def register_commands(self):
        @self.leaderboard_command_group.command(name="top")
        async def top_leaderboard(interaction: discord.Interaction,
                                  number: app_commands.Range[int, 3, 20] = 10):
            """Show the XP leaderboard of top members for the server.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            number : app_commands.Range[int, 3, 15]
                The number of members to show.
            """
            await interaction.response.send_message(embed=await self.leaderboard_range_embed(1, number))

        @self.leaderboard_command_group.command(name="self")
        async def self_leaderboard(interaction: discord.Interaction,
                                   number: app_commands.Range[int, 3, 20] = 10):
            """Show your position on the XP leaderboard for the server.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            number : app_commands.Range[int, 3, 15]
                The number of members to show.
            """
            member = self.handler.convert_to_experience_member(interaction.user)
            await interaction.response.send_message(embed=await self.leaderboard_embed_around_member(member, number))

    def leaderboard_range_rows(self, from_rank: int, to_rank: int) -> [sqlite3.Row]:
        return self.handler.basic_database_query(self.handler.sql_commands.select_many_members_by_condition(('userid', 'experience', 'experience_level', 'rank'), "rank>=? AND rank <=?"), (from_rank, to_rank), -1)

    async def leaderboard_range_experience_members(self, from_rank: int, to_rank: int) -> [ExperienceMember]:
        rows = self.leaderboard_range_rows(from_rank, to_rank)
        members = [ExperienceMember.cast_from_member(await self.bot.lookup_member(row["userid"]), self.handler) for row in rows]
        for member, row in zip(members, rows):
            member.level = row["experience_level"]
            member.xp_quantity = row["experience"]
            member.rank = row["rank"]
        # members.sort(key=lambda x: x.rank, reverse=True)
        return members

    async def leaderboard_range_embed(self, from_rank: int, to_rank: int) -> discord.Embed:
        members = await self.leaderboard_range_experience_members(from_rank, to_rank)
        embed = discord.Embed(title="**Server XP Leaderboard**")
        self.bot.embed_theme.apply_theme(embed)
        maximum_level_length = len(str(members[0].level))
        maximum_rank_length = len(str(to_rank))

        def format_member(member: ExperienceMember) -> str:
            return f"``Rank #{member.rank:<{maximum_rank_length}} @ Level {member.level:<{maximum_level_length}}:`` {member.mention}"

        embed.description = "\n".join(map(format_member, members))

        return embed

    async def leaderboard_embed_around_member(self, member: ExperienceMember, quantity: int) -> discord.Embed:
        midpoint = member.rank
        lowpoint = max(midpoint-ceil(quantity/2), 1)
        highpoint = lowpoint+quantity-1
        return await self.leaderboard_range_embed(lowpoint, highpoint)


setup = extension_setup(LeaderboardCommands)
