import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("DISCORD_TOKEN")
server_id = int(os.getenv("DISCORD_SERVER_ID"))


class SquadsBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.channel_creators = []
        super().__init__(*args, **kwargs)


bot = SquadsBot(command_prefix=">", case_insensitive=True)


class ChannelCreator:
    def __init__(self, bot, channel_id, create_name, create_category_id, create_userlimit=0):
        self.bot = bot
        self.channel = bot.get_channel(channel_id)
        self.create_name = create_name
        self.create_category = bot.get_channel(create_category_id)
        self.create_userlimit = create_userlimit


class TemporaryChannel:
    def __init__(self, category_id, name, userlimit=0):
        pass


@bot.event
async def on_ready():
    guild = discord.utils.get(bot.guilds, id=server_id)
    if not guild:
        print("Failed to connect to server defined in .ENV!")
        return

    print(f'{bot.user} has connected to Discord! Server name: {guild.name}, ID: {guild.id}')
    with open("channel-creators.json", "r") as readfile:
        channel_creators_data = json.load(readfile)


bot.run(token)
