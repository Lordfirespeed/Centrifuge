import discord
import logging
from discord.ext import commands, tasks
from bot.common import GuildBot, extension_setup
from bot.cogs.xp.main import XPCog
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VoiceXP(XPCog):
    def __init__(self, bot: GuildBot):
        super(VoiceXP, self).__init__(bot)
        self.member_ids_connection_times: dict[int, datetime] = {}

    async def cog_load(self) -> None:
        await super(VoiceXP, self).cog_load()
        self.do_voice_xp_additions.start()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        logger.debug("Saw a voice state update")
        self.on_connect(member, before, after)
        self.on_disconnect(member, before, after)

    def on_connect(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is not None:
            return
        if not (after and after.channel):
            return

        logger.debug(f"Saw {member.mention} join a voice channel")
        self.member_ids_connection_times[member.id] = datetime.now()

    def on_disconnect(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not (before and before.channel):
            return
        if after.channel is not None:
            return

        logger.debug(f"Saw {member.mention} leave a voice channel")
        try:
            last_addition_time = self.member_ids_connection_times.pop(member.id)
        except KeyError:
            return

        self.do_one_addition(member.id, last_addition_time)

    def do_one_addition(self, member_id: int, last_addition_time: datetime):
        logger.debug(f"Adding voice XP to <@{member_id}>")
        time_to_add_xp_for = datetime.now() - last_addition_time
        minutes_to_add_xp_for = min((time_to_add_xp_for.total_seconds() / 60), 2)
        if minutes_to_add_xp_for < 0:
            return
        self.handler.add_experience_from_action(member_id, self.handler.reward_xp_voice * minutes_to_add_xp_for)

    @tasks.loop(seconds=60.0)
    async def do_voice_xp_additions(self):
        time_now = datetime.now()
        for connected_member_id, connected_at in self.member_ids_connection_times.items():
            self.member_ids_connection_times[connected_member_id] = time_now
            self.do_one_addition(connected_member_id, connected_at)

    @do_voice_xp_additions.before_loop
    async def before_do_experience_additions(self):
        await self.bot.wait_until_ready()


setup = extension_setup(VoiceXP)
