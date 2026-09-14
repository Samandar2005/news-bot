"""Language selection keyboard."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

_LANGUAGE_BUTTONS = [
    ("uz", "🇺🇿 O'zbekcha"),
    ("ru", "🇷🇺 Русский"),
    ("en", "🇬🇧 English"),
]


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"lang:{code}")]
            for code, label in _LANGUAGE_BUTTONS
        ]
    )
