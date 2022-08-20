from __future__ import annotations

import logging
import json
from random import random, choice
from os import getcwd
from html2image import Html2Image
from contextlib import closing as contextlib_closing
from urllib.request import pathname2url
from bot.cogs.xp.main import ExperienceMember, XPHandling
from enum import Enum
from pathlib import Path


html_renderer = Html2Image(size=(1024, 308))


class UserDisplayCardType(Enum):
    DisplayProgress = "show_user.html"
    LevelUp = "level_up.html"


class DeletingFile:
    def __init__(self, file: Path):
        self.file = file

    def close(self):
        self.file.unlink(missing_ok=True)


class ExtraCardFields:
    __slots__ = ["party_emoji",
                 "rare_party_emoji"]

    def __init__(self):
        self.party_emoji: [str] = []
        self.rare_party_emoji: dict[str, float] = {}
        self.load_party_emoji()

    @staticmethod
    def previous_level_requirement(card: UserDisplayCard):
        return XPHandling.format_xp_quantity(card.member.get_current_level_requirement())

    @staticmethod
    def next_level_requirement(card: UserDisplayCard):
        return XPHandling.format_xp_quantity(card.member.get_next_level_requirement())

    @staticmethod
    def level_progress_percentage(card: UserDisplayCard):
        return round(card.member.get_level_progress() * 100, 1)

    @staticmethod
    def user_colour(card: UserDisplayCard):
        colour = card.member.colour
        if colour.value == 0:
            return "255,255,255"
        return str(colour.to_rgb())[1:-1]

    def load_party_emoji(self):
        with open("data/xp/party_emojis.json") as party_emoji_file:
            try:
                party_emoji_data = json.load(party_emoji_file)
            except json.decoder.JSONDecodeError:
                return

        self.party_emoji = party_emoji_data["main"]
        self.rare_party_emoji = party_emoji_data["rare"]

    def party(self, *args, **kwargs):
        random_rare_selected = random()
        cumulative_rare_chance = 0
        for rare_emoji, rare_chance in self.rare_party_emoji.items():
            cumulative_rare_chance += rare_chance
            if random_rare_selected < cumulative_rare_chance:
                return rare_emoji

        return choice(self.party_emoji)


class UserDisplayCard:
    global html_renderer
    temp_directory = Path("data/xp/temp_cards/")
    card_directory = Path("data/xp/html_cards/")
    extra_fields_generator = ExtraCardFields()
    extra_fields = {UserDisplayCardType.DisplayProgress: {"previous_level_requirement": extra_fields_generator.previous_level_requirement,
                                                          "next_level_requirement": extra_fields_generator.next_level_requirement,
                                                          "level_progress_percentage": extra_fields_generator.level_progress_percentage},
                    UserDisplayCardType.LevelUp: {"party1": extra_fields_generator.party,
                                                  "party2": extra_fields_generator.party}
                    }

    def __init__(self, member: ExperienceMember, card_type: UserDisplayCardType):
        self.member = member
        self.card_type = card_type
        self._template_filepath = Path(self.card_directory, self.card_type.value)
        unique_card_name = f"{self.card_type.name}{self.member.id}"
        self._temporary_html_filepath = Path(self.temp_directory, f"{unique_card_name}.html")
        self._temporary_png_filepath = Path(self.temp_directory, f"{unique_card_name}.png")

        html_renderer.output_path = self.temp_directory

    def _read_card_template(self) -> str:
        with open(self._template_filepath) as template_html_file:
            return template_html_file.read()

    def _format_card_template(self, template_html_string: str) -> str:
        data = {
            "username": self.member.display_name,
            "discriminator": self.member.discriminator,
            "profile_url": self.member.display_avatar,
            "level": self.member.level,
            "rank": self.member.rank,
            "xp_quantity": XPHandling.format_xp_quantity(self.member.xp_quantity),
            "user_colour": ExtraCardFields.user_colour(self)
        }

        for field_name, field_factory in self.extra_fields[self.card_type].items():
            data[field_name] = field_factory(self)

        return template_html_string.format(**data)

    def _write_html_card(self, formatted_html_string: str) -> DeletingFile:
        with open(self._temporary_html_filepath, "w") as temporary_html_file:
            temporary_html_file.write(formatted_html_string)
        return DeletingFile(self._temporary_html_filepath)

    def _get_html_card_file_url(self):
        return "file://" + pathname2url(str(Path(getcwd(), self._temporary_html_filepath)))

    def _render_png_card(self) -> DeletingFile:
        html_renderer.screenshot(url=self._get_html_card_file_url(), save_as=self._temporary_png_filepath.name)
        return DeletingFile(self._temporary_png_filepath)

    def get_png_card(self) -> contextlib_closing[DeletingFile]:
        template_string = self._read_card_template()
        formatted_template_string = self._format_card_template(template_string)
        with contextlib_closing(self._write_html_card(formatted_template_string)):
            return contextlib_closing(self._render_png_card())


def setup(bot) -> None:
    pass
