"""Terminology dictionary: Devanagari / IAST / common romanized spellings for key concepts.

Used for lexical query expansion only. Variants are spellings of the *same* term; we never map
different concepts onto one another.
"""

from __future__ import annotations

import re
import unicodedata

TERMS: dict[str, list[str]] = {
    "bhakti": ["भक्ति", "bhakti", "bhakthi", "devotion"],
    "bhagavat prapti": [
        "भगवत्प्राप्ति",
        "भगवत प्राप्ति",
        "bhagavat prapti",
        "bhagwat prapti",
        "god realization",
    ],
    "sadhana": ["साधना", "sādhanā", "sadhana", "sadhna", "spiritual practice"],
    "maya": ["माया", "māyā", "maya"],
    "karma": ["कर्म", "karma", "karm"],
    "sharanagati": ["शरणागति", "śaraṇāgati", "sharanagati", "saranagati", "surrender"],
    "prema": ["प्रेम", "prema", "prem", "divine love"],
    "guru": ["गुरु", "guru"],
    "krishna": ["कृष्ण", "kṛṣṇa", "krishna", "krishn", "shri krishna"],
    "radha": ["राधा", "rādhā", "radha"],
    "jiva": ["जीव", "jīva", "jiva", "jeev", "soul"],
    "sansar": ["संसार", "saṁsāra", "samsara", "sansar", "material world"],
    "sukh": ["सुख", "sukha", "sukh", "happiness"],
    "dhan": ["धन", "dhana", "dhan", "wealth", "money", "पैसा", "paisa", "लखपति", "करोड़पति"],
    "bachpan": ["बचपन", "bachpan", "childhood", "कौमार", "kaumara"],
    "mann": ["मन", "mana", "mann", "mind"],
    "ananda": ["आनन्द", "आनंद", "ānanda", "anand", "bliss"],
    "satsang": ["सत्संग", "satsang", "satsanga"],
    "vairagya": ["वैराग्य", "vairāgya", "vairagya", "detachment"],
    "moksha": ["मोक्ष", "mokṣa", "moksha", "mukti", "मुक्ति", "liberation"],
}

_fold_cache: dict[str, str] = {}


def fold(s: str) -> str:
    """Lowercase + strip diacritics so 'Kṛṣṇa' ~ 'krsna' and 'Śrī' ~ 'sri'."""
    if s in _fold_cache:
        return _fold_cache[s]
    out = "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    ).lower()
    _fold_cache[s] = out
    return out


_VARIANT_INDEX: dict[str, str] = {}
for canon, variants in TERMS.items():
    for v in variants:
        _VARIANT_INDEX[fold(v)] = canon


def expand_query_terms(query: str, max_terms: int = 12) -> list[str]:
    """Return variant spellings for recognised terms in the query (for lexical OR-expansion)."""
    q = fold(query)
    words = set(re.findall(r"[\w\u0900-\u097F]+", q))
    found: list[str] = []
    for variant, canon in _VARIANT_INDEX.items():
        if " " in variant:
            if variant in q and canon not in found:
                found.append(canon)
        elif variant in words and canon not in found:
            found.append(canon)
    out: list[str] = []
    for canon in found:
        for v in TERMS[canon]:
            if fold(v) not in words and v not in out:
                out.append(v)
    return out[:max_terms]
