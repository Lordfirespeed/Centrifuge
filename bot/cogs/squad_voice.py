from typing import Optional

import discord
import re
from discord import app_commands, utils
from discord.ext import commands
from collections import defaultdict
import json
import asyncio
from bot.main import GuildBot, basic_extension_setup


class SquadVoice(commands.Cog):
    def __init__(self, bot: GuildBot):
        self.bot = bot
        self.channel_creators = {}
        self.all_temporary_channels = {}

        self.voice_creator_commands: app_commands.Group = None
        self.created_channel_commands: app_commands.Group = None

    async def cog_load(self) -> None:
        self.create_command_groups()
        self.register_voice_creator_commands_to_group()

        await self.load_from_json()

    def cog_unload(self) -> None:
        if self.channel_creators:
            self.dump_channel_creators()
        if self.all_temporary_channels:
            self.dump_temporary_channels()

    def dump_channel_creators(self):
        data = [{"channel_id": channel_creator.channel.id,
                 "create_name": channel_creator.create_name,
                 "create_category_id": channel_creator.create_category.id if channel_creator.create_category else None,
                 "create_user_limit": channel_creator.create_user_limit}
                for channel_creator in self.channel_creators.values()]
        with open("data/squad_voice/channel-creators.json", "w") as writefile:
            json.dump(data, writefile, indent=2)

    def dump_temporary_channels(self):
        data = [{"channel_id": temporary_channel.channel.id,
                 "index": temporary_channel.index,
                 "creator": temporary_channel.creator.channel.id}
                for temporary_channel in self.all_temporary_channels.values()]
        with open("data/squad_voice/temporary-channels.json", "w") as writefile:
            json.dump(data, writefile, indent=2)

    async def load_from_json(self):
        with open("data/squad_voice/channel-creators.json", "r") as readfile:
            channel_creators_data = json.load(readfile)

        self.channel_creators = {}
        self.all_temporary_channels = {}

        for channel_creator_data in channel_creators_data:
            try:
                channel_creator_data["channel"] = await self.bot.fetch_channel(channel_creator_data["channel_id"])
            except discord.NotFound:
                continue
            del channel_creator_data["channel_id"]
            if channel_creator_data["create_category_id"]:
                try:
                    channel_creator_data["create_category"] = await self.bot.fetch_channel(channel_creator_data["create_category_id"])
                except discord.NotFound:
                    channel_creator_data["create_category"] = channel_creator_data["channel"].category
            else:
                channel_creator_data["create_category"] = None
            del channel_creator_data["create_category_id"]
            channel_creator = ChannelCreator(self, **channel_creator_data)
            self.channel_creators[channel_creator.channel.id] = channel_creator

        with open("data/squad_voice/temporary-channels.json", "r") as readfile:
            temporary_channels_data = json.load(readfile)
        for temporary_channel_data in temporary_channels_data:
            try:
                channel = await self.bot.fetch_channel(temporary_channel_data["channel_id"])
            except discord.NotFound:
                continue
            if len(channel.voice_states) == 0:
                await channel.delete()
            elif channel and temporary_channel_data["creator"] in self.channel_creators.keys():
                channel_creator = self.channel_creators[temporary_channel_data["creator"]]
                temporary_channel = TemporaryChannel(self, channel_creator,
                                                     temporary_channel_data["index"], channel_creator.create_category,
                                                     channel_creator.create_name, channel_creator.create_user_limit,
                                                     channel)
                await temporary_channel.ready.wait()
                channel_creator.register_temporary_channel(temporary_channel, dump=False)

        self.dump_temporary_channels()
        self.dump_channel_creators()

    async def get_temporary_channel(self, interaction: discord.Interaction):
        voice_state = interaction.user.voice
        if not voice_state:
            await interaction.response.send_message("You are not in a voice channel.", ephemeral=True)
            return None

        in_channel = voice_state.channel
        if in_channel.id not in self.all_temporary_channels.keys():
            await interaction.response.send_message("You are not in a temporary voice channel.", ephemeral=True)
            return None

        return in_channel

    async def do_limit_command(self, interaction: discord.Interaction, size, message):
        temporary_channel = await self.get_temporary_channel(interaction)
        if not temporary_channel:
            return
        if size == 0:
            size = None
        elif size < 0:
            await interaction.response.send_message("Cannot set negative channel size.", ephemeral=True)
            return

        success = await temporary_channel.edit(user_limit=size, forced=False)
        if not success:
            await interaction.response.send_messaged(f"Please wait 60s to use that command again.", ephemeral=True)
            return

        await interaction.response.send_message(message % (temporary_channel.channel.mention, size or "unlimited"))

    async def check_joined_creator_channel(self, user, channel_moved_to):
        if channel_moved_to.channel is None:
            return

        try:
            joined_channel_creator = self.channel_creators[channel_moved_to.channel.id]
        except KeyError:
            return

        new_temporary_channel = await joined_channel_creator.create_temporary_channel()
        await new_temporary_channel.ready.wait()
        await user.move_to(new_temporary_channel.channel)

    async def check_left_temporary_channel(self, channel_moved_from):
        if channel_moved_from.channel is None:
            return

        try:
            left_temp_channel = self.all_temporary_channels[channel_moved_from.channel.id]
        except KeyError:
            return

        voice_states = channel_moved_from.channel.voice_states
        if len(voice_states) == 0:
            await left_temp_channel.delete()

    @commands.Cog.listener()
    async def on_voice_state_update(self, user, before, after):
        if before.channel == after.channel:
            return
        await self.check_joined_creator_channel(user, after)
        await self.check_left_temporary_channel(before)

    def create_command_groups(self):
        self.voice_creator_commands = app_commands.Group(name="voicecreator",
                                                         description="Incremental Channel Creator Commands",
                                                         guild_only=True,
                                                         default_permissions=discord.Permissions(manage_channels=True))
        self.created_channel_commands = app_commands.Group(name="voice",
                                                           description="Created Channel Commands",
                                                           guild_only=True)

        self.__cog_app_commands__.append(self.voice_creator_commands)
        self.__cog_app_commands__.append(self.created_channel_commands)

    def register_voice_creator_commands_to_group(self):
        @self.voice_creator_commands.command(name="create")
        @app_commands.rename(category="creator_category",
                             create_name="created_name",
                             create_category="created_category")
        async def _create_channel_creator(interaction: discord.Interaction,
                                          name: str,
                                          category: Optional[discord.CategoryChannel] = None,
                                          create_name: Optional[str] = None,
                                          create_category: Optional[discord.CategoryChannel] = None,
                                          user_limit: Optional[int] = None):
            """Create an incremental channel creator.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            name : str
                Name of channel creator.
            category : Optional[discord.CategoryChannel]
                Category to place creator into.
            create_name : Optional[str]
                Name of created temporary channels.
            create_category : Optional[discord.CategoryChannel]
                Category of created temporary channels.
            user_limit : Optional[int]
                User limit of created temporary channels.
            """
            new_channel_creator_channel = await interaction.guild.create_voice_channel(name=name, category=category)
            self.channel_creators[new_channel_creator_channel.id] = ChannelCreator(self,
                                                                                   new_channel_creator_channel,
                                                                                   create_name or name,
                                                                                   create_category or category,
                                                                                   user_limit)
            self.dump_channel_creators()
            await interaction.response.send_message(
                f"Created new incremental channel creator {new_channel_creator_channel.mention} successfully.")

        @self.voice_creator_commands.command(name="delete")
        async def _delete_channel_creator(interaction: discord.Interaction,
                                          channel: discord.VoiceChannel):
            """Delete an incremental channel creator.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            channel : discord.VoiceChannel
                Incremental voice channel creator to delete.
            """

            if channel.id not in self.channel_creators.keys():
                await interaction.response.send_message(
                    f"{channel.mention} is not an incremental voice channel creator.")
                return

            await self.channel_creators[channel.id].delete()
            await interaction.response.send_message(
                f"Successfully deleted incremental voice channel creator with ID `{channel.id}`")

        @self.voice_creator_commands.command(name="edit")
        @app_commands.rename(create_name="created_name",
                             create_category="created_category")
        async def _edit_channel_creator(interaction: discord.Interaction,
                                        channel: discord.VoiceChannel,
                                        create_name: Optional[str] = None,
                                        create_category: Optional[discord.CategoryChannel] = None,
                                        user_limit: Optional[int] = None):
            """Edit an incremental channel creator.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            channel : discord.VoiceChannel
                Incremental voice channel creator to edit.
            create_name : Optional[str]
                Name of created temporary channels.
            create_category : Optional[discord.CategoryChannel]
                Category of created temporary channels.
            user_limit : Optional[int]
                User limit of created temporary channels.
            """
            if channel.id not in self.channel_creators.keys():
                await interaction.response.send_message(f"{channel.mention} is not an incremental voice channel creator.")
                return

            channel_creator = self.channel_creators[channel.id]
            await channel_creator.edit(create_name, create_category, user_limit)
            await interaction.response.send_message(
                f"Successfully edited incremental channel creator {channel_creator.channel.mention}")

    def register_created_channel_commands_to_group(self):
        @self.created_channel_commands.command(name="resize")
        async def _resize(interaction: discord.Interaction,
                          size: int):
            """Resize your voice channel.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            size : int
                Number of users allowed in the channel.
            """
            await self.do_limit_command(interaction, size, "Successfully set %s size to `%s`")

        @self.created_channel_commands.command(name="limit")
        async def _limit(interaction: discord.Interaction,
                         limit: int):
            """Apply a user limit to your voice channel. 0 removes the limit.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            limit : int
                Number of users allowed in the channel.
            """
            await self.do_limit_command(interaction, limit, "Successfully limited %s to `%s`")

        @self.created_channel_commands.command(name="unlimit")
        async def _unlimit(interaction: discord.Interaction):
            """Unlimit your voice channel."

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            """
            temporary_channel = await self.get_temporary_channel(interaction)
            if not temporary_channel:
                await interaction.response.send_message(f"You are not in a temporary voice channel.", ephemeral=True)
                return

            success = await temporary_channel.edit(user_limit=None, forced=False)
            if not success:
                await interaction.response.send_message(f"Please wait 60s to use that command again.", ephemeral=True)
                return

            await interaction.response.send_message(f"Successfully unlimited {temporary_channel.channel.mention}")

        @self.created_channel_commands.command(name="rename")
        async def _rename(self, interaction: discord.Interaction,
                          name: str):
            """Rename your voice channel.

            Parameters
            ----------
            interaction : discord.Interaction
                The interaction object.
            name : str
                New name of the channel.
            """
            temporary_channel = await self.get_temporary_channel(interaction)
            if not temporary_channel:
                return

            if re.match(r"#\d+", name.lower().removeprefix(temporary_channel.creator.create_name.lower()).strip()):
                await interaction.response.send_message("Please don't use misleading channel names.", ephemeral=True)
                return

            success = await temporary_channel.edit(name=name, forced=False)
            if not success:
                await interaction.response.send_message(f"Please wait 60s to use that command again.", ephemeral=True)
                return

            await interaction.response.send_message(f"Successfully renamed {temporary_channel.channel.mention}")


class ChannelCreator:
    def __init__(self, cog: SquadVoice, channel: discord.VoiceChannel, create_name: str,
                 create_category: discord.CategoryChannel = None, create_user_limit: int = None):
        self.cog = cog
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
        self.cog.dump_temporary_channels()
        del cache

        await self.channel.delete()

        del self.cog.channel_creators[self.channel.id]
        self.cog.dump_channel_creators()

    def get_minimum_unused_index(self):
        if len(self.used_indexes) == 0:
            return 1
        minval, maxval = min(self.used_indexes), max(self.used_indexes)
        if len(self.used_indexes) < maxval - minval + 1:
            return min(set(range(minval, maxval + 1)) - self.used_indexes)
        else:
            return len(self.used_indexes) + 1

    async def create_temporary_channel(self):
        index = self.get_minimum_unused_index()
        temporary_channel = TemporaryChannel(self.cog, self, index, self.create_category,
                                             self.create_name, self.create_user_limit)
        await temporary_channel.ready.wait()
        self.register_temporary_channel(temporary_channel)

        return temporary_channel

    def register_temporary_channel(self, temporary_channel, dump=True):
        self.used_indexes.add(temporary_channel.index)
        self.created_channels[temporary_channel.channel.id] = temporary_channel
        self.cog.all_temporary_channels[temporary_channel.channel.id] = temporary_channel
        if dump:
            self.cog.dump_temporary_channels()

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
    def __init__(self, cog: SquadVoice, creator: ChannelCreator, index: int,
                 category: discord.CategoryChannel, name: str, user_limit: int = None,
                 channel: discord.VoiceChannel = None):
        self.cog = cog
        self.creator = creator
        self.index = index
        self.name = name
        self.channel = channel
        self.category = category
        self.user_limit = user_limit
        self.edited_recently = defaultdict(lambda: False)
        self.ready = asyncio.Event()

        loop = asyncio.get_event_loop()
        loop.create_task(self.ready_up())

    async def ready_up(self):
        to_name = self.make_name()
        if not self.channel:
            guild = self.creator.channel.guild
            try:
                assert type(guild) is discord.Guild
            except AssertionError:
                guild = utils.get(self.cog.bot.guilds, id=guild.id)

            try:
                self.channel = await guild.create_voice_channel(to_name, category=self.category, user_limit=self.user_limit)
            except discord.HTTPException as error:
                if "Category does not exist" in str(error):
                    self.creator.create_category = self.creator.channel.category
                    self.category = self.creator.create_category
                    self.channel = await guild.create_voice_channel(to_name, category=self.category, user_limit=self.user_limit)
                    self.cog.dump_channel_creators()
                else:
                    raise error

        self.ready.set()

    def make_edit_timer(self, time: int, property_name: str):
        async def _job():
            await asyncio.sleep(time)
            self.edited_recently[property_name] = False

        self.edited_recently[property_name] = bool(asyncio.create_task(_job()))

    def make_name(self):
        if self.name == self.creator.create_name:
            return f"{self.name} #{str(self.index)}"
        else:
            return self.name

    async def delete(self, dump=True):

        await self.channel.delete()

        self.creator.used_indexes.remove(self.index)

        del self.creator.created_channels[self.channel.id]
        del self.cog.all_temporary_channels[self.channel.id]
        if dump:
            self.cog.dump_temporary_channels()

    async def edit(self, index: int = None, category: discord.CategoryChannel = False, name: str = None,
                   user_limit: int = False, forced=True):
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
            await self.channel.edit(name=self.make_name(), category=self.category,
                                    user_limit=self.user_limit if self.user_limit is not None else 0)
        return True


setup = basic_extension_setup(SquadVoice)
