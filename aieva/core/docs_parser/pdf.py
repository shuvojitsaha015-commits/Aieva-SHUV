"""The PDF reader of Aieva.

A PDF has no formulas - it has text and pictures. The reader

* collects the text of the pages and keeps the lines that look like a formula,
* returns the embedded pictures as image candidates,
* renders the pages that have **no** text (a scanned page) as an image, so
  that the OCR pipeline can read them.

``marker-pdf`` is used when it is installed: it converts the whole page to
LaTeX, which is much better than a line of text.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aieva.core.docs_parser.extract import EquationCandidate

LOGGER = logging.getLogger(__name__)

#: The resolution of the rendered pages (dots per inch).
RENDER_DPI = 150

#: The zoom factor that belongs to :data:`RENDER_DPI` (72 dpi is the base).
ZOOM = RENDER_DPI / 72.0


def marker_available() -> bool:
    """``True`` when the optional ``marker-pdf`` package can be used."""
    try:  # pragma: no cover - the optional dependency is rarely installed
        import marker  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def extract_pdf_equations(
    path: str | Path, max_pages: int = 0, include_images: bool = True
) -> list[EquationCandidate]:
    """Every equation of a ``.pdf`` document."""
    import pymupdf

    candidates: list[EquationCandidate] = []
    with pymupdf.open(str(path)) as document:
        pages = document.page_count
        for number in range(pages):
            page_number = number + 1
            if max_pages and page_number > max_pages:
                break
            page = document.load_page(number)
            text = page.get_text("text") or ""
            candidates.extend(_text_candidates(text, page_number))

            if not text.strip():
                # a scanned page: the whole page goes to the OCR
                image = _render_page(page)
                if image is not None:
                    candidates.append(
                        EquationCandidate(
                            page=page_number,
                            image=image,
                            source="scan",
                            meta={"scanned": True},
                        )
                    )
            elif include_images:
                candidates.extend(_image_candidates(page, page_number))
    return candidates


def _text_candidates(text: str, page: int) -> list[EquationCandidate]:
    """The lines of a page that look like a formula."""
    from aieva.core.ocr.pipeline import looks_like_math

    candidates: list[EquationCandidate] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or len(line) > 160:
            continue
        if "=" not in line and not any(symbol in line for symbol in ("∑", "∫", "√", "±")):
            continue
        if not looks_like_math(line):
            continue
        candidates.append(EquationCandidate(page=page, text=line, source="pdf-text"))
    return candidates


def _image_candidates(page: Any, number: int) -> list[EquationCandidate]:
    """The pictures that are embedded in a page."""
    from io import BytesIO

    from PIL import Image

    candidates: list[EquationCandidate] = []
    try:
        images = page.get_images(full=True)
    except Exception as exc:  # noqa: BLE001 - a broken page
        LOGGER.info("The images of the page could not be read: %s", exc)
        return candidates
    for info in images:
        xref = info[0]
        try:
            data = page.parent.extract_image(xref).get("image")
            if not data:
                continue
            image = Image.open(BytesIO(data)).convert("RGB")
        except Exception as exc:  # noqa: BLE001 - a broken image
            LOGGER.info("The image %s could not be read: %s", xref, exc)
            continue
        candidates.append(
            EquationCandidate(page=number, image=image, source="image", meta={"xref": xref})
        )
    return candidates


def _render_page(page: Any) -> Any | None:
    """Render a page into a PIL image (used for the scanned pages)."""
    from io import BytesIO

    from PIL import Image

    try:
        pixmap = page.get_pixmap(matrix=pymupdf_matrix())
        return Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - a broken page
        LOGGER.info("The page could not be rendered: %s", exc)
        return None


def pymupdf_matrix() -> Any:
    """The matrix that belongs to :data:`RENDER_DPI`."""
    import pymupdf

    return pymupdf.Matrix(ZOOM, ZOOM)


__all__ = ["RENDER_DPI", "ZOOM", "extract_pdf_equations", "marker_available"]
