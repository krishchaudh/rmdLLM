"""Script/language detection for queries: 'hi' (Devanagari), 'hi-Latn' (Romanized Hindi) or 'en'."""

from __future__ import annotations

import re

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")

# Common Romanized-Hindi function words / spiritual vocabulary. Matching several of them in a
# Latin-script query is a strong signal of Hinglish rather than English.
_ROMAN_HINDI_HINTS = {
    "kya",
    "kyu",
    "kyun",
    "kyon",
    "kaise",
    "kaun",
    "kab",
    "kahan",
    "hai",
    "hain",
    "nahi",
    "nahin",
    "ka",
    "ki",
    "ke",
    "ko",
    "se",
    "me",
    "mein",
    "par",
    "aur",
    "hota",
    "hoti",
    "hote",
    "karna",
    "karo",
    "chahiye",
    "bhagwan",
    "bhagavan",
    "bhakti",
    "sadhana",
    "maya",
    "prem",
    "sukh",
    "dukh",
    "sansar",
    "samsar",
    "dhan",
    "paisa",
    "bachpan",
    "bhajan",
    "guru",
    "krishna",
    "radha",
    "jeev",
    "jiv",
    "mann",
    "man",
    "sharanagati",
    "prapti",
}


def detect_language(text: str) -> str:
    if _DEVANAGARI.search(text):
        return "hi"
    words = re.findall(r"[a-z]+", text.lower())
    if not words:
        return "en"
    hits = sum(1 for w in words if w in _ROMAN_HINDI_HINTS)
    if hits >= 2 and hits / len(words) >= 0.25:
        return "hi-Latn"
    return "en"
