"""Rule-based categorization (spec Phase 3, stage 5 / Phase 5: categorization
is Hybrid — rules primary, LLM fallback for ambiguous cases). The LLM
fallback is M10's job; this module is the "rules" half on its own.

**The Technology/Programming/AI/Software-Development overlap** (called out
explicitly in spec Phase 3 stage 5 as an edge case) is handled by keyword
*specificity* rather than trying to make the categories mutually exclusive
at the keyword level: CATEGORY_KEYWORDS is ordered from most specific
(python) to least specific (world_news), and ties in score are broken by
that order — `max()` keeps the first-encountered maximum for equal scores,
so "PyPI announces a new Python release" scores under `python` even though
it would also weakly match `programming` and `technology`.

Only English and Russian keyword sets exist right now, matching the two
languages our seeded sources actually publish in (spec Phase 3 stage 1 —
see backend/db/seed_sources.py's documented gap on Uzbek sources). An
article in an unsupported language, or one that matches nothing, returns
None — the caller (pipeline/collectors/ingest.py) falls back to the
source's configured default_category_id, which is correct far more often
than a forced guess would be.
"""

from __future__ import annotations

import re

# Ordered most- to least-specific on purpose — see module docstring.
CATEGORY_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "python": {
        "en": [
            "python programming",
            "python developer",
            "python 3",
            "pypi",
            "django",
            "flask",
            "cpython",
            "pip install",
        ],
        "ru": ["python", "django", "flask", "cpython", "разработчик python"],
    },
    "artificial_intelligence": {
        "en": [
            "artificial intelligence",
            "machine learning",
            "neural network",
            "large language model",
            "chatbot",
            "generative ai",
            "deep learning",
            "openai",
            "llm",
            "pytorch",
            "chatgpt",
        ],
        "ru": [
            "искусственный интеллект",
            "машинное обучение",
            "нейронная сеть",
            "языковая модель",
            "чат-бот",
            "генеративный ии",
            "глубокое обучение",
        ],
    },
    "cybersecurity": {
        "en": [
            "cybersecurity",
            "data breach",
            "ransomware",
            "malware",
            "hacker",
            "phishing",
            "vulnerability",
            "cyberattack",
            "encryption",
            "zero-day",
        ],
        "ru": [
            "кибербезопасность",
            "утечка данных",
            "вымогател",
            "вредоносн",
            "хакер",
            "фишинг",
            "уязвимост",
            "кибератак",
            "шифрован",
        ],
    },
    "software_development": {
        "en": [
            "software engineering",
            "devops",
            "ci/cd",
            "software release",
            "codebase",
            "software architecture",
            "agile",
            "software update",
            "version release",
        ],
        "ru": [
            "разработка программного обеспечения",
            "devops",
            "релиз",
            "архитектура программного обеспечения",
            "исправление ошибок",
            "обновление по",
        ],
    },
    "programming": {
        "en": [
            "programming language",
            "source code",
            "open source",
            "github",
            "software developer",
            "coding",
            "algorithm",
            "compiler",
            "framework",
        ],
        "ru": [
            "язык программирования",
            "исходный код",
            "открытый исходный код",
            "github",
            "разработчик",
            "программирование",
            "алгоритм",
            "компилятор",
        ],
    },
    "startups": {
        "en": [
            "startup",
            "venture capital",
            "funding round",
            "seed funding",
            "unicorn",
            "series a",
            "pitch deck",
            "accelerator",
            "y combinator",
        ],
        "ru": [
            "стартап",
            "венчурный капитал",
            "раунд финансирования",
            "единорог",
            "акселератор",
        ],
    },
    "finance": {
        "en": [
            "interest rate",
            "federal reserve",
            "inflation",
            "central bank",
            "cryptocurrency",
            "bitcoin",
            "hedge fund",
            "bond market",
            "exchange rate",
        ],
        "ru": [
            "процентная ставка",
            "центральный банк",
            "инфляция",
            "криптовалюта",
            "биткоин",
            "хедж-фонд",
            "валютный курс",
        ],
    },
    "business": {
        "en": [
            "ceo",
            "corporation",
            "merger",
            "acquisition",
            "earnings report",
            "quarterly results",
            "stock market",
            "shareholders",
            "ipo",
        ],
        "ru": [
            "генеральный директор",
            "корпорация",
            "слияние",
            "поглощение",
            "квартальная отчетность",
            "фондовый рынок",
            "акционер",
        ],
    },
    "space": {
        "en": [
            "nasa",
            "spacex",
            "astronaut",
            "satellite launch",
            "mars mission",
            "rocket launch",
            "space station",
            "telescope",
            "lunar",
        ],
        "ru": [
            "наса",
            "spacex",
            "космонавт",
            "запуск спутника",
            "миссия на марс",
            "запуск ракеты",
            "космическая станция",
            "телескоп",
        ],
    },
    "natural_disasters": {
        "en": [
            "earthquake",
            "hurricane",
            "flood",
            "wildfire",
            "tsunami",
            "tornado",
            "volcanic eruption",
            "landslide",
            "magnitude",
        ],
        "ru": [
            "землетрясение",
            "ураган",
            "наводнение",
            "пожар",
            "цунами",
            "торнадо",
            "извержение вулкана",
            "оползень",
        ],
    },
    "technology": {
        "en": [
            "smartphone",
            "gadget",
            "tech company",
            "silicon valley",
            "consumer electronics",
            "operating system",
            "chipmaker",
            "semiconductor",
        ],
        "ru": [
            "смартфон",
            "гаджет",
            "технологическая компания",
            "потребительская электроника",
            "операционная система",
            "полупроводник",
        ],
    },
    "science": {
        "en": [
            "research study",
            "scientists",
            "laboratory",
            "peer-reviewed",
            "physics",
            "chemistry",
            "biology",
            "genome",
            "clinical trial",
        ],
        "ru": [
            "исследование",
            "ученые",
            "лаборатория",
            "физика",
            "химия",
            "биология",
            "геном",
            "клиническое испытание",
        ],
    },
    "politics": {
        "en": [
            "election",
            "president",
            "parliament",
            "senate",
            "congress",
            "prime minister",
            "political party",
            "legislation",
            "voters",
        ],
        "ru": [
            "выборы",
            "президент",
            "парламент",
            "сенат",
            "премьер-министр",
            "политическая партия",
            "законодательство",
            "избиратели",
        ],
    },
    "world_news": {
        "en": [
            "united nations",
            "global summit",
            "foreign minister",
            "diplomatic",
            "ceasefire",
            "refugee crisis",
            "geopolitical",
        ],
        "ru": [
            "оон",
            "мировой саммит",
            "министр иностранных дел",
            "дипломатическ",
            "перемирие",
            "беженц",
            "геополитическ",
        ],
    },
}

# Uzbek keyword set closes M14's third-language categorization gap. Keep the
# rules compact to avoid an LLM call for ordinary classification.
_UZBEK_KEYWORDS = {
    "python": ["python", "django", "flask", "dasturchi"],
    "artificial_intelligence": [
        "sun'iy intellekt", "mashinali o'qitish", "neyron tarmoq", "chatgpt"
    ],
    "cybersecurity": ["kiberxavfsizlik", "ma'lumotlar sizishi", "xaker", "firibgarlik"],
    "software_development": ["dasturiy ta'minot", "devops", "dastur yangilanishi", "kod"],
    "programming": ["dasturlash", "ochiq manba", "algoritm", "kompilyator"],
    "startups": ["startap", "venchur", "investitsiya", "akselerator"],
    "finance": ["foiz stavkasi", "inflyatsiya", "markaziy bank", "kriptovalyuta", "bitcoin"],
    "business": ["kompaniya", "qo'shilish", "aksiyador", "daromad"],
    "space": ["nasa", "kosmonavt", "sun'iy yo'ldosh", "mars", "raketa"],
    "natural_disasters": ["zilzila", "suv toshqini", "o'rmon yong'ini", "to'fon", "vulqon"],
    "technology": ["smartfon", "texnologiya", "operatsion tizim", "chip"],
    "science": ["tadqiqot", "olimlar", "laboratoriya", "fizika", "biologiya"],
    "politics": ["saylov", "prezident", "parlament", "senat", "qonunchilik"],
    "world_news": ["birlashgan millatlar", "sammit", "diplomatik", "sulh", "geosiyosiy"],
}
for _category, _keywords in _UZBEK_KEYWORDS.items():
    CATEGORY_KEYWORDS[_category]["uz"] = _keywords

# A single stray keyword match is often coincidental; require the article
# to clear this bar before we trust the keyword result over the source's
# own configured default_category_id.
MIN_SCORE_THRESHOLD = 2

_TITLE_WEIGHT = 3
_CONTENT_WEIGHT = 1


def _count_occurrences(pattern: str, text: str) -> int:
    return len(re.findall(re.escape(pattern), text))


def categorize(title: str, content: str, language: str | None) -> str | None:
    """Returns the best-matching category *key* (not id — the caller
    resolves that against InterestCategory, since this module has no DB
    access by design), or None if nothing scored above threshold.
    """
    if language not in {"en", "ru", "uz"}:
        return None

    title_lower = title.lower()
    content_lower = content.lower()

    scores: dict[str, int] = {}
    for category_key, by_language in CATEGORY_KEYWORDS.items():
        keywords = by_language.get(language)
        if not keywords:
            continue
        score = sum(
            _count_occurrences(kw, title_lower) * _TITLE_WEIGHT
            + _count_occurrences(kw, content_lower) * _CONTENT_WEIGHT
            for kw in keywords
        )
        if score > 0:
            scores[category_key] = score

    if not scores:
        return None

    best_category, best_score = max(scores.items(), key=lambda item: item[1])
    return best_category if best_score >= MIN_SCORE_THRESHOLD else None
