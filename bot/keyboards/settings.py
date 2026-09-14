"""Notification settings toggle keyboard.

No FSM state needed (unlike interests' choosing_interests state) — each
button press is a complete, standalone action: toggle, tell the backend,
redraw. There's no "still deciding, not yet confirmed" phase to track.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.locales.strings import t


def settings_keyboard(
    morning_enabled: bool, evening_enabled: bool, language: str
) -> InlineKeyboardMarkup:
    morning_mark = "✅" if morning_enabled else "▫️"
    evening_mark = "✅" if evening_enabled else "▫️"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{morning_mark} {t(language, 'morning_digest_label')}",
                    callback_data="settings:toggle_morning",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{evening_mark} {t(language, 'evening_digest_label')}",
                    callback_data="settings:toggle_evening",
                )
            ],
        ]
    )
