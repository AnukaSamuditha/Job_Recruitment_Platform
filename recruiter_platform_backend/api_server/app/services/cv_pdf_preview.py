"""Render CV PDF pages to PNG data URLs for browser preview (PyMuPDF)."""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


def pdf_bytes_to_png_data_urls(
    pdf_bytes: bytes,
    *,
    max_pages: int,
    max_width_px: int,
) -> list[str]:
    """
    Rasterize up to ``max_pages`` pages; scale so width ≤ ``max_width_px``.
    Returns ``data:image/png;base64,...`` strings suitable for ``<img src>``.
    """
    import fitz  # PyMuPDF

    if not pdf_bytes:
        return []

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    urls: list[str] = []
    try:
        n = min(doc.page_count, max(1, max_pages))
        for i in range(n):
            page = doc.load_page(i)
            rect = page.rect
            if rect.width <= 0:
                continue
            scale = max_width_px / float(rect.width)
            scale = max(0.4, min(scale, 3.0))
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png = pix.tobytes("png")
            b64 = base64.standard_b64encode(png).decode("ascii")
            urls.append(f"data:image/png;base64,{b64}")
    finally:
        doc.close()

    if not urls:
        logger.warning("PDF produced no preview pages (empty or unreadable PDF?)")
    return urls
