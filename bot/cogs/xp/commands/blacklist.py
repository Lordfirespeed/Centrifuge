from typing import Optional
import discord
from discord import app_commands
from bot.common import extension_setup
from bot.exceptions import standard_error_handling
from bot.cogs.xp.main import XPCommandCog, ExperienceMember


class BlacklistChannels(XPCommandCog):
    pass


setup = extension_setup(BlacklistChannels)
