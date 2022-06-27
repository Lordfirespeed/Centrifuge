import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()

token = os.getenv("APPLICATION_TOKEN")
server_id = int(os.getenv("DISCORD_SERVER_ID"))
guild = discord.Object(id=server_id)


class SquadsBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.guild = guild
        super().__init__(*args, **kwargs)

    @staticmethod
    async def validate_arguments(interaction: discord.Interaction, arguments: dict[str, list[type, type]]):
        valid_bools = {argument_name: types[0] == types[1] for argument_name, types in arguments.items() if
                       not isinstance(None, types[0])}
        if not all(valid_bools.values()):
            invalid_arguments = {argument_name: arguments[argument_name][1] for argument_name, valid in
                                 valid_bools.items() if not valid}
            newline = "\n"
            await interaction.response.send_message(
                f"Incorrect argument type(s).\n{newline.join([f'`{argument_name}` should be `{correct_type.__name__}`' for argument_name, correct_type in invalid_arguments.items()])}")
            return False
        else:
            return True

    async def setup_hook(self) -> None:
        await bot.add_cog(HighLevel(bot), guilds=[bot.guild])
        await bot.add_cog(LowLevel(bot), guilds=[bot.guild])
        await self.load_extension(f"cogs.squad_voice")
        await bot.tree.sync(guild=guild)


class LowLevel(commands.Cog, name="Low Level"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Checks bot latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(content=f"Pong! (`{round(self.bot.latency * 1000)}ms`)")


class HighLevel(commands.Cog, name="High Level"):
    def __init__(self, bot):
        self.bot = bot
        self.restarting = False

    @app_commands.command(name="restart", description="Restart the bot. Locked to bot developer")
    async def _restart(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(f"You don't have permission to use this.")
            return
        if self.restarting:
            await interaction.response.send_message(f"Already restarting.")
            return

        self.restarting = True
        path_to_start = os.path.join(os.path.dirname(__file__), "..", "start_bot.sh")
        if os.path.exists(path_to_start) and os.path.isfile(path_to_start):
            await interaction.response.send_message(f"Restarting...")
            await self.bot.close()
            os.chdir(os.path.join(os.path.dirname(__file__), ".."))
            os.execv(path_to_start, [" "])
        else:
            await interaction.response.send_message(f"Failed to find bot start script.")


intents = discord.Intents.none()
intents.guilds = True
intents.voice_states = True
bot = SquadsBot(command_prefix=">", intents=intents, case_insensitive=True)

bot.run(token)
