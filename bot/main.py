from typing import Awaitable, Callable, Optional
from os import getenv
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv


class DependentCog(commands.Cog.__class__):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dependencies = Optional[tuple[str]]


class GuildBot(commands.Bot):
    initial_extensions = ["cogs.squad_voice",
                          "cogs.misc.ping",
                          "cogs.misc.restart",
                          "cogs.misc.badger",
                          "cogs.xp.group",
                          "cogs.xp.main",
                          "cogs.xp.listeners",
                          "cogs.xp.commands.show",
                          "cogs.xp.commands.curve",
                          "cogs.xp.commands.rolescalar",
                          "cogs.xp.commands.autorole",
                          "cogs.xp.commands.set",
                          "cogs.xp.commands.announce",
                          "cogs.xp.commands.reward"]

    def __init__(self, guild, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild: discord.Guild = guild

    async def lookup_member(self, member_id: int):
        member = self.guild.get_member(member_id)
        if member:
            return member

        member = await self.guild.fetch_member(member_id)
        return member

    async def lookup_channel(self, channel_id: int):
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


async def load_dependencies(bot: GuildBot, cog: DependentCog) -> None:
    if not isinstance(cog, DependentCog):
        return
    if cog.dependencies is None:
        return
    if len(cog.dependencies) == 0:
        return

    for dependency in cog.dependencies:
        await bot.load_extension(dependency)


def extension_setup(cog: commands.Cog.__class__) -> Callable[[GuildBot], Awaitable[None]]:
    async def setup(bot: GuildBot) -> None:
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
    logging.basicConfig(level=logging.DEBUG)
    main()
