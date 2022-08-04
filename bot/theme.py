from typing import Optional
from dataclasses import dataclass
import discord


@dataclass
class EmbedTheme:
    """Dataclass representing a theme that can be applied to discord embeds."""
    identifier: str
    colour: discord.Colour

    author_name: Optional[str] = None
    author_url: Optional[str] = None
    author_icon_url: Optional[str] = None

    thumbnail_url: Optional[str] = None

    footer_text: Optional[str] = None
    footer_icon_url: Optional[str] = None

    def apply_colour(self, embed: discord.Embed) -> None:
        embed.colour = self.colour

    def apply_author(self, embed: discord.Embed) -> None:
        if self.author_name is None:
            embed.remove_author()
            return

        embed.set_author(name=self.author_name, url=self.author_url, icon_url=self.author_icon_url)

    def apply_thumbnail(self, embed: discord.Embed) -> None:
        embed.set_thumbnail(url=self.thumbnail_url)

    def apply_footer(self, embed: discord.Embed) -> None:
        if self.footer_text is None:
            embed.remove_footer()
            return

        embed.set_footer(text=self.footer_text, icon_url=self.footer_icon_url)

    def apply_theme(self, embed: discord.Embed) -> None:
        self.apply_colour(embed)
        self.apply_author(embed)
        self.apply_thumbnail(embed)
        self.apply_footer(embed)



