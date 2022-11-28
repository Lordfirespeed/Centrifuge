from __future__ import annotations
from typing import Awaitable, Callable, Optional
from os import getenv, getcwd
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from bot.theme import EmbedTheme


class FeatureCog(commands.Cog.__class__):
    dependencies = Optional[tuple[str]]
    features = Optional[tuple[str]]

    @classmethod
    async def load_features(cls, bot: GuildBot) -> None:
        if cls.features is None:
            return
        if len(cls.features) == 0:
            return

        for dependent in cls.features:
            await bot.load_extension(dependent)

    @classmethod
    async def load_dependencies(cls, bot: GuildBot) -> None:
        if cls.dependencies is None:
            return
        if len(cls.dependencies) == 0:
            return

        for dependency in cls.dependencies:
            await bot.load_extension(dependency)


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
                          "cogs.xp.commands.show"
                          ]

    def __init__(self, guild, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild: discord.Guild = guild
        self.embed_theme = EmbedTheme("Main", discord.Colour.from_rgb(0, 145, 255))
        self.loaded_extensions = set()

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

    async def load_extension(self, extension_name: str, *args, **kwargs) -> None:
        if extension_name in self.loaded_extensions:
            return
        await super().load_extension(extension_name, *args, **kwargs)
        self.loaded_extensions.add(extension_name)


async def load_features(bot: GuildBot, cog: commands.Cog.__class__) -> None:
    if not issubclass(cog, FeatureCog):
        return

    await cog.load_features(bot)


async def load_dependencies(bot: GuildBot, cog: commands.Cog.__class__) -> None:
    if not issubclass(cog, FeatureCog):
        return

    await cog.load_dependencies(bot)


def extension_setup(*args: [commands.Cog.__class__]) -> Callable[[GuildBot], Awaitable[None]]:
    async def setup(bot: GuildBot) -> None:
        for cog in args:
            await load_dependencies(bot, cog)
            new_cog = cog(bot)
            await bot.add_cog(new_cog, guilds=[bot.guild])
            await load_features(bot, cog)

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
