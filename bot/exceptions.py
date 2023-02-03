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
        except NotImplementedError:
            await interaction.response.send_message(f"This command has not been implemented - contact <@290259615059279883>")
        except Exception as error:
            logging.exception(error)
            await interaction.response.send_message("Unexpected error occurred, please try again.", ephemeral=True)
    return magic


class CustomErrorBase(Exception):
    def __init__(self, message=None):
        if message is not None:
            self.message = message


class ConflictError(CustomErrorBase):
    message = "You tried to do something that would cause a conflict."


class ContextError(CustomErrorBase):
    message = "You can't use this command right now."


class NotFoundError(CustomErrorBase):
    message = "Whatever you're looking for, it's not here!"


class ValueErrorWithMessage(CustomErrorBase):
    message = "Something was wrong with the parameters you provided."
