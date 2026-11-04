"""Interface text in English and Russian. The language follows the
`language` setting (the Windows display language when it is "auto"); any
other language gets English."""

STRINGS = {
    "en": {
        "app": "Museum Wallpapers",
        "about": "About this painting",
        "next": "Next painting",
        "read_more": "Read more",
        "save": "Save to collection",
        "save_short": "Save",
        "saved": "Saved to your collection",
        "already_saved": "Already in your collection",
        "change_every": "Change every",
        "minutes": "{n} minutes",
        "hour": "1 hour",
        "hours": "{n} hours",
        "day": "1 day",
        "only_on_demand": "Only when I ask",
        "artists": "Artists",
        "fame_famous": "Famous (~280 painters)",
        "fame_known": "Known (~1200 painters)",
        "fame_any": "Any painter",
        "fit": "Paintings that are not widescreen",
        "fit_blur": "Blurred frame",
        "fit_auto": "Fill, or blurred frame if cropping a lot",
        "fit_wall": "Dark wall",
        "fit_cover": "Fill the screen (crop)",
        "caption": "Caption on wallpaper",
        "caption_off": "Off",
        "caption_bottom-right": "Bottom right",
        "caption_bottom-left": "Bottom left",
        "caption_top-right": "Top right",
        "caption_top-left": "Top left",
        "language": "Language",
        "lang_auto": "Same as Windows",
        "notify_on_change": "Notify when it changes",
        "start_with_windows": "Start with Windows",
        "open_collection": "Open collection folder",
        "quit": "Quit",
        "more_by": "More by {name}",
        "more_of": "More {name}",
        "showing_only": "Showing only: {name}",
        "show_all": "Show all paintings again",
        "finding": "Finding a painting…",
        "no_painting": "No painting yet — the first one appears within a minute.",
        "started": "Museum Wallpapers is running. Right-click the frame icon by the clock for options.",
        "close": "Close",
    },
    "ru": {
        "app": "Museum Wallpapers",
        "about": "Об этой картине",
        "next": "Следующая картина",
        "read_more": "Подробнее",
        "save": "Сохранить в коллекцию",
        "save_short": "Сохранить",
        "saved": "Сохранено в коллекцию",
        "already_saved": "Уже есть в коллекции",
        "change_every": "Как часто менять",
        "minutes": "{n} минут",
        "hour": "1 час",
        "hours": "{n} часов",
        "day": "1 день",
        "only_on_demand": "Только по запросу",
        "artists": "Художники",
        "fame_famous": "Знаменитые (~280)",
        "fame_known": "Известные (~1200)",
        "fame_any": "Любые",
        "fit": "Картины не 16:9",
        "fit_blur": "Размытая рамка",
        "fit_auto": "Заполнить, или рамка при сильной обрезке",
        "fit_wall": "Тёмная стена",
        "fit_cover": "Заполнить экран (обрезать)",
        "caption": "Подпись на обоях",
        "caption_off": "Выключена",
        "caption_bottom-right": "Справа внизу",
        "caption_bottom-left": "Слева внизу",
        "caption_top-right": "Справа вверху",
        "caption_top-left": "Слева вверху",
        "language": "Язык",
        "lang_auto": "Как в Windows",
        "notify_on_change": "Уведомлять о смене",
        "start_with_windows": "Запускать вместе с Windows",
        "open_collection": "Открыть папку коллекции",
        "quit": "Выход",
        "more_by": "Ещё {name}",
        "more_of": "Ещё: {name}",
        "showing_only": "Только: {name}",
        "show_all": "Снова показывать все картины",
        "finding": "Ищу картину…",
        "no_painting": "Картины пока нет — первая появится в течение минуты.",
        "started": "Museum Wallpapers запущен. Настройки — правой кнопкой по значку-рамке у часов.",
        "close": "Закрыть",
    },
}

# Names of the languages offered in the menu, in their own language.
LANGUAGE_NAMES = {
    "en": "English", "ru": "Русский", "uk": "Українська", "de": "Deutsch", "fr": "Français",
    "es": "Español", "it": "Italiano", "nl": "Nederlands", "pl": "Polski", "pt": "Português",
}


def ui_language(config_or_language):
    language = config_or_language.get("language", "en") if isinstance(config_or_language, dict) \
        else str(config_or_language or "en")
    return language if language in STRINGS else "en"


def t(key, config_or_language="en", **values):
    table = STRINGS[ui_language(config_or_language)]
    text = table.get(key) or STRINGS["en"].get(key) or key
    return text.format(**values) if values else text


def interval_label(minutes, config_or_language="en"):
    if minutes == 0:
        return t("only_on_demand", config_or_language)
    if minutes < 60:
        return t("minutes", config_or_language, n=minutes)
    if minutes == 60:
        return t("hour", config_or_language)
    if minutes == 1440:
        return t("day", config_or_language)
    hours = minutes // 60
    text = t("hours", config_or_language, n=hours)
    if ui_language(config_or_language) == "ru" and hours in (2, 3, 4):
        text = f"{hours} часа"
    return text
