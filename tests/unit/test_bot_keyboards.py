"""Unit tests for keyboard builders — pure functions, no network involved."""

from __future__ import annotations

from bot.keyboards.interests import interests_keyboard
from bot.keyboards.language import language_keyboard
from bot.services.backend_client import CategoryDTO


def test_language_keyboard_has_three_buttons_with_correct_callbacks():
    kb = language_keyboard()
    all_buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert len(all_buttons) == 3
    callback_data = {btn.callback_data for btn in all_buttons}
    assert callback_data == {"lang:uz", "lang:ru", "lang:en"}


def _sample_categories() -> list[CategoryDTO]:
    return [
        CategoryDTO(
            id=1, key="tech", name_en="Technology", name_ru="Технологии", name_uz="Texnologiya"
        ),
        CategoryDTO(id=2, key="ai", name_en="AI", name_ru="ИИ", name_uz="SI"),
        CategoryDTO(id=3, key="space", name_en="Space", name_ru="Космос", name_uz="Kosmos"),
    ]


def test_interests_keyboard_marks_selected_categories():
    kb = interests_keyboard(_sample_categories(), selected_ids={2}, language="en")
    all_buttons = [btn for row in kb.inline_keyboard for btn in row]
    # 3 category buttons + 1 Done button
    assert len(all_buttons) == 4

    ai_button = next(b for b in all_buttons if b.callback_data == "interest:2")
    tech_button = next(b for b in all_buttons if b.callback_data == "interest:1")
    assert ai_button.text.startswith("✅")
    assert tech_button.text.startswith("▫️")


def test_interests_keyboard_uses_requested_language():
    kb = interests_keyboard(_sample_categories(), selected_ids=set(), language="ru")
    all_buttons = [btn for row in kb.inline_keyboard for btn in row]
    tech_button = next(b for b in all_buttons if b.callback_data == "interest:1")
    assert "Технологии" in tech_button.text


def test_interests_keyboard_always_has_done_button_last():
    kb = interests_keyboard(_sample_categories(), selected_ids=set(), language="en")
    last_row = kb.inline_keyboard[-1]
    assert len(last_row) == 1
    assert last_row[0].callback_data == "interests:done"
