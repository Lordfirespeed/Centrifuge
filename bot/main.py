import os
import re
import json
import asyncio
import discord
from collections import defaultdict
from discord_slash import cog_ext, SlashCommand, SlashContext
from discord_slash.utils.manage_commands import create_option
from discord import utils
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("APPLICATION_TOKEN")
server_id = int(os.getenv("DISCORD_SERVER_ID"))
server_ids = [server_id]


class SquadsBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.channel_creators = {}
        self.all_temporary_channels = {}
        super().__init__(*args, **kwargs)

    @staticmethod
    async def authenticate(context: SlashContext, permission_names: list[str]):
        perm_bools = {permission_name: getattr(context.author.guild_permissions, permission_name) for permission_name in
                      permission_names}
        if not all(perm_bools.values()):
            missing_perms = [permission_name for permission_name, has_permission in perm_bools.items() if
                             not has_permission]
            missing_perms_titles = [permission_name.replace("_", " ").title() for permission_name in missing_perms]
            await context.send(
                f"Sorry, you don't have permission to execute this command. (Missing: `{'`, `'.join(missing_perms_titles)}`)")
            return False
        else:
            return True

    @staticmethod
    async def validate_arguments(context: SlashContext, arguments: dict[str, list[type, type]]):
        valid_bools = {argument_name: types[0] == types[1] for argument_name, types in arguments.items() if
                       not isinstance(None, types[0])}
        if not all(valid_bools.values()):
            invalid_arguments = {argument_name: arguments[argument_name][1] for argument_name, valid in
                                 valid_bools.items() if not valid}
            newline = "\n"
            await context.send(
                f"Incorrect argument type(s).\n{newline.join([f'`{argument_name}` should be `{correct_type.__name__}`' for argument_name, correct_type in invalid_arguments.items()])}")
            return False
        else:
            return True

    def dump_channel_creators(self):
        data = [{"channel_id": channel_creator.channel.id,
                 "create_name": channel_creator.create_name,
                 "create_category_id": channel_creator.create_category.id if channel_creator.create_category else None,
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
    def __init__(self, bot: SquadsBot, channel: discord.VoiceChannel, create_name: str,
                 create_category: discord.CategoryChannel = None, create_user_limit: int = None):
        self.bot = bot
        self.channel = channel
        self.create_name = create_name
        self.create_category = create_category
        self.create_user_limit = create_user_limit
        self.created_channels = {}
        self.used_indexes = set()

    async def delete(self):
        cache = self.created_channels.copy().values()
        for created_channel in cache:
            await created_channel.delete(dump=False)
        self.bot.dump_temporary_channels()
        del cache

        await self.channel.delete()

        del self.bot.channel_creators[self.channel.id]
        self.bot.dump_channel_creators()

    def get_minimum_unused_index(self):
        if len(self.used_indexes) == 0:
            return 1
        minval, maxval = min(self.used_indexes), max(self.used_indexes)
        if len(self.used_indexes) < maxval - minval + 1:
            return min(set(range(minval, maxval + 1)) - self.used_indexes)
        else:
            return len(self.used_indexes) + 1

    async def create_temporary_channel(self, owner_user_id):
        index = self.get_minimum_unused_index()
        temporary_channel = TemporaryChannel(self.bot, owner_user_id, self, index, self.create_category,
                                             self.create_name, self.create_user_limit)
        await temporary_channel.ready.wait()
        self.register_temporary_channel(temporary_channel)

        return temporary_channel

    def register_temporary_channel(self, temporary_channel, dump=True):
        self.used_indexes.add(temporary_channel.index)
        self.created_channels[temporary_channel.channel.id] = temporary_channel
        self.bot.all_temporary_channels[temporary_channel.channel.id] = temporary_channel
        if dump:
            bot.dump_temporary_channels()

    async def edit(self, create_name: str = None, create_category: discord.CategoryChannel = None,
                   create_user_limit: int = False):
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
                await temporary_channel.edit(name=self.create_name, category=self.create_category,
                                             user_limit=self.create_user_limit)


class TemporaryChannel:
    def __init__(self, bot: SquadsBot, owner_user_id: int, creator: ChannelCreator, index: int,
                 category: discord.CategoryChannel, name: str, user_limit: int = None,
                 channel: discord.VoiceChannel = None):
        self.bot = bot
        self.owner_user_id = owner_user_id
        self.creator = creator
        self.index = index
        self.name = name
        self.channel = channel
        self.category = category
        self.user_limit = user_limit
        self.edited_recently = defaultdict(lambda: False)
        self.ready = asyncio.Event()

        async def ready_up():
            to_name = self.make_name()
            if not self.channel:
                try:
                    self.channel = await creator.channel.guild.create_voice_channel(to_name, category=self.category,
                                                                                    user_limit=self.user_limit)
                except discord.HTTPException as error:
                    if "Category does not exist" in str(error):
                        self.creator.create_category = self.creator.channel.category
                        self.category = self.creator.create_category
                        self.channel = await creator.channel.guild.create_voice_channel(to_name, category=self.category,
                                                                                        user_limit=self.user_limit)
                        self.bot.dump_channel_creators()
                    else:
                        raise error

            self.ready.set()

        loop = asyncio.get_event_loop()
        loop.create_task(ready_up())

    def make_edit_timer(self, time: int, property_name: str):
        async def _job():
            await asyncio.sleep(time)
            self.edited_recently[property_name] = False

        self.edited_recently[property_name] = asyncio.create_task(_job())

    def make_name(self):
        if self.name == self.creator.create_name:
            return f"{self.name} #{str(self.index)}"
        else:
            return self.name

    async def delete(self, dump=True):

        await self.channel.delete()

        self.creator.used_indexes.remove(self.index)

        del self.creator.created_channels[self.channel.id]
        del self.bot.all_temporary_channels[self.channel.id]
        if dump:
            bot.dump_temporary_channels()

    async def edit(self, index: int = None, category: discord.CategoryChannel = False, name: str = None,
                   user_limit: int = False, owner_user_id=None, forced=True):
        changed = False
        on_timer = False
        if index:
            if self.edited_recently["index"]:
                on_timer = True
            elif not forced:
                self.make_edit_timer(60, "index")
                self.index = index
                changed = True

        if category or category is None:
            self.category = category
            changed = True

        if name:
            if self.edited_recently["name"]:
                on_timer = True
            elif not forced:
                self.make_edit_timer(60, "name")
                self.name = name
                changed = True

        if owner_user_id:
            self.owner_user_id = owner_user_id
            # not changed as we do not need to actually edit the channel in discord

        if user_limit or user_limit is None:
            if self.edited_recently["user_limit"]:
                on_timer = True
            elif not forced:
                self.make_edit_timer(60, "user_limit")
                self.user_limit = user_limit
                changed = True

        if on_timer and not forced:
            return False

        if changed and ((not on_timer) or forced):
            await self.channel.edit(name=self.make_name(), category=self.category, user_limit=self.user_limit)
        return True


class VoiceHandler(commands.Cog, name="Voice Handler"):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        with open("channel-creators.json", "r") as readfile:
            channel_creators_data = json.load(readfile)

        self.bot.channel_creators = {}
        self.bot.all_temporary_channels = {}

        for channel_creator_data in channel_creators_data:
            try:
                channel_creator_data["channel"] = await self.bot.fetch_channel(channel_creator_data["channel_id"])
            except discord.NotFound:
                continue
            del channel_creator_data["channel_id"]
            if channel_creator_data["create_category_id"]:
                try:
                    channel_creator_data["create_category"] = await self.bot.fetch_channel(
                        channel_creator_data["create_category_id"])
                except discord.NotFound:
                    channel_creator_data["create_category"] = channel_creator_data["channel"].category
            else:
                channel_creator_data["create_category"] = None
            del channel_creator_data["create_category_id"]
            channel_creator = ChannelCreator(self.bot, **channel_creator_data)
            self.bot.channel_creators[channel_creator.channel.id] = channel_creator

        with open("temporary-channels.json", "r") as readfile:
            temporary_channels_data = json.load(readfile)
        for temporary_channel_data in temporary_channels_data:
            try:
                channel = await self.bot.fetch_channel(temporary_channel_data["channel_id"])
            except discord.NotFound:
                continue
            if len(channel.voice_states) == 0:
                await channel.delete()
            elif channel and temporary_channel_data["creator"] in self.bot.channel_creators.keys():
                channel_creator = self.bot.channel_creators[temporary_channel_data["creator"]]
                temporary_channel = TemporaryChannel(self.bot, temporary_channel_data["owner"], channel_creator,
                                                     temporary_channel_data["index"], channel_creator.create_category,
                                                     channel_creator.create_name, channel_creator.create_user_limit,
                                                     channel)
                await temporary_channel.ready.wait()
                channel_creator.register_temporary_channel(temporary_channel, dump=False)

        self.bot.dump_temporary_channels()
        self.bot.dump_channel_creators()

    @commands.Cog.listener()
    async def on_disconnect(self):
        if self.bot.channel_creators:
            self.bot.dump_channel_creators()
        if self.bot.all_temporary_channels:
            self.bot.dump_temporary_channels()

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
                    await left_temp_channel.delete()

    @cog_ext.cog_slash(name="ping", guild_ids=server_ids,
                       description="Checks bot latency")
    async def ping(self, ctx: SlashContext):
        await ctx.send(content=f"Pong! (`{round(self.bot.latency * 1000)}ms`)")


class HighLevel(commands.Cog, name="High Level"):
    def __init__(self, bot):
        self.bot = bot
        self.restarting = False

    @cog_ext.cog_slash(name="restart", description="Restart the bot. Locked to bot developer.", guild_ids=server_ids)
    async def _restart(self, context: SlashContext):
        if await self.bot.is_owner(context.author) or await self.bot:
            if not self.restarting:
                self.restarting = True
                path_to_start = os.path.join(os.path.dirname(__file__), "..", "start_bot.sh")
                if os.path.exists(path_to_start) and os.path.isfile(path_to_start):
                    await context.send(f"Restarting...")
                    await self.bot.close()
                    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
                    os.execv(path_to_start, [" "])
                else:
                    await context.send(f"Failed to find bot start script.")
        else:
            await context.send(f"You don't have permission to use this.")


class CreationCommands(commands.Cog, name="Creation Commands"):
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_subcommand(base="voicecreator", name="create", guild_ids=server_ids,
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
    async def _create_channel_creator(self, context: SlashContext, name: str, category: discord.CategoryChannel = None,
                                      create_name: str = None, create_category: discord.CategoryChannel = None,
                                      user_limit: int = None):
        if not await self.bot.authenticate(context, ["manage_channels"]):
            return

        typed_params = {"category": [type(category), discord.CategoryChannel],
                        "create_category": [type(create_category), discord.CategoryChannel]}
        if not await self.bot.validate_arguments(context, typed_params):
            return

        new_channel_creator_channel = await context.guild.create_voice_channel(name=name, category=category)
        self.bot.channel_creators[new_channel_creator_channel.id] = ChannelCreator(self.bot,
                                                                                   new_channel_creator_channel,
                                                                                   create_name or name,
                                                                                   create_category or category,
                                                                                   user_limit)
        self.bot.dump_channel_creators()
        await context.send(
            f"Created new incremental channel creator {new_channel_creator_channel.mention} successfully.")

    @cog_ext.cog_subcommand(base="voicecreator", name="delete", guild_ids=server_ids,
                            description="Delete an incremental channel creator.",
                            options=[
                                create_option(name="channel",
                                              description="Incremental voice channel creator to delete",
                                              option_type=7,
                                              required=True)  #
                            ])
    async def _delete_channel_creator(self, context: SlashContext, channel: discord.VoiceChannel):
        if not await self.bot.authenticate(context, ["manage_channels"]):
            return

        if channel.id not in self.bot.channel_creators.keys():
            await context.send(f"{channel.mention} is not an incremental voice channel creator.")
        else:
            await self.bot.channel_creators[channel.id].delete()
            await context.send(f"Successfully deleted incremental voice channel creator with ID `{channel.id}`")

    @cog_ext.cog_subcommand(base="voicecreator", name="edit", guild_ids=server_ids,
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
    async def _edit_channel_creator(self, context: SlashContext, channel: discord.VoiceChannel, create_name: str = None,
                                    create_category: discord.CategoryChannel = False, user_limit: int = None):
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

    async def do_limit_command(self, context, size, message):
        temporary_channel = await self.get_owned_channel(context)
        if not temporary_channel:
            return
        if size == 0:
            size = None
        elif size < 0:
            await context.send("Cannot set negative channel size.")
            return

        success = await temporary_channel.edit(user_limit=size, forced=False)
        if success:
            await context.send(message % temporary_channel.channel.mention, size)
        else:
            await context.send(f"Please wait 60s to use that command again.")

    @cog_ext.cog_subcommand(base="voice", name="resize", guild_ids=server_ids,
                            description="Resize your voice channel.",
                            options=[
                                create_option(name="size",
                                              description="Number of users allowed in the channel",
                                              option_type=4,
                                              required=True)
                            ])
    async def _resize(self, context: SlashContext, size: int):
        await self.do_limit_command(context, size, "Successfully set %s size to `%s`")

    @cog_ext.cog_subcommand(base="voice", name="limit", guild_ids=server_ids,
                            description="Apply a user limit to your voice channel. Limit 0 removes the limit.",
                            options=[
                                create_option(name="size",
                                              description="Number of users allowed in the channel",
                                              option_type=4,
                                              required=True)
                            ])
    async def _limit(self, context: SlashContext, size: int):
        await self.do_limit_command(context, size, "Successfully limited %s to `%s`")

    @cog_ext.cog_subcommand(base="voice", name="unlimit", guild_ids=server_ids,
                            description="Unlimit your voice channel.")
    async def _unlimit(self, context):
        temporary_channel = await self.get_owned_channel(context)
        if temporary_channel:
            success = await temporary_channel.edit(user_limit=None, forced=False)
            if success:
                await context.send(f"Successfully unlimited {temporary_channel.channel.mention}")
            else:
                await context.send(f"Please wait 60s to use that command again.")

    @cog_ext.cog_subcommand(base="voice", name="rename", guild_ids=server_ids,
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
            if re.match(r"#\d+", name.lower().removeprefix(temporary_channel.creator.create_name.lower()).strip()):
                await context.send("Please don't use misleading channel names.")
                return
            success = await temporary_channel.edit(name=name, forced=False)
            if success:
                await context.send(f"Successfully renamed {temporary_channel.channel.mention}")
            else:
                await context.send(f"Please wait 60s to use that command again.")

    @cog_ext.cog_subcommand(base="voice", name="owner", guild_ids=server_ids,
                            description="Transfer ownership of your voice channel",
                            options=[
                                create_option(name="user",
                                              description="New owner of the channel",
                                              option_type=6,
                                              required=True)
                            ])
    async def _owner(self, context: SlashContext, user: discord.Member):
        temporary_channel = await self.get_owned_channel(context)
        if temporary_channel:
            if user.voice and user.voice.channel.id == temporary_channel.channel.id:
                await temporary_channel.edit(owner_user_id=user.id)
                await context.send(
                    f"Successfully transferred ownership of {temporary_channel.channel.mention} to {user.mention}")
            else:
                await context.send(
                    f"{user.mention} is not in {temporary_channel.channel.mention}, ownership not transferred.")


bot.add_cog(VoiceHandler(bot))
bot.add_cog(HighLevel(bot))
bot.add_cog(CreationCommands(bot))
bot.add_cog(OwnedChannelCommands(bot))

bot.run(token)
