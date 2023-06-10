from os import getenv, getcwd
from dotenv import load_dotenv
import discord
import logging
from .common import GuildBot


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
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(filename="botlog.log", mode="w"),
            logging.StreamHandler()
        ]
    )
    logging.debug(f"CWD: {getcwd()}")
    main()
