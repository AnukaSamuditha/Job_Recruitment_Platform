"""Normalize rich job descriptions (e.g. Tiptap HTML) to plain text for hashing + embeddings."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def html_to_plain(html: str) -> str:
    """Strip tags and collapse whitespace."""
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
