import discord
from discord.ext import commands
from bot.main import basic_extension_setup
from bot.cogs.xp.main import XPCog


class XPListeners(XPCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def cog_load(self) -> None:
        super().cog_load()

    def award_reply_xp(self, message: discord.Message) -> None:
        try:
            assert message.reference is not None
            assert message.flags.is_crossposted is False
            assert message.reference.cached_message is not None
        except AssertionError:
            return

        self.handler.add_experience(message.reference.cached_message.author.id, self.handler.reward_xp_reply)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        try:
            assert payload.member is not None
            assert payload.member.bot is False
            assert payload.member.guild.id == self.bot.guild.id
        except AssertionError:
            return

        self.handler.add_experience(payload.member.id, self.handler.reward_xp_react)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            assert message.author.bot is False
            assert type(message.author) is discord.Member
            assert message.author.guild.id == self.bot.guild.id
            assert message.type == discord.Message.default
        except AssertionError:
            return

        self.handler.add_experience(message.author.id, self.handler.reward_xp_message)

        self.award_reply_xp(message)


setup = basic_extension_setup(XPListeners)
