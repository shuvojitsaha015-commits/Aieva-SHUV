"""Visual theme for Aieva.

Everything that has a size or a colour lives here so that the smart-board rules
are applied consistently:

* all sizes are density independent (``dp`` / ``sp``) so the app scales from a
  phone to a 4K interactive board;
* every touch target is at least :data:`MIN_TOUCH_DP` (56 dp) tall;
* the palette is high contrast so it stays readable under classroom lighting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kivy.metrics import dp, sp

# --- palette (high contrast, readable on a bright classroom board) --------
# A deep indigo night with one vivid accent - the colours of the board.
BACKGROUND: tuple[float, float, float, float] = (0.020, 0.020, 0.051, 1)
SURFACE: tuple[float, float, float, float] = (0.055, 0.059, 0.125, 1)
SURFACE_ALT: tuple[float, float, float, float] = (0.098, 0.106, 0.200, 1)
CARD: tuple[float, float, float, float] = (0.063, 0.071, 0.150, 1)
BORDER: tuple[float, float, float, float] = (0.145, 0.157, 0.290, 1)
PRIMARY: tuple[float, float, float, float] = (0.039, 0.149, 0.902, 1)
ACCENT: tuple[float, float, float, float] = (0.486, 0.424, 0.941, 1)
WARNING: tuple[float, float, float, float] = (0.941, 0.663, 0.180, 1)
DANGER: tuple[float, float, float, float] = (0.941, 0.353, 0.353, 1)
TEXT: tuple[float, float, float, float] = (0.937, 0.941, 0.957, 1)
TEXT_MUTED: tuple[float, float, float, float] = (0.620, 0.643, 0.753, 1)

#: Minimum touch target for a smart board, in density independent pixels.
MIN_TOUCH_DP: int = 56
#: Default pen width on the whiteboard.
DEFAULT_PEN_WIDTH: float = 4.0

# --- metrics -------------------------------------------------------------
TITLE_BAR_DP: int = 64
BUTTON_HEIGHT_DP: int = MIN_TOUCH_DP
INPUT_HEIGHT_DP: int = 56
SLIDER_HEIGHT_DP: int = 48
PANEL_PADDING_DP: int = 12
GAP_DP: int = 8
#: The radius of a card or a panel, in density independent pixels.
RADIUS_DP: int = 14
#: The height of a tile of the home grid, in density independent pixels.
CARD_HEIGHT_DP: int = 116


def dp_size(value: float) -> float:
    """Convert a design value (dp) into pixels."""
    return dp(value)


def sp_size(value: float) -> float:
    """Convert a design value (sp) into pixels."""
    return sp(value)


@dataclass(frozen=True)
class PenPalette:
    """The colours offered by the whiteboard."""

    colours: dict[str, tuple[float, float, float, float]] = field(
        default_factory=lambda: {
            "black": (0.05, 0.05, 0.06, 1),
            "white": (1.0, 1.0, 1.0, 1),
            "red": (0.90, 0.20, 0.22, 1),
            "blue": (0.20, 0.45, 0.95, 1),
            "green": (0.15, 0.70, 0.35, 1),
            "yellow": (0.95, 0.80, 0.15, 1),
        }
    )

    def get(self, name: str) -> tuple[float, float, float, float]:
        return self.colours.get(name, self.colours["black"])

    def names(self) -> list[str]:
        return list(self.colours)


PEN_PALETTE = PenPalette()

#: Example inputs shown as hints in the input bar.
TEXT_EXAMPLES = ("y = m*x + c", "x^2 + y^2 = r^2", "y = a*x^2 + b*x + c")
LATEX_EXAMPLES = (r"y = m x + c", r"x^{2} + y^{2} = r^{2}", r"\frac{-b \pm \sqrt{b^2-4ac}}{2a}")


__all__ = [
    "ACCENT",
    "BACKGROUND",
    "BORDER",
    "BUTTON_HEIGHT_DP",
    "CARD",
    "CARD_HEIGHT_DP",
    "DANGER",
    "DEFAULT_PEN_WIDTH",
    "GAP_DP",
    "INPUT_HEIGHT_DP",
    "LATEX_EXAMPLES",
    "MIN_TOUCH_DP",
    "PANEL_PADDING_DP",
    "PEN_PALETTE",
    "PRIMARY",
    "RADIUS_DP",
    "SLIDER_HEIGHT_DP",
    "SURFACE",
    "SURFACE_ALT",
    "TEXT",
    "TEXT_EXAMPLES",
    "TEXT_MUTED",
    "TITLE_BAR_DP",
    "WARNING",
    "PenPalette",
    "dp_size",
    "sp_size",
]
