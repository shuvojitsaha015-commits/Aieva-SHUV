"""Build the preview page of the Aieva project.

The page is a **product showcase**: the running application, one screen at a
time. It is a static page - the images are inlined, so it works without a
network.

    python3 scripts/make_preview_page.py -> preview/index.html
"""

from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREVIEW = ROOT / "preview"

#: The hero image and the gallery.
HERO = ("01-home.png", "Aieva")
GALLERY = [
    (
        "07-equation-sliders.png",
        "Type an equation, move the sliders",
        "Every parameter of the equation is a slider and the figure follows "
        "while the slider moves.",
    ),
    (
        "02-whiteboard.png",
        "Draw it with the finger",
        "The strokes are data, so the board can be read by the OCR and plotted " "again.",
    ),
    (
        "03-calculus-integral.png",
        "Calculus",
        "The shaded area of the integral, the exact value from SymPy and the "
        "numerical value from the quadrature.",
    ),
    (
        "04-linalg-matrix.png",
        "Linear algebra",
        "The grid is warped by the matrix; the determinant is the area scale "
        "and the basis vectors are drawn.",
    ),
    (
        "05-3d-surface.png",
        "Three dimensional plots",
        "Drag rotates the camera, a pinch zooms and the quality is chosen in " "the settings.",
    ),
    (
        "06-solver-steps.png",
        "Solve from the screen",
        "The selected region is read, solved and shown step by step with the " "formulas.",
    ),
    (
        "08-wordproblem.png",
        "Word problems",
        "The text becomes a model with variables and an equation; the numbers "
        "are confirmed and the picture is animated.",
    ),
    (
        "09-documents.png",
        "Documents",
        "The equations of a PDF, a presentation or a Word file are extracted " "and ready to plot.",
    ),
    (
        "10-settings.png",
        "Settings",
        "The server, the quality of the renderer, the offline mode, the pen "
        "and the palm rejection.",
    ),
]

FEATURES = [
    (
        "M4 12h16M4 7h16M4 17h10",
        "Screen aware",
        "A region of the board is selected, read and turned into a solution.",
    ),
    (
        "M4 19V5m0 14h16M8 15l3-4 3 2 4-6",
        "Live mathematics",
        "The figure is redrawn while the parameter changes.",
    ),
    (
        "M12 3v18M3 12h18",
        "Every subject",
        "The screens are built from a plugin registry, so a new subject needs "
        "no change in the interface.",
    ),
    (
        "M12 3l9 5v8l-9 5-9-5V8z",
        "Built for a board",
        "Touch first, large targets, palm rejection and a quality that keeps "
        "the picture smooth.",
    ),
]


def data_uri(path: Path) -> str:
    """A PNG as a data URI (so the page works on its own)."""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def icon(paths: str) -> str:
    """A small line icon (drawn with SVG paths)."""
    return (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{paths}"/></svg>'
    )


def build() -> str:
    hero_path = PREVIEW / HERO[0]
    hero_image = ""
    if hero_path.is_file():
        hero_image = f'<img src="{data_uri(hero_path)}" alt="{HERO[1]}">'

    gallery = []
    for name, title, text in GALLERY:
        path = PREVIEW / name
        if not path.is_file():
            continue
        gallery.append(f"""        <figure class="shot">
          <div class="frame"><img src="{data_uri(path)}" alt="{title}"></div>
          <figcaption>
            <strong>{title}</strong>
            <span>{text}</span>
          </figcaption>
        </figure>""")

    features = []
    for paths, title, text in FEATURES:
        features.append(f"""        <div class="feature">
          <span class="feature-icon">{icon(paths)}</span>
          <h3>{title}</h3>
          <p>{text}</p>
        </div>""")

    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aieva</title>
<style>
  :root {
    --bg: #05050d;
    --panel: #0c0e1c;
    --line: rgba(255, 255, 255, .10);
    --text: #eff0f4;
    --muted: #9ea4c0;
    --primary: #0a26e6;
    --violet: #7c6cf0;
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; -webkit-text-size-adjust: 100%; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
          Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  body::before {
    content: "";
    position: fixed;
    inset: -40vh -25vw auto -25vw;
    height: 100vh;
    background:
      radial-gradient(55% 55% at 24% 34%, rgba(10, 38, 230, .34), transparent 68%),
      radial-gradient(45% 45% at 76% 16%, rgba(124, 108, 240, .24), transparent 70%);
    filter: blur(30px);
    pointer-events: none;
    z-index: 0;
  }
  .wrap { position: relative; z-index: 1; }

  nav {
    position: sticky;
    top: 0;
    z-index: 5;
    display: flex;
    align-items: center;
    gap: 28px;
    padding: 16px 32px;
    background: rgba(5, 5, 13, .72);
    backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--line);
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    font-size: 19px;
    font-weight: 700;
    letter-spacing: -.01em;
    color: var(--text);
  }
  .brand i {
    width: 11px; height: 11px;
    border-radius: 3px;
    background: var(--primary);
    display: inline-block;
  }
  nav a {
    color: var(--muted);
    text-decoration: none;
    font-size: 15px;
    transition: color .18s ease;
  }
  nav a:hover { color: var(--text); }

  header {
    max-width: 1120px;
    margin: 0 auto;
    padding: 96px 28px 0;
    text-align: center;
  }
  .eyebrow {
    display: inline-block;
    font-size: 12px;
    letter-spacing: .2em;
    text-transform: uppercase;
    color: var(--muted);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 7px 16px;
    background: rgba(255, 255, 255, .03);
  }
  h1 {
    margin: 26px 0 0;
    font-size: clamp(44px, 7.4vw, 78px);
    line-height: 1.04;
    letter-spacing: -.035em;
    font-weight: 700;
    background: linear-gradient(115deg, #ffffff 24%, #b9c9ff 60%, #c4b8ff 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  .lead {
    margin: 22px auto 0;
    max-width: 600px;
    font-size: 19px;
    color: var(--muted);
  }
  .hero {
    margin: 52px auto 0;
    max-width: 1060px;
    border-radius: 20px;
    overflow: hidden;
    border: 1px solid var(--line);
    background: var(--panel);
    box-shadow: 0 50px 130px -50px rgba(0, 0, 0, .95),
                0 0 90px -40px rgba(10, 38, 230, .55);
  }
  .hero img { display: block; width: 100%; }

  section { max-width: 1120px; margin: 0 auto; padding: 0 28px; }
  .features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 18px;
    margin-top: 76px;
  }
  .feature {
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 24px 22px 26px;
    background: linear-gradient(180deg, rgba(255, 255, 255, .04), rgba(255, 255, 255, 0));
  }
  .feature-icon {
    display: inline-flex;
    width: 42px; height: 42px;
    align-items: center; justify-content: center;
    border-radius: 12px;
    color: #9fb4ff;
    background: rgba(10, 38, 230, .20);
    border: 1px solid rgba(124, 108, 240, .30);
  }
  .feature-icon svg { width: 21px; height: 21px; }
  .feature h3 { margin: 16px 0 6px; font-size: 17px; letter-spacing: -.01em; }
  .feature p { margin: 0; font-size: 14.5px; color: var(--muted); }

  .gallery {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
    gap: 26px;
    margin-top: 26px;
    padding-bottom: 20px;
  }
  .shot { margin: 0; }
  .frame {
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid var(--line);
    background: var(--panel);
    box-shadow: 0 30px 80px -40px rgba(0, 0, 0, .9);
  }
  .frame img { display: block; width: 100%; }
  .shot figcaption { padding: 16px 4px 0; }
  .shot strong { display: block; font-size: 16px; letter-spacing: -.01em; }
  .shot span { display: block; margin-top: 5px; color: var(--muted); font-size: 14.5px; }

  footer {
    max-width: 1120px;
    margin: 92px auto 0;
    padding: 30px 28px 58px;
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-size: 14px;
  }
  @media (max-width: 720px) {
    header { padding-top: 58px; }
    .gallery { grid-template-columns: 1fr; }
    nav { gap: 18px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <nav>
    <span class="brand"><i></i>Aieva</span>
    <a href="#features">Features</a>
    <a href="#screens">Screens</a>
  </nav>

  <header>
    <span class="eyebrow">Mathematics edition</span>
    <h1>Mathematics you can touch.</h1>
    <p class="lead">A screen aware assistant for interactive boards: write an
       equation, move a parameter and watch the picture appear.</p>
    <div class="hero">{{HERO_IMAGE}}</div>
  </header>

  <section id="features">
    <div class="features">
{{FEATURES}}
    </div>
  </section>

  <section id="screens">
    <div class="gallery">
{{GALLERY}}
    </div>
  </section>

  <footer>Aieva &middot; Mathematics edition</footer>
</div>
</body>
</html>
"""

    page = (
        template.replace("{{HERO_IMAGE}}", hero_image)
        .replace("{{FEATURES}}", "\n".join(features))
        .replace("{{GALLERY}}", "\n".join(gallery))
    )
    return page


def main() -> int:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    page = PREVIEW / "index.html"
    page.write_text(build(), encoding="utf-8")
    size = page.stat().st_size
    print(f"wrote {page} ({size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
