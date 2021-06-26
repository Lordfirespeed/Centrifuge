import os
import json
import asyncio
import discord
from discord_slash import cog_ext, SlashCommand, SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice, create_permission
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

    @staticmethod
    async def authenticate(context: SlashContext, permission_names: list[str]):
        perm_bools = {permission_name: getattr(context.author.guild_permissions, permission_name) for permission_name in permission_names}
        if not all(perm_bools.values()):
            missing_perms = [permission_name for permission_name, has_permission in perm_bools.items() if not has_permission]
            missing_perms_titles = [permission_name.replace("_", " ").title() for permission_name in missing_perms]
            await context.send(f"Sorry, you don't have permission to execute this command. (Missing: `{'`, `'.join(missing_perms_titles)}`)")
            return False
        else:
            return True

    @staticmethod
    async def validate_arguments(context: SlashContext, arguments: dict[str, list[type, type]]):
        valid_bools = {argument_name: types[0] == types[1] for argument_name, types in arguments.items() if not isinstance(None, types[0])}
        if not all(valid_bools.values()):
            invalid_arguments = {argument_name: arguments[argument_name][1] for argument_name, valid in valid_bools.items() if not valid}
            newline = "\n"
            await context.send(f"Incorrect argument type(s).\n{newline.join([f'`{argument_name}` should be `{correct_type.__name__}`' for argument_name, correct_type in invalid_arguments.items()])}")
            return False
        else:
            return True

    def dump_channel_creators(self):
        data = [{"channel_id": channel_creator.channel.id,
                 "create_name": channel_creator.create_name,
                 "create_category_id": channel_creator.create_category.id,
                 "create_user_limit": channel_creator.create_user_limit}
                for channel_creator in self.channel_creators.values()]
        with open("channel-creators.json", "w") as writefile:
            json.dump(data, writefile, indent=2)

    def dump_temporary_channels(self):
        data = [{"channel_id": temporary_channel.channel.id,
                 "owner": temporary_channel.owner_user_id,
                 "index": temporary_channel.index,
                 "creator": temporary_channel.creator.channel.id}
                for temporary_channel in self.all_temporary_channels.values()]
        with open("temporary-channels.json", "w") as writefile:
            json.dump(data, writefile, indent=2)


bot = SquadsBot(command_prefix=">", case_insensitive=True)
slash = SlashCommand(bot, sync_commands=True)


class ChannelCreator:
    def __init__(self, bot: SquadsBot, channel: discord.VoiceChannel, create_name: str, create_category: discord.CategoryChannel = None, create_user_limit: int = None):
        self.bot = bot
        self.channel = channel
        self.create_name = create_name
        self.create_category = create_category
        self.create_user_limit = create_user_limit
        self.created_channels = {}
        self.used_indexes = set()

    def delete(self):
        cache = self.created_channels.copy().values()
        for created_channel in cache:
            created_channel.delete(dump=False)
        self.bot.dump_temporary_channels()
        del cache

        async def remove_channel():
            await self.channel.delete()

        del self.bot.channel_creators[self.channel.id]
        self.bot.dump_channel_creators()

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

    async def create_temporary_channel(self, owner_user_id):
        index = self.get_minimum_unused_index()
        temporary_channel = TemporaryChannel(self.bot, owner_user_id, self, index, self.create_category, self.create_name, self.create_user_limit)
        await temporary_channel.ready.wait()
        self.register_temporary_channel(temporary_channel)

        return temporary_channel

    def register_temporary_channel(self, temporary_channel, dump=True):
        self.used_indexes.add(temporary_channel.index)
        self.created_channels[temporary_channel.channel.id] = temporary_channel
        self.bot.all_temporary_channels[temporary_channel.channel.id] = temporary_channel
        if dump:
            bot.dump_temporary_channels()

    async def edit(self, create_name: str = None, create_category: discord.CategoryChannel = None, create_user_limit: int = False):
        changed = False
        if create_name:
            self.create_name = create_name
            changed = True

        if create_user_limit or create_user_limit is None:
            self.create_user_limit = create_user_limit
            changed = True

        if create_category:
            self.create_category = create_category

            changed = True

        if changed:
            for _, temporary_channel in sorted(self.created_channels.items()):
                await temporary_channel.edit(name=self.create_name, category=self.create_category, user_limit=self.create_user_limit)


class TemporaryChannel:
    def __init__(self, bot: SquadsBot, owner_user_id: int, creator: ChannelCreator, index: int, category: discord.CategoryChannel, name: str, user_limit: int = None, channel: discord.VoiceChannel = None):
        self.bot = bot
        self.owner_user_id = owner_user_id
        self.creator = creator
        self.index = index
        self.name = name
        self.channel = channel
        self.category = category
        self.user_limit = user_limit
        self.ready = asyncio.Event()

        async def ready_up():
            to_name = self.make_name()
            if self.channel:
                if self.channel.name != to_name or self.channel.user_limit != self.user_limit:
                    await self.channel.edit(name=to_name, user_limit=self.user_limit)
            else:
                self.channel = await creator.channel.guild.create_voice_channel(to_name, category=self.category, user_limit=self.user_limit)
            self.ready.set()

        loop = asyncio.get_event_loop()
        loop.create_task(ready_up())

    def make_name(self):
        return f"{self.name} {str(self.index)}"

    def delete(self, dump=True):

        async def remove_channel():
            await self.channel.delete()

        self.creator.used_indexes.remove(self.index)

        loop = asyncio.get_event_loop()
        loop.create_task(remove_channel())
        del self.creator.created_channels[self.channel.id]
        del self.bot.all_temporary_channels[self.channel.id]
        if dump:
            bot.dump_temporary_channels()

    async def edit(self, index: int = None, category: discord.CategoryChannel = False, name: str = None, user_limit: int = False):
        changed = False
        if index:
            self.index = index
            changed = True

        if category or category is None:
            self.category = category
            changed = True

        if name:
            self.name = name
            changed = True

        if user_limit or user_limit is None:
            self.user_limit = user_limit
            changed = True

        if changed:
            await self.channel.edit(name=self.make_name(), category=self.category, user_limit=self.user_limit)


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
            channel_creator_data["channel"] = await self.bot.fetch_channel(channel_creator_data["channel_id"])
            del channel_creator_data["channel_id"]
            channel_creator_data["create_category"] = await self.bot.fetch_channel(channel_creator_data["create_category_id"])
            del channel_creator_data["create_category_id"]
            channel_creator = ChannelCreator(self.bot, **channel_creator_data)
            self.bot.channel_creators[channel_creator.channel.id] = channel_creator

        with open("temporary-channels.json", "r") as readfile:
            temporary_channels_data = json.load(readfile)
        for temporary_channel_data in temporary_channels_data:
            channel = await self.bot.fetch_channel(temporary_channel_data["channel_id"])
            if len(channel.voice_states) == 0:
                await channel.delete()
            elif channel and temporary_channel_data["creator"] in self.bot.channel_creators.keys():
                channel_creator = self.bot.channel_creators[temporary_channel_data["creator"]]
                temporary_channel = TemporaryChannel(self.bot, temporary_channel_data["owner"], channel_creator, temporary_channel_data["index"], channel_creator.create_category, channel_creator.create_name, channel_creator.create_user_limit, channel)
                await temporary_channel.ready.wait()
                channel_creator.register_temporary_channel(temporary_channel, dump=False)

    @commands.Cog.listener()
    async def on_disconnect(self):
        self.bot.dump_temporary_channels()
        self.bot.dump_channel_creators()
        self.bot.channel_creators = {}
        self.bot.all_temporary_channels = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, user, before, after):
        if after.channel is not None and after.channel != before.channel:
            joined_channel_creator = utils.get(self.bot.channel_creators.values(), channel__id=after.channel.id)
            if joined_channel_creator:
                new_temporary_channel = await joined_channel_creator.create_temporary_channel(user.id)
                await new_temporary_channel.ready.wait()
                await user.move_to(new_temporary_channel.channel)

        if before.channel is not None and before.channel != after.channel:
            left_temp_channel = utils.get(self.bot.all_temporary_channels.values(), channel__id=before.channel.id)
            if left_temp_channel:
                voice_states = before.channel.voice_states
                if len(voice_states) == 0:
                    left_temp_channel.delete()

    @cog_ext.cog_slash(name="ping", guild_ids=[server_id],
                       description="Checks bot latency")
    async def ping(self, ctx: SlashContext):
        await ctx.send(content=f"Pong! (`{round(self.bot.latency*1000)}ms`)")


class CreationCommands(commands.Cog, name="Creation Commands"):
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(name="create", guild_ids=[server_id],
                       description="Create an incremental channel creator.",
                       options=[
                           create_option(name="name",
                                         description="Name of channel creator",
                                         option_type=3,
                                         required=True),
                           create_option(name="category",
                                         description="Category to place creator in",
                                         option_type=7,
                                         required=False),
                           create_option(name="create_name",
                                         description="Name of temporary channels to create",
                                         option_type=3,
                                         required=False),
                           create_option(name="create_category",
                                         description="Category to place temporary channels in",
                                         option_type=7,
                                         required=False),
                           create_option(name="user_limit",
                                         description="User limit of temporary channels",
                                         option_type=4,
                                         required=False)
                       ])
    async def _create_channel_creator(self, context: SlashContext, name: str, category: discord.CategoryChannel = None, create_name: str = None, create_category: discord.CategoryChannel = None, user_limit: int = None):
        if not await self.bot.authenticate(context, ["manage_channels"]):
            return

        typed_params = {"category": [type(category), discord.CategoryChannel], "create_category": [type(create_category), discord.CategoryChannel]}
        if not await self.bot.validate_arguments(context, typed_params):
            return

        new_channel_creator_channel = await context.guild.create_voice_channel(name=name, category=category)
        self.bot.channel_creators[new_channel_creator_channel.id] = ChannelCreator(self.bot, new_channel_creator_channel, create_name or name, create_category or category, user_limit)
        self.bot.dump_channel_creators()
        await context.send("Created new incremental channel creator successfully.")

    @cog_ext.cog_slash(name="delete", guild_ids=[server_id],
                       description="Delete an incremental channel creator.",
                       options=[
                           create_option(name="channel",
                                         description="Incremental voice channel creator to delete",
                                         option_type=7,
                                         required=True)#
                       ])
    async def _delete_channel_creator(self, context: SlashContext, channel: discord.VoiceChannel):
        if not await self.bot.authenticate(context, ["manage_channels"]):
            return

        if channel.id not in self.bot.channel_creators.keys():
            await context.send(f"{channel.mention} is not an incremental voice channel creator.")
        else:
            self.bot.channel_creators[channel.id].delete()
            await context.send(f"Successfully deleted incremental voice channel creator with ID `{channel.id}`")

    @cog_ext.cog_slash(name="edit", guild_ids=[server_id],
                       description="Edit an incremental channel creator.",
                       options=[
                           create_option(name="channel",
                                         description="Incremental voice channel creator to edit",
                                         option_type=7,
                                         required=True),
                           create_option(name="create_name",
                                         description="Name of temporary channels to create",
                                         option_type=3,
                                         required=False),
                           create_option(name="create_category",
                                         description="Category to place temporary channels in",
                                         option_type=7,
                                         required=False),
                           create_option(name="user_limit",
                                         description="User limit of temporary channels",
                                         option_type=4,
                                         required=False)
                       ])
    async def _edit_channel_creator(self, context: SlashContext, channel: discord.VoiceChannel, create_name: str = None, create_category: discord.CategoryChannel = False, user_limit: int = None):
        if not await self.bot.authenticate(context, ["manage_channels"]):
            return

        typed_params = {"create_category": [type(create_category), discord.CategoryChannel]}
        if not await self.bot.validate_arguments(context, typed_params):
            return

        if channel.id not in self.bot.channel_creators.keys():
            await context.send(f"{channel.mention} is not an incremental voice channel creator.")
            return

        channel_creator = self.bot.channel_creators[channel.id]
        await channel_creator.edit(create_name, create_category, user_limit)
        await context.send(f"Successfully edited incremental channel creator {channel_creator.channel.mention}")


class OwnedChannelCommands(commands.Cog, name="Owned Channel Commands"):
    def __init__(self, bot):
        self.bot = bot

    async def get_owned_channel(self, context: SlashContext):
        voice_state = context.author.voice
        if not voice_state:
            await context.send("You are not in a voice channel.")
            return None

        in_channel = voice_state.channel
        if in_channel.id not in self.bot.all_temporary_channels.keys():
            await context.send("You are not in a temporary voice channel.")
            return None

        temporary_channel = self.bot.all_temporary_channels[in_channel.id]
        if context.author.id != temporary_channel.owner_user_id:
            await context.send(
                f"<@{temporary_channel.owner_user_id}> is the owner of your current voice channel, you cannot execute this command.")
            return None

        return temporary_channel

    @cog_ext.cog_slash(name="resize", guild_ids=[server_id],
                       description="Resize your voice channel.",
                       options=[
                           create_option(name="size",
                                         description="Number of users allowed in the channel",
                                         option_type=4,
                                         required=True)
                       ])
    async def _resize(self, context: SlashContext, size: int):
        temporary_channel = await self.get_owned_channel(context)
        if not temporary_channel:
            return
        if size == 0:
            size = None
        elif size < 0:
            await context.send("Cannot set negative channel size.")
            return

        await temporary_channel.edit(user_limit=size)
        await context.send(f"Successfully set {temporary_channel.channel.mention} size to `{size}`")

    @cog_ext.cog_slash(name="limit", guild_ids=[server_id],
                       description="Apply a user limit to your voice channel. Limit 0 removes the limit.",
                       options=[
                           create_option(name="size",
                                         description="Number of users allowed in the channel",
                                         option_type=4,
                                         required=True)
                       ])
    async def _limit(self, context: SlashContext, size: int):
        temporary_channel = await self.get_owned_channel(context)
        if not temporary_channel:
            return
        if size == 0:
            size = None
        elif size < 0:
            await context.send("Cannot set negative channel size.")
            return

        await temporary_channel.edit(user_limit=size)
        await context.send(f"Successfully limited {temporary_channel.channel.mention} to `{size}`")

    @cog_ext.cog_slash(name="unlimit", guild_ids=[server_id],
                       description="Unlimit your voice channel.")
    async def _unlimit(self, context):
        temporary_channel = await self.get_owned_channel(context)
        if temporary_channel:
            await temporary_channel.edit(user_limit=None)
            await context.send(f"Successfully unlimited {temporary_channel.channel.mention}")

    @cog_ext.cog_slash(name="rename", guild_ids=[server_id],
                       description="Rename your voice channel.",
                       options=[
                           create_option(name="name",
                                         description="New name of the channel",
                                         option_type=3,
                                         required=True)
                       ])
    async def _rename(self, context: SlashContext, name: str):
        temporary_channel = await self.get_owned_channel(context)
        if temporary_channel:
            await temporary_channel.edit(name=name)
            await context.send(f"Successfully renamed {temporary_channel.channel.mention}")


bot.add_cog(VoiceHandler(bot))
bot.add_cog(CreationCommands(bot))
bot.add_cog(OwnedChannelCommands(bot))

bot.run(token)
