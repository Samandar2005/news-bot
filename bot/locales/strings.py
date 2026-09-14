"""Localized bot UI strings.

A plain nested dict rather than a full i18n library (gettext/fluent) —
the string set is small and static for the MVP; worth revisiting once the
bot's copy grows past what's comfortable to eyeball in one file.
"""

from __future__ import annotations

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "welcome_choose_language": (
            "👋 Welcome! Please choose your language to get started."
        ),
        "language_set": "Language set to English.",
        "choose_interests": (
            "Great! Now pick the topics you're interested in — tap to "
            "select or deselect, then press Done."
        ),
        "interests_saved_onboarding": (
            "✅ All set! You'll get your first digest at the next "
            "scheduled time (07:00 / 19:00). Use /news anytime for the "
            "latest, or /settings to manage notifications."
        ),
        "interests_saved": "✅ Your interests have been updated.",
        "interests_empty_warning": (
            "You haven't selected any topics yet — tap at least one, "
            "then press Done."
        ),
        "main_menu": (
            "Main menu:\n"
            "/news — latest digest now\n"
            "/interests — change interests\n"
            "/language — change language\n"
            "/settings — notification settings"
        ),
        "done_button": "✅ Done",
        "error_generic": "Something went wrong on our end — please try again in a moment.",
        "settings_title": "🔔 Notification settings",
        "morning_digest_label": "Morning digest (07:00)",
        "evening_digest_label": "Evening digest (19:00)",
        "settings_updated": "✅ Updated.",
        "news_no_content": "No news to show right now — check back soon!",
    },
    "ru": {
        "welcome_choose_language": (
            "👋 Добро пожаловать! Пожалуйста, выберите язык, чтобы начать."
        ),
        "language_set": "Язык изменён на русский.",
        "choose_interests": (
            "Отлично! Теперь выберите интересующие вас темы — нажмите, "
            "чтобы выбрать или убрать, затем нажмите «Готово»."
        ),
        "interests_saved_onboarding": (
            "✅ Готово! Вы получите первую подборку в ближайшее плановое "
            "время (07:00 / 19:00). Используйте /news в любой момент, "
            "или /settings для настройки уведомлений."
        ),
        "interests_saved": "✅ Ваши интересы обновлены.",
        "interests_empty_warning": (
            "Вы пока не выбрали ни одной темы — выберите хотя бы одну, "
            "затем нажмите «Готово»."
        ),
        "main_menu": (
            "Главное меню:\n"
            "/news — последняя подборка сейчас\n"
            "/interests — изменить интересы\n"
            "/language — изменить язык\n"
            "/settings — настройки уведомлений"
        ),
        "done_button": "✅ Готово",
        "error_generic": "Что-то пошло не так. Пожалуйста, попробуйте ещё раз.",
        "settings_title": "🔔 Настройки уведомлений",
        "morning_digest_label": "Утренняя подборка (07:00)",
        "evening_digest_label": "Вечерняя подборка (19:00)",
        "settings_updated": "✅ Обновлено.",
        "news_no_content": "Пока нет новостей — загляните позже!",
    },
    "uz": {
        "welcome_choose_language": (
            "👋 Xush kelibsiz! Boshlash uchun tilni tanlang."
        ),
        "language_set": "Til o'zbekchaga o'zgartirildi.",
        "choose_interests": (
            "Ajoyib! Endi qiziqtirgan mavzularingizni tanlang — tanlash "
            "yoki bekor qilish uchun bosing, so'ng «Tayyor»ni bosing."
        ),
        "interests_saved_onboarding": (
            "✅ Tayyor! Birinchi yangiliklar to'plamini keyingi rejalashtirilgan "
            "vaqtda olasiz (07:00 / 19:00). /news orqali istalgan vaqtda so'nggi "
            "yangiliklarni, /settings orqali bildirishnomalarni boshqaring."
        ),
        "interests_saved": "✅ Qiziqishlaringiz yangilandi.",
        "interests_empty_warning": (
            "Siz hali birorta mavzu tanlamadingiz — kamida bittasini tanlang, "
            "so'ng «Tayyor»ni bosing."
        ),
        "main_menu": (
            "Asosiy menyu:\n"
            "/news — hozirgi so'nggi yangiliklar\n"
            "/interests — qiziqishlarni o'zgartirish\n"
            "/language — tilni o'zgartirish\n"
            "/settings — bildirishnoma sozlamalari"
        ),
        "done_button": "✅ Tayyor",
        "error_generic": "Xatolik yuz berdi — birozdan so'ng qayta urinib ko'ring.",
        "settings_title": "🔔 Bildirishnoma sozlamalari",
        "morning_digest_label": "Ertalabki to'plam (07:00)",
        "evening_digest_label": "Kechki to'plam (19:00)",
        "settings_updated": "✅ Yangilandi.",
        "news_no_content": "Hozircha yangilik yo'q — birozdan so'ng qayta urinib ko'ring!",
    },
}


def t(language: str, key: str) -> str:
    """Look up a localized string, falling back to English then the key
    itself if something is missing rather than raising mid-conversation."""
    return _STRINGS.get(language, _STRINGS["en"]).get(key) or _STRINGS["en"].get(key, key)
