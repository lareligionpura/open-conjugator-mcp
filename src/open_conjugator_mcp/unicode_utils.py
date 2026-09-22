from __future__ import annotations

import re
import unicodedata


ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
ARABIC_DIACRITICS_RE = re.compile(
    r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u08d3-\u08ff]"
)


def normalize_display(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip())


def normalize_lookup(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def strip_arabic_diacritics(value: str) -> str:
    return ARABIC_DIACRITICS_RE.sub("", normalize_display(value))


def normalize_arabic_lookup(value: str) -> str:
    value = strip_arabic_diacritics(value)
    return value.replace("ٱ", "ا").replace("ـ", "")


def contains_arabic(value: str) -> bool:
    return bool(ARABIC_RE.search(value))

