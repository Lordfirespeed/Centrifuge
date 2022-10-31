import discord
from discord import app_commands
from bot.main import extension_setup
from bot.cogs.xp.main import XPCommandCog
from bot.exceptions import standard_error_handling


class RewardCommands(XPCommandCog):
    def register_commands(self) -> None:
        @self.command_group_cog.admin_xp_commands.command(name="reward")
        @app_commands.choices(action=[
            app_commands.Choice(name="message", value="message"),
            app_commands.Choice(name="voice", value="voice"),
            app_commands.Choice(name="reply", value="reply"),
            app_commands.Choice(name="react", value="react")
        ])
        @standard_error_handling
        async def set_xp_reward(interaction: discord.Interaction,
                                action: app_commands.Choice[str],
                                reward: float):
            """Set the XP reward for a particular action.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            action: app_commands.Choice[str]
                The action that will prompt the XP reward.
            reward: float
                The amount of XP to be awarded following the action."""

            self.handler.set_xp_reward_for_action(action.value, reward)
            await interaction.response.send_message(content=f"Successfully set XP reward for `{action.name}` to `{reward}`xp.")

        @self.command_group_cog.admin_xp_commands.command(name="cap")
        @app_commands.default_permissions(manage_guild=True)
        @standard_error_handling
        async def set_xp_gain_cap(interaction: discord.Interaction,
                                  cap: float):
            """Set the per-minute XP gain cap for all users.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            cap: float
                The maximum amount of XP that an arbitrary user can earn per minute."""

            self.handler.set_xp_gain_cap(cap)
            await interaction.response.send_message(content=f"Successfully set XP gain cap to `{cap}`xp per minute.")


setup = extension_setup(RewardCommands)
