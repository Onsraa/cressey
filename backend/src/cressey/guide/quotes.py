from cressey.guide.models import Unit

_TYPO = str.maketrans({"’": "'", "‘": "'", "«": '"', "»": '"', "“": '"', "”": '"'})


def normalize(s: str) -> str:
    return " ".join(s.translate(_TYPO).split()).lower()


def verify_quote(quote: str, unit: Unit) -> bool:
    return 8 <= len(quote.split()) <= 30 and normalize(quote) in normalize(unit.text)
