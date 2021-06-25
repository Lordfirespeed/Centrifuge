import os
import json
import asyncio
import discord
from discord_slash import cog_ext, SlashCommand, SlashContext
from discord import utils
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("DISCORD_TOKEN")
server_id = int(os.getenv("DISCORD_SERVER_ID"))


class SquadsBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.channel_creators = {}
        self.all_temporary_channels = {}
        super().__init__(*args, **kwargs)


bot = SquadsBot(command_prefix=">", case_insensitive=True)
slash = SlashCommand(bot, sync_commands=True)


class ChannelCreator:
    def __init__(self, bot: SquadsBot, channel_id: int, create_name: str, create_category_id: int = None, create_user_limit: int = None):
        self.bot = bot
        self.channel_id = channel_id
        self.channel = None
        self.create_name = create_name
        self.create_category_id = create_category_id
        self.create_category = None
        self.create_userlimit = create_user_limit
        self.created_channels = {}
        self.used_indexes = set()
        self.ready = asyncio.Event()

        async def ready_up():
            self.channel = await bot.fetch_channel(channel_id)
            if create_category_id is not None:
                self.create_category = await bot.fetch_channel(create_category_id)
            else:
                self.create_category = self.channel.category
            self.ready.set()

        loop = asyncio.get_event_loop()
        loop.create_task(ready_up())

    def delete(self):
        cache = self.created_channels.copy().values()
        for created_channel in cache:
            created_channel.delete()
        del cache

        async def remove_channel():
            await self.channel.delete()

        del self.bot.channel_creators[self.channel_id]

        loop = asyncio.get_event_loop()
        loop.create_task(remove_channel())

    def get_minimum_unused_index(self):
        if len(self.used_indexes) == 0:
            return 1
        minval, maxval = min(self.used_indexes), max(self.used_indexes)
        if len(self.used_indexes) < maxval - minval + 1:
            return min(set(range(minval, maxval+1)) - self.used_indexes)
        else:
            return len(self.used_indexes) + 1

    async def create_temporary_channel(self):
        index = self.get_minimum_unused_index()
        temporary_channel = TemporaryChannel(self.bot, self, index, self.create_category, self.create_name, self.create_userlimit)
        self.used_indexes.add(index)
        await temporary_channel.ready.wait()
        self.created_channels[temporary_channel.channel.id] = temporary_channel
        self.bot.all_temporary_channels[temporary_channel.channel.id] = temporary_channel
        return temporary_channel


class TemporaryChannel:
    def __init__(self, bot: SquadsBot, creator: ChannelCreator, index: int, category: discord.CategoryChannel, name: str, user_limit: int = None):
        self.bot = bot
        self.creator = creator
        self.index = index
        self.channel = None
        self.ready = asyncio.Event()
        kwargs = {"category": category}
        if user_limit is not None:
            kwargs["user_limit"] = user_limit

        async def ready_up():
            self.channel = await category.guild.create_voice_channel(f"{name} {str(index)}", **kwargs)
            self.ready.set()

        loop = asyncio.get_event_loop()
        loop.create_task(ready_up())

    def delete(self):

        async def remove_channel():
            await self.channel.delete()

        self.creator.used_indexes.remove(self.index)

        loop = asyncio.get_event_loop()
        loop.create_task(remove_channel())
        del self.creator.created_channels[self.channel.id]
        del self.bot.all_temporary_channels[self.channel.id]


@bot.event
async def on_ready():
    guild = discord.utils.get(bot.guilds, id=server_id)
    if not guild:
        print("Failed to connect to server defined in .ENV!")
        return

    print(f'{bot.user} has connected to Discord! Server name: {guild.name}, ID: {guild.id}')


class VoiceHandler(commands.Cog, name="Voice Handler"):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        with open("channel-creators.json", "r") as readfile:
            channel_creators_data = json.load(readfile)
        for channel_creator_data in channel_creators_data:
            channel_creator = ChannelCreator(self.bot, **channel_creator_data)
            self.bot.channel_creators[channel_creator.channel_id] = channel_creator

    @commands.Cog.listener()
    async def on_voice_state_update(self, user, before, after):
        if after.channel is not None and after.channel != before.channel:
            joined_channel_creator = utils.get(self.bot.channel_creators.values(), channel_id=after.channel.id)
            if joined_channel_creator:
                if joined_channel_creator.ready.is_set():
                    new_temporary_channel = await joined_channel_creator.create_temporary_channel()
                    await new_temporary_channel.ready.wait()
                    await user.move_to(new_temporary_channel.channel)
                else:
                    await user.move_to(None)
        if before.channel is not None and before.channel != after.channel:
            left_temp_channel = utils.get(self.bot.all_temporary_channels.values(), channel__id=before.channel.id)
            if left_temp_channel:
                voice_states = before.channel.voice_states
                if len(voice_states) == 0:
                    left_temp_channel.delete()

    @cog_ext.cog_slash(name="ping", guild_ids=[server_id])
    async def ping(self, ctx: SlashContext):
        await ctx.send(content="Pong!")


bot.add_cog(VoiceHandler(bot))

bot.run(token)
