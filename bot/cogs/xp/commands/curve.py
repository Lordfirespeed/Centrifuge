import discord
from discord import app_commands
from bot.main import basic_extension_setup
from bot.cogs.xp.main import XPCommandCog


class CurveCommand(XPCommandCog):
    def register_command(self):
        @self.command_group_cog.xp_commands.command(name="curve")
        @app_commands.choices(maintain=[
            app_commands.Choice(name="xp", value=False),
            app_commands.Choice(name="level", value=True)
        ])
        @app_commands.default_permissions(manage_guild=True)
        async def curve(interaction: discord.Interaction,
                        scalar: float,
                        power: float,
                        maintain: app_commands.Choice[bool]):
            """Update the level XP requirement curve.
            Level XP Requirement = scalar * Level ** power

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            scalar : float
                The scalar in the requirement curve expression.
            power : float
                The power in the requirement curve expression.
            maintain : app_commands.Choice[bool]
                Whether to maintain users' level progress or XP quantity.
            """

            self.handler.update_level_curve(scalar, power, maintain.value)

            await interaction.response.send_message(content=f"Success.")


setup = basic_extension_setup(CurveCommand)
