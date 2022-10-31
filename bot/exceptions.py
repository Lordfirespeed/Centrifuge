import logging
from typing import Callable
from functools import wraps
from discord import Interaction as DiscordInteraction, app_commands


def standard_error_handling(method):
    @wraps(method)
    async def magic(interaction: DiscordInteraction, *args, **kwargs):
        try:
            await method(interaction, *args, **kwargs)
        except CustomErrorBase as error:
            await interaction.response.send_message(error.message, ephemeral=True)
        except app_commands.CommandOnCooldown as error:
            await interaction.response.send_message(str(error), ephemeral=True)
        except Exception as error:
            logging.exception(error)
            await interaction.response.send_message("Unexpected error occurred, please try again.", ephemeral=True)
    return magic


class CustomErrorBase(Exception):
    def __init__(self, message):
        self.message = message


class ConflictError(CustomErrorBase):
    pass


class NotFoundError(CustomErrorBase):
    pass


class ValueErrorWithMessage(CustomErrorBase):
    pass
