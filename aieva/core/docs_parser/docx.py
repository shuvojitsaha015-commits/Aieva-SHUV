"""The DOCX reader of Aieva.

Word stores its equations as OMML inside the XML of the paragraph. The reader

* collects the text of the paragraphs and of the tables,
* converts every OMML formula to LaTeX,
* hands the embedded pictures to the OCR pipeline (they are returned as image
  candidates).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aieva.core.docs_parser.extract import EquationCandidate
from aieva.core.docs_parser.omml import MATH_NS, omml_to_latex

LOGGER = logging.getLogger(__name__)

#: The XML namespace of Word.
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _math_elements(parent: Any) -> list[Any]:
    """The ``m:oMath`` elements below a node."""
    found: list[Any] = []
    for node in parent.iter():
        tag = getattr(node, "tag", "")
        if isinstance(tag, str) and tag.rsplit("}", 1)[-1] == "oMath":
            found.append(node)
    return found


def _paragraph_text(paragraph: Any) -> str:
    """The text of a paragraph without the formulas."""
    return (paragraph.text or "").strip()


def extract_docx_equations(
    path: str | Path, max_pages: int = 0, include_images: bool = True
) -> list[EquationCandidate]:
    """Every equation of a ``.docx`` document."""
    from docx import Document

    document = Document(str(path))
    candidates: list[EquationCandidate] = []
    page = 1

    for paragraph in document.paragraphs:
        text = _paragraph_text(paragraph)
        formulas = _math_elements(paragraph._p)
        if formulas:
            for formula in formulas:
                latex = omml_to_latex(formula)
                if not latex:
                    continue
                candidates.append(
                    EquationCandidate(
                        page=page,
                        latex=latex,
                        text=text,
                        source="omml",
                        meta={"paragraph": text},
                    )
                )
            continue
        if text and _is_math(text):
            candidates.append(EquationCandidate(page=page, text=text, source="text"))

    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    text = _paragraph_text(paragraph)
                    for formula in _math_elements(paragraph._p):
                        latex = omml_to_latex(formula)
                        if latex:
                            candidates.append(
                                EquationCandidate(
                                    page=page,
                                    latex=latex,
                                    text=text,
                                    source="omml",
                                )
                            )
                    if text and _is_math(text):
                        candidates.append(EquationCandidate(page=page, text=text, source="text"))

    if include_images:
        candidates.extend(_image_candidates(document, page))

    if max_pages:
        candidates = [item for item in candidates if item.page <= max_pages]
    return candidates


def _image_candidates(document: Any, page: int) -> list[EquationCandidate]:
    """The pictures of the document (they have to be read by the OCR)."""
    from io import BytesIO

    from PIL import Image

    candidates: list[EquationCandidate] = []
    seen: set[str] = set()
    try:
        parts = list(document.part.related_parts.values())
    except Exception as exc:  # noqa: BLE001 - a broken document
        LOGGER.info("The images of the document could not be read: %s", exc)
        return candidates
    for part in parts:
        content_type = getattr(part, "content_type", "")
        if not content_type.startswith("image/"):
            continue
        name = str(getattr(part, "partname", ""))
        if name in seen:
            continue
        seen.add(name)
        try:
            image = Image.open(BytesIO(part.blob)).convert("RGB")
        except Exception as exc:  # noqa: BLE001 - a broken image
            LOGGER.info("The image %s could not be opened: %s", name, exc)
            continue
        candidates.append(
            EquationCandidate(page=page, image=image, source="image", meta={"part": name})
        )
    return candidates


def _is_math(text: str) -> bool:
    """``True`` when a line of text looks like a formula."""
    from aieva.core.ocr.pipeline import looks_like_math

    stripped = (text or "").strip()
    if not stripped or len(stripped) > 120:
        return False
    if "=" not in stripped:
        return False
    return looks_like_math(stripped)


__all__ = ["MATH_NS", "WORD_NS", "extract_docx_equations"]
