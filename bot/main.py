from typing import Awaitable, Callable
from os import getenv
import discord
from discord.ext import commands
from dotenv import load_dotenv


class GuildBot(commands.Bot):
    initial_extensions = ["cogs.squad_voice",
                          "cogs.misc.ping",
                          "cogs.misc.restart"]

    def __init__(self, guild, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild = guild

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
        for extension_name in self.initial_extensions:
            await self.load_extension(extension_name)

        await self.tree.sync(guild=self.guild)


def basic_extension_setup(cog: commands.Cog.__class__) -> Callable[[GuildBot], Awaitable[None]]:
    async def setup(bot: GuildBot) -> None:
        await bot.add_cog(cog(bot), guilds=[bot.guild])
    return setup


def main() -> None:
    load_dotenv()

    token = getenv("APPLICATION_TOKEN")
    server_id = int(getenv("DISCORD_SERVER_ID"))
    guild = discord.Object(id=server_id)

    intents = discord.Intents.none()
    intents.guilds = True
    intents.voice_states = True
    bot = GuildBot(guild, command_prefix=">", intents=intents, case_insensitive=True)

    bot.run(token)


if __name__ == "__main__":
    main()
