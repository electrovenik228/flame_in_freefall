"""Automated checks on AI output (sections 7.3 and 7.5).

- Evidence quotes must appear word for word in the stored source. Only runs of whitespace are
  normalized, because line breaks in a source carry no meaning.
- A number in AI prose is verified when the same number appears in the text of a source document
  of the cited record. Units are not converted: prompts require numbers as the source writes them.
- Identifiers such as PSI-69 and digits inside names such as C2H4 are not numeric claims.
"""

import re

WHITESPACE = re.compile(r"\s+")
IDENTIFIER = re.compile(r"\bPSI-\d+\b")
TOKEN = re.compile(r"\d+(?:[.,]\d+)*")
THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")


def normalize(text: str) -> str:
    return WHITESPACE.sub(" ", text).strip()


def quote_in_source(quote: str, source_text: str) -> bool:
    cleaned = normalize(quote)
    return bool(cleaned) and cleaned in normalize(source_text)


def numbers_in(text: str) -> list[tuple[str, float]]:
    """Numeric tokens of a text with their values."""
    cleaned = IDENTIFIER.sub(" ", text)
    found: list[tuple[str, float]] = []
    for match in TOKEN.finditer(cleaned):
        if cleaned[match.start() - 1 : match.start()].isalpha():
            continue  # part of a name or formula: C2H4, CO2, H19H101
        token = match.group()
        # "1,000" is one number; "2,3" is a list of two.
        parts = [token.replace(",", "")] if THOUSANDS.fullmatch(token) else token.split(",")
        for part in parts:
            try:
                found.append((part, float(part)))
            except ValueError:
                continue
    return found


def number_set(text: str) -> set[float]:
    return {round(value, 9) for _, value in numbers_in(text)}


def unmatched_numbers(ai_text: str, source_texts: list[str]) -> list[str]:
    """Numbers stated in AI text that appear in none of the source texts."""
    allowed: set[float] = set()
    for source in source_texts:
        allowed |= number_set(source)
    return [token for token, value in numbers_in(ai_text) if round(value, 9) not in allowed]


def number_in_quotes(value: float, quotes: list[str]) -> bool:
    return any(round(value, 9) in number_set(quote) for quote in quotes)
