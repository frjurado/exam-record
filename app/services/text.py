import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# Every way of writing "number" before a figure: n.º 3, nº 3, no. 3, núm. 3, n. 3
_NUMBER_SIGN = re.compile(r"\b(?:n o|no|num|numero|n) (?=\d)")


def normalize(text: str | None) -> str:
    """Fold text for matching: no accents, lower case, punctuation collapsed to single spaces.

    "Albéniz" and "albeniz" normalize to the same string, as do "Op. 27, n.º 2" and
    "op 27 nº 2" (both become "op 27 n 2").
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    folded = _NON_ALNUM.sub(" ", without_marks.casefold()).strip()
    return _NUMBER_SIGN.sub("n ", folded)


def tokens(text: str | None) -> list[str]:
    return normalize(text).split()


def matches(query_tokens: list[str], haystack: str) -> bool:
    """True if every query token appears in the (already normalized) haystack."""
    return all(token in haystack for token in query_tokens)
