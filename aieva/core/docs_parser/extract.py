"""Unified equation extraction for PDF / PPTX / DOCX.

The entry point is :func:`extract_equations`. It returns a list of
:class:`EquationCandidate` - one per equation it found:

* a candidate with a ``latex`` can be drawn straight away;
* a candidate with an ``image`` (and without a LaTeX) has to go through the
  OCR pipeline;
* a candidate with only ``text`` is a formula that was written as text (a
  PDF, for example) and can be parsed by the maths core.

Only ``.pdf``, ``.pptx`` and ``.docx`` are supported. The old binary formats
(``.doc``, ``.ppt``) get a clear message - see :func:`unsupported_message`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The file types Aieva can read.
SUPPORTED_SUFFIXES: tuple[str, ...] = (".pdf", ".pptx", ".docx")

#: The file types that are recognised but not supported.
LEGACY_SUFFIXES: tuple[str, ...] = (".doc", ".ppt", ".odt", ".odp", ".rtf")

#: The maximum number of pages that are read by default (0 = all).
DEFAULT_MAX_PAGES = 0


@dataclass
class EquationCandidate:
    """One equation that was found in a document."""

    page: int = 1
    bbox: tuple[float, float, float, float] | None = None
    latex: str | None = None
    text: str = ""
    image: Any | None = None
    source: str = "text"
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def has_latex(self) -> bool:
        """``True`` when the equation is already LaTeX."""
        return bool(self.latex and self.latex.strip())

    @property
    def needs_ocr(self) -> bool:
        """``True`` when the candidate has to go through the OCR pipeline."""
        return not self.has_latex and self.image is not None

    @property
    def display(self) -> str:
        """What the UI shows under the thumbnail."""
        if self.has_latex:
            return self.latex or ""
        if self.text:
            return self.text
        return "(a picture - it has to be read)"

    def to_dict(self) -> dict[str, Any]:
        """A JSON friendly description (the image is not included)."""
        return {
            "page": self.page,
            "bbox": list(self.bbox) if self.bbox else None,
            "latex": self.latex,
            "text": self.text,
            "has_image": self.image is not None,
            "source": self.source,
            "needs_ocr": self.needs_ocr,
            "display": self.display,
            "meta": dict(self.meta),
        }


def document_kind(path: str | Path) -> str:
    """``pdf``, ``pptx``, ``docx`` or ``unsupported``."""
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".pptx":
        return "pptx"
    if suffix == ".docx":
        return "docx"
    return "unsupported"


def unsupported_message(path: str | Path) -> str:
    """The message for a file that Aieva cannot read."""
    suffix = Path(path).suffix.lower()
    if suffix in LEGACY_SUFFIXES:
        return (
            f"{suffix} is an old binary format - please save the file as "
            f"{suffix}x (or as a PDF) and try again."
        )
    return (
        f"Aieva cannot read {suffix or 'this file'} - the supported formats are "
        f"{', '.join(SUPPORTED_SUFFIXES)}."
    )


def extract_equations(
    path: str | Path,
    max_pages: int = DEFAULT_MAX_PAGES,
    include_images: bool = True,
) -> list[EquationCandidate]:
    """Every equation of a document.

    The pages are read lazily by the format specific parser - a big document
    is not loaded completely into the memory.
    """
    document = Path(path)
    if not document.is_file():
        raise FileNotFoundError(f"The document {document} does not exist")

    kind = document_kind(document)
    if kind == "pdf":
        from aieva.core.docs_parser.pdf import extract_pdf_equations

        return extract_pdf_equations(document, max_pages=max_pages, include_images=include_images)
    if kind == "pptx":
        from aieva.core.docs_parser.pptx import extract_pptx_equations

        return extract_pptx_equations(document, max_pages=max_pages, include_images=include_images)
    if kind == "docx":
        from aieva.core.docs_parser.docx import extract_docx_equations

        return extract_docx_equations(document, max_pages=max_pages, include_images=include_images)
    raise ValueError(unsupported_message(document))


def page_count(path: str | Path) -> int:
    """How many pages / slides the document has (0 when unknown)."""
    document = Path(path)
    kind = document_kind(document)
    try:
        if kind == "pdf":
            import pymupdf

            with pymupdf.open(document) as handle:
                return int(handle.page_count)
        if kind == "pptx":
            from pptx import Presentation

            return len(Presentation(str(document)).slides)
        if kind == "docx":
            from docx import Document

            return len(Document(str(document)).paragraphs)
    except Exception as exc:  # noqa: BLE001 - the count is only a hint
        LOGGER.info("The number of pages could not be read: %s", exc)
    return 0


__all__ = [
    "DEFAULT_MAX_PAGES",
    "LEGACY_SUFFIXES",
    "SUPPORTED_SUFFIXES",
    "EquationCandidate",
    "document_kind",
    "extract_equations",
    "page_count",
    "unsupported_message",
]
