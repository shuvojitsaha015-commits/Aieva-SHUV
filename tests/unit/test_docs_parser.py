"""The document parser of Phase 10 (PDF / PPTX / DOCX)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aieva.core.docs_parser.extract import (
    SUPPORTED_SUFFIXES,
    EquationCandidate,
    document_kind,
    extract_equations,
    page_count,
    unsupported_message,
)
from aieva.core.docs_parser.omml import omml_to_latex

DOCS = Path(__file__).resolve().parents[1] / "fixtures" / "docs"


def _omml(xml: str):
    from lxml import etree

    return etree.fromstring(xml)


def _math(inner: str):
    return _omml(
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        f"{inner}</m:oMath>"
    )


# ------------------------------------------------------------------ the files
def test_the_fixtures_exist():
    for name in ("equations.docx", "slide.pptx", "text.pdf", "scanned.pdf"):
        assert (DOCS / name).is_file()


def test_document_kind():
    assert document_kind("a.pdf") == "pdf"
    assert document_kind("a.PPTX") == "pptx"
    assert document_kind("a.docx") == "docx"
    assert document_kind("a.doc") == "unsupported"
    assert document_kind("a.txt") == "unsupported"
    assert ".pdf" in SUPPORTED_SUFFIXES


def test_the_message_for_an_old_format():
    message = unsupported_message("lesson.doc")
    assert "docx" in message
    assert ".pptx" in unsupported_message("lesson.ppt")
    assert "pdf" in unsupported_message("lesson.key")


def test_an_unsupported_file_is_refused(tmp_path):
    path = tmp_path / "lesson.doc"
    path.write_bytes(b"not a document")
    with pytest.raises(ValueError) as error:
        extract_equations(path)
    assert "docx" in str(error.value)


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_equations(tmp_path / "nothing.docx")


# ------------------------------------------------------------------- the docx
def test_the_docx_gives_the_omml_equations():
    candidates = extract_equations(DOCS / "equations.docx")
    latex = [item.latex for item in candidates if item.has_latex]
    assert len(latex) == 2
    assert "x^{2}" in latex[0]
    assert "3x" in latex[0]
    assert latex[1].startswith("E =")
    assert r"\frac{1}{2}" in latex[1]
    assert all(item.source == "omml" for item in candidates)


def test_the_docx_candidates_can_be_serialised():
    candidates = extract_equations(DOCS / "equations.docx")
    data = candidates[0].to_dict()
    assert data["page"] == 1
    assert data["latex"]
    assert data["has_image"] is False
    assert data["needs_ocr"] is False


# ------------------------------------------------------------------- the pptx
def test_the_pptx_gives_the_picture_and_the_text():
    candidates = extract_equations(DOCS / "slide.pptx")
    images = [item for item in candidates if item.image is not None]
    texts = [item for item in candidates if item.text]
    assert len(images) == 1
    assert images[0].needs_ocr
    assert images[0].bbox is not None
    assert images[0].page == 1
    assert len(texts) == 1
    assert "A = w * h = 40" in texts[0].text


def test_the_pptx_picture_is_a_real_image():
    candidates = extract_equations(DOCS / "slide.pptx")
    image = candidates[0].image
    assert image is not None
    assert image.width > 100
    assert image.mode == "RGB"


# -------------------------------------------------------------------- the pdf
def test_the_text_pdf_gives_the_lines():
    candidates = extract_equations(DOCS / "text.pdf")
    texts = [item.text for item in candidates]
    assert any("x^2 + 3x - 2 = 0" in text for text in texts)
    assert len(candidates) >= 2
    assert all(item.source == "pdf-text" for item in candidates)


def test_the_scanned_pdf_gives_an_image():
    candidates = extract_equations(DOCS / "scanned.pdf")
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.image is not None
    assert candidate.needs_ocr
    assert candidate.source == "scan"
    assert candidate.meta["scanned"] is True


def test_the_page_count():
    assert page_count(DOCS / "text.pdf") == 1
    assert page_count(DOCS / "slide.pptx") == 1
    assert page_count(DOCS / "equations.docx") > 0
    assert page_count(DOCS / "nothing.pdf") == 0


def test_max_pages_stops_the_reader():
    candidates = extract_equations(DOCS / "equations.docx", max_pages=0)
    assert candidates


# ---------------------------------------------------------------------- omml
def test_omml_simple_text():
    assert omml_to_latex(_math("<m:r><m:t>x + 1</m:t></m:r>")) == "x + 1"


def test_omml_superscript():
    latex = omml_to_latex(
        _math(
            "<m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>"
        )
    )
    assert latex == "x^{2}"


def test_omml_fraction():
    latex = omml_to_latex(
        _math(
            "<m:f><m:num><m:r><m:t>1</m:t></m:r></m:num>"
            "<m:den><m:r><m:t>2</m:t></m:r></m:den></m:f>"
        )
    )
    assert latex == r"\frac{1}{2}"


def test_omml_radical():
    latex = omml_to_latex(_math("<m:rad><m:deg/><m:e><m:r><m:t>x</m:t></m:r></m:e></m:rad>"))
    assert latex == r"\sqrt{x}"


def test_omml_delimiter():
    latex = omml_to_latex(
        _math(
            '<m:d><m:dPr><m:begChr m:val="[" xmlns:m="http://schemas.openxmlformats.org/'
            'officeDocument/2006/math"/><m:endChr m:val="]" xmlns:m="http://schemas.'
            'openxmlformats.org/officeDocument/2006/math"/></m:dPr>'
            "<m:e><m:r><m:t>x</m:t></m:r></m:e></m:d>"
        )
    )
    assert latex == r"\left[x\right]"


def test_omml_sum():
    latex = omml_to_latex(
        _math(
            '<m:nary><m:naryPr><m:chr m:val="∑" xmlns:m="http://schemas.openxmlformats.org/'
            'officeDocument/2006/math"/></m:naryPr>'
            "<m:sub><m:r><m:t>i=1</m:t></m:r></m:sub>"
            "<m:e><m:r><m:t>i</m:t></m:r></m:e></m:nary>"
        )
    )
    assert r"\sum" in latex
    assert "i=1" in latex


def test_omml_matrix():
    latex = omml_to_latex(
        _math(
            "<m:m><m:mr><m:e><m:r><m:t>1</m:t></m:r></m:e>"
            "<m:e><m:r><m:t>2</m:t></m:r></m:e></m:mr></m:m>"
        )
    )
    assert r"\begin{matrix}" in latex
    assert "1 & 2" in latex


def test_omml_operators_are_translated():
    latex = omml_to_latex(_math("<m:r><m:t>a ≤ b</m:t></m:r>"))
    assert r"\leq" in latex


def test_omml_of_nothing_is_empty():
    assert omml_to_latex(None) == ""
    assert omml_to_latex([]) == ""


# ------------------------------------------------------------------ candidate
def test_a_candidate_without_latex_and_without_image():
    candidate = EquationCandidate(page=2, text="x = 1")
    assert not candidate.has_latex
    assert not candidate.needs_ocr
    assert candidate.display == "x = 1"
    assert candidate.to_dict()["page"] == 2
