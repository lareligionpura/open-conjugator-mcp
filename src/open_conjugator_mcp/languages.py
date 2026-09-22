from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Language:
    code: str
    iso3: str
    name: str
    native_name: str
    direction: str
    engine: str
    priority: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


LANGUAGES = (
    Language("ar", "ara", "Arabic", "العربية", "rtl", "CAMeL Morph + CAMeL Tools", 1),
    Language("es", "spa", "Spanish", "Español", "ltr", "UniMorph", 2),
    Language("en", "eng", "English", "English", "ltr", "UniMorph", 3),
    Language("fr", "fra", "French", "Français", "ltr", "UniMorph", 4),
)


def _key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold().strip()
    return "".join(char for char in decomposed if not unicodedata.combining(char))


ALIASES: dict[str, Language] = {}
for language in LANGUAGES:
    for alias in (language.code, language.iso3, language.name, language.native_name):
        ALIASES[_key(alias)] = language

for alias, code in {
    "árabe": "ar",
    "arabe": "ar",
    "arabic": "ar",
    "español": "es",
    "espanol": "es",
    "spanish": "es",
    "inglés": "en",
    "ingles": "en",
    "english": "en",
    "francés": "fr",
    "frances": "fr",
    "french": "fr",
}.items():
    ALIASES[_key(alias)] = next(item for item in LANGUAGES if item.code == code)


def resolve_language(value: str) -> Language:
    try:
        return ALIASES[_key(value)]
    except KeyError as error:
        supported = ", ".join(language.code for language in LANGUAGES)
        raise ValueError(f"Unsupported language '{value}'. Supported codes: {supported}") from error

