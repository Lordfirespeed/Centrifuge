from typing import Awaitable, Callable, Optional
from os import getenv, getcwd
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from bot.theme import EmbedTheme


class FeatureCog(commands.Cog.__class__):
    dependents = Optional[tuple[str]]


class GuildBot(commands.Bot):
    initial_extensions = ["cogs.squad_voice",
                          "cogs.misc.ping",
                          "cogs.misc.restart",
                          "cogs.misc.badger",
                          "cogs.xp.group",
                          "cogs.xp.main",
                          "cogs.xp.listeners",
                          "cogs.xp.voice",
                          "cogs.xp.commands.autorole",
                          "cogs.xp.commands.announce",
                          "cogs.xp.commands.curve",
                          "cogs.xp.commands.leaderboard",
                          "cogs.xp.commands.reward",
                          "cogs.xp.commands.rolescalar",
                          "cogs.xp.commands.set",
                          "cogs.xp.commands.show",
                          "cogs.fashion.main"
                          ]

    def __init__(self, guild, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild: discord.Guild = guild
        self.embed_theme = EmbedTheme("Main", discord.Colour.from_rgb(0, 145, 255))

    async def lookup_member(self, member_id: int):
        if type(member_id) is not int:
            raise TypeError

        member = self.guild.get_member(member_id)
        if member:
            return member

        member = await self.guild.fetch_member(member_id)
        return member

    async def lookup_channel(self, channel_id: int):
        if type(channel_id) is not int:
            raise TypeError

        channel = self.guild.get_channel(channel_id)
        if channel:
            return channel

        channel = await self.guild.fetch_channel(channel_id)
        return channel

    async def setup_hook(self) -> None:
        self.guild = await self.fetch_guild(self.guild.id)

        for extension_name in self.initial_extensions:
            await self.load_extension(extension_name)

        await self.tree.sync(guild=self.guild)

    async def load_extension(self, *args, **kwargs) -> None:
        await super().load_extension(*args, **kwargs)


async def load_dependencies(bot: GuildBot, cog: FeatureCog) -> None:
    if not isinstance(cog, FeatureCog):
        return
    if cog.dependents is None:
        return
    if len(cog.dependents) == 0:
        return

    for dependent in cog.dependents:
        await bot.load_extension(dependent)


def extension_setup(*args: [commands.Cog.__class__]) -> Callable[[GuildBot], Awaitable[None]]:
    async def setup(bot: GuildBot) -> None:
        for cog in args:
            new_cog = cog(bot)
            await bot.add_cog(new_cog, guilds=[bot.guild])
            await load_dependencies(bot, cog)

    return setup


def main() -> None:
    load_dotenv()

    token = getenv("APPLICATION_TOKEN")
    server_id = int(getenv("DISCORD_SERVER_ID"))
    guild = discord.Object(id=server_id)

    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True
    intents.guild_reactions = True
    intents.voice_states = True
    intents.members = True
    bot = GuildBot(guild, command_prefix=">", intents=intents, case_insensitive=True)

    bot.run(token)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename="botlog.log", filemode="w")
    logging.debug(f"CWD: {getcwd()}")
    main()
