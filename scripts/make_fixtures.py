"""Create the document fixtures of Phase 10.

The fixtures are generated (not hand made), so they can be rebuilt at any
time::

    python3 scripts/make_fixtures.py

It writes into ``tests/fixtures/docs/``:

``equations.docx``
    a Word document with two OMML formulas;
``slide.pptx``
    a slide with an equation **picture** and a text formula;
``text.pdf``
    a PDF with formulas as text;
``scanned.pdf``
    a PDF with only a picture (a scanned page).
"""

from __future__ import annotations

import io
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "tests" / "fixtures" / "docs"

MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _omml(latex_parts: list[str]) -> str:
    """A tiny OMML builder for the formulas of the fixture."""
    body = ""
    for part in latex_parts:
        if part.startswith(("sup(", "sup2(")):
            base, exponent = part[part.index("(") + 1 : -1].split("|")
            body += (
                "<m:sSup><m:e><m:r><m:t>"
                f"{base}"
                "</m:t></m:r></m:e><m:sup><m:r><m:t>"
                f"{exponent}"
                "</m:t></m:r></m:sup></m:sSup>"
            )
        elif part.startswith("frac("):
            top, bottom = part[5:-1].split("|")
            body += (
                "<m:f><m:num><m:r><m:t>"
                f"{top}"
                "</m:t></m:r></m:num><m:den><m:r><m:t>"
                f"{bottom}"
                "</m:t></m:r></m:den></m:f>"
            )
        else:
            body += f"<m:r><m:t>{part}</m:t></m:r>"
    return (
        f'<m:oMathPara xmlns:m="{MATH_NS}" xmlns:w="{W_NS}"><m:oMath>{body}</m:oMath>'
        "</m:oMathPara>"
    )


def make_docx() -> Path:
    """A Word document with two OMML formulas."""
    from docx import Document

    document = Document()
    document.add_paragraph("Solve the two equations of the exercise:")
    document.add_paragraph("")

    first = document.add_paragraph("")
    first._p.append(
        first._p.makeelement(
            "{http://www.w3.org/XML/1998/namespace}dummy",
            {},
        )
    )  # keep lxml happy about the namespace handling
    first._p.remove(first._p[-1])
    from lxml import etree

    first._p.append(etree.fromstring(_omml(["sup(x|2)", "+", "3x", "=", "7"])))
    document.add_paragraph("and the energy of the ball:")

    second = document.add_paragraph("")
    second._p.append(etree.fromstring(_omml(["E", "=", "frac(1|2)", "m", "sup2(v|2)"])))
    path = OUT_DIR / "equations.docx"
    document.save(str(path))
    return path


def _formula_image(text: str, width: int = 640, height: int = 200) -> bytes:
    """A picture with a formula in it."""
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    figure = plt.figure(figsize=(width / 100, height / 100), dpi=100)
    figure.patch.set_facecolor("white")
    figure.text(0.5, 0.5, f"${text}$", ha="center", va="center", fontsize=34, color="black")
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=100)
    plt.close(figure)
    return buffer.getvalue()


def make_pptx() -> Path:
    """A slide with an equation picture and a formula as text."""
    from pptx import Presentation
    from pptx.util import Emu

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])

    title = slide.shapes.title
    if title is not None:
        title.text = "The exercise of the week"

    picture = slide.shapes.add_picture(
        io.BytesIO(_formula_image(r"x^2 + 3x - 2 = 0")),
        Emu(600000),
        Emu(1800000),
        Emu(5000000),
        Emu(1400000),
    )
    picture.name = "equation picture"

    box = slide.shapes.add_textbox(Emu(600000), Emu(3400000), Emu(5000000), Emu(800000))
    box.text_frame.text = "and the area: A = w * h = 40"

    path = OUT_DIR / "slide.pptx"
    presentation.save(str(path))
    return path


def make_text_pdf() -> Path:
    """A PDF with the formulas as text."""
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 100), "Solve the quadratic equation", fontsize=16)
    page.insert_text((72, 140), "x^2 + 3x - 2 = 0", fontsize=14)
    page.insert_text((72, 170), "and the area A = w*h = 40 m^2", fontsize=14)
    page.insert_text((72, 210), "Just a sentence without any mathematics.", fontsize=12)
    path = OUT_DIR / "text.pdf"
    document.save(str(path))
    document.close()
    return path


def make_scanned_pdf() -> Path:
    """A PDF with only a picture - a scanned page."""
    import pymupdf
    from PIL import Image

    image_bytes = _formula_image(r"\int_0^1 x^2 dx = \frac{1}{3}", width=700, height=460)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=72)
    jpeg = buffer.getvalue()

    document = pymupdf.open()
    page = document.new_page(width=600, height=420)
    page.insert_image(pymupdf.Rect(40, 40, 560, 380), stream=jpeg)
    path = OUT_DIR / "scanned.pdf"
    document.save(str(path))
    document.close()
    return path


def main() -> None:
    """Write every fixture."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for builder in (make_docx, make_pptx, make_text_pdf, make_scanned_pdf):
        path = builder()
        print(f"{path.relative_to(REPO_ROOT)}  ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
