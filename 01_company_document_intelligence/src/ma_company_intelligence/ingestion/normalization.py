"""Conservative normalization for parser-produced text."""

import unicodedata


def normalize_extracted_text(text: str) -> str:
    """Normalize line endings and remove non-text control characters.

    Spaces, tabs, newlines, symbols, punctuation, and other visible characters are
    deliberately preserved because they may encode financial meaning or table layout.
    """

    normalized_line_endings = text.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        character
        for character in normalized_line_endings
        if character in {"\n", "\t"} or unicodedata.category(character) != "Cc"
    )
