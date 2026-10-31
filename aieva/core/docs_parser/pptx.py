"""The PPTX reader of Aieva.

PowerPoint stores its equations either as OMML inside the XML of a shape or as
a picture. The reader

* collects the text of the shapes and of the tables,
* converts the OMML formulas to LaTeX,
* returns the pictures (with their position on the slide) as image candidates
  for the OCR pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aieva.core.docs_parser.extract import EquationCandidate
from aieva.core.docs_parser.omml import omml_to_latex

LOGGER = logging.getLogger(__name__)

#: English Metric Units per point.
EMU_PER_POINT = 12700.0


def _math_elements(shape: Any) -> list[Any]:
    """The ``m:oMath`` elements inside the XML of a shape."""
    found: list[Any] = []
    element = getattr(shape, "_element", None)
    if element is None:
        return found
    for node in element.iter():
        tag = getattr(node, "tag", "")
        if isinstance(tag, str) and tag.rsplit("}", 1)[-1] == "oMath":
            found.append(node)
    return found


def _bbox(shape: Any) -> tuple[float, float, float, float] | None:
    """The position of a shape on the slide (in points)."""
    try:
        left = shape.left / EMU_PER_POINT
        top = shape.top / EMU_PER_POINT
        width = shape.width / EMU_PER_POINT
        height = shape.height / EMU_PER_POINT
    except Exception:  # noqa: BLE001 - a shape without a position
        return None
    return (left, top, left + width, top + height)


def extract_pptx_equations(
    path: str | Path, max_pages: int = 0, include_images: bool = True
) -> list[EquationCandidate]:
    """Every equation of a ``.pptx`` presentation."""
    from pptx import Presentation

    presentation = Presentation(str(path))
    candidates: list[EquationCandidate] = []

    for number, slide in enumerate(presentation.slides, start=1):
        if max_pages and number > max_pages:
            break
        for shape in slide.shapes:
            candidates.extend(_shape_candidates(shape, number, include_images))
    return candidates


def _shape_candidates(shape: Any, page: int, include_images: bool) -> list[EquationCandidate]:
    """The candidates of one shape."""
    candidates: list[EquationCandidate] = []

    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            for cell in row.cells:
                text = (cell.text or "").strip()
                if text and _is_math(text):
                    candidates.append(
                        EquationCandidate(
                            page=page,
                            bbox=_bbox(shape),
                            text=text,
                            source="text",
                        )
                    )
        return candidates

    if getattr(shape, "shape_type", None) is not None and shape.shape_type == 13:  # PICTURE
        image = _picture_image(shape)
        if image is not None and include_images:
            candidates.append(
                EquationCandidate(
                    page=page,
                    bbox=_bbox(shape),
                    image=image,
                    source="image",
                )
            )
        return candidates

    text = ""
    if getattr(shape, "has_text_frame", False):
        text = (shape.text_frame.text or "").strip()

    formulas = _math_elements(shape)
    if formulas:
        for formula in formulas:
            latex = omml_to_latex(formula)
            if not latex:
                continue
            candidates.append(
                EquationCandidate(
                    page=page,
                    bbox=_bbox(shape),
                    latex=latex,
                    text=text,
                    source="omml",
                )
            )
        return candidates

    if text and _is_math(text):
        candidates.append(EquationCandidate(page=page, bbox=_bbox(shape), text=text, source="text"))
    return candidates


def _picture_image(shape: Any) -> Any | None:
    """The picture of a shape as a PIL image."""
    from io import BytesIO

    from PIL import Image

    try:
        blob = shape.image.blob
        return Image.open(BytesIO(blob)).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - a broken image
        LOGGER.info("The picture could not be read: %s", exc)
        return None


def _is_math(text: str) -> bool:
    """``True`` when a line of text looks like a formula."""
    from aieva.core.ocr.pipeline import looks_like_math

    stripped = (text or "").strip()
    if not stripped or len(stripped) > 120:
        return False
    if "=" not in stripped:
        return False
    return looks_like_math(stripped)


__all__ = ["EMU_PER_POINT", "extract_pptx_equations"]
