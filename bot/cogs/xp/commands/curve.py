from typing import Optional
import discord
from discord import app_commands
from bot.common import extension_setup
from bot.cogs.xp.main import XPCommandCog


class CurveCommand(XPCommandCog):
    def register_commands(self):
        @self.command_group_cog.admin_xp_commands.command(name="curve")
        @app_commands.choices(maintain=[
            app_commands.Choice(name="xp", value=0),
            app_commands.Choice(name="level", value=1)
        ])
        async def curve(interaction: discord.Interaction,
                        scalar: Optional[float],
                        power: Optional[float],
                        maintain: Optional[app_commands.Choice[int]] = 0):
            """Update the level XP requirement curve.
            Level XP Requirement = scalar * Level ** power
            Users' XP quantities or levels will be updated accordingly; this command is destructive.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            scalar : Optional[float]
                The scalar in the requirement curve expression.
            power : Optional[float]
                The power in the requirement curve expression.
            maintain : Optional[app_commands.Choice[int]]
                Whether to maintain users' level progress or XP quantity.
            """

            if type(maintain) is app_commands.Choice:
                maintain = maintain.value
            maintain = bool(maintain)

            self.handler.update_level_curve(scalar, power, maintain)

            await interaction.response.send_message(content=f"Successfully set new level requirement curve to `{self.handler.level_curve_scalar} * L^{self.handler.level_curve_power}`.")


setup = extension_setup(CurveCommand)
