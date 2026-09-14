"""Interest multi-select keyboard.

One button per category (toggled ✅/▫️ by tapping — see
bot/handlers/interests.py), two per row, plus a Done button on its own row.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.locales.strings import t
from bot.services.backend_client import CategoryDTO


def interests_keyboard(
    categories: list[CategoryDTO], selected_ids: set[int], language: str
) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []
    for category in categories:
        mark = "✅" if category.id in selected_ids else "▫️"
        buttons.append(
            InlineKeyboardButton(
                text=f"{mark} {category.localized_name(language)}",
                callback_data=f"interest:{category.id}",
            )
        )

    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append(
        [InlineKeyboardButton(text=t(language, "done_button"), callback_data="interests:done")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
