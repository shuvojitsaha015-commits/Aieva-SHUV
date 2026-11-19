"""What should be done with the problem that was read.

The board is read by **Gemini**. It answers with the expression *and* with
an **intent** - what the teacher wants:

* ``solve`` - the answer (an equation to solve, a value to find),
* ``graph`` - the picture (a function to plot, a curve to see),
* ``both`` - the answer *and* the picture,
* ``none`` - there is no mathematics on the board.

The intent is **advisory**: when Gemini does not answer (no network, a
strange answer, an old server) the local rule based classifier decides
instead. The board must never stand still because the cloud had a bad day.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)

#: The intents the board understands.
INTENTS = ("solve", "graph", "both", "none")


@dataclass(frozen=True)
class Intent:
    """What has to be done with the problem."""

    #: Should the answer be computed?
    solve: bool = True
    #: Should the graph be drawn?
    graph: bool = True
    #: Where the decision came from (``gemini`` or ``rules``).
    source: str = "rules"
    #: The intent as it was written (``""`` when there was none).
    raw: str = ""

    def to_dict(self) -> dict[str, Any]:
        """The intent as a plain dictionary."""
        return {
            "solve": self.solve,
            "graph": self.graph,
            "source": self.source,
            "raw": self.raw,
        }


def from_text(text: str) -> Intent | None:
    """The intent of the model (``None`` when it did not say anything)."""
    value = (text or "").strip().lower()
    if value not in INTENTS:
        return None
    if value == "solve":
        return Intent(solve=True, graph=False, source="gemini", raw=value)
    if value == "graph":
        return Intent(solve=False, graph=True, source="gemini", raw=value)
    if value == "both":
        return Intent(solve=True, graph=True, source="gemini", raw=value)
    return Intent(solve=False, graph=False, source="gemini", raw=value)


def from_classification(classification: Any) -> Intent:
    """The intent of the local rules - the fallback when Gemini is silent.

    A problem that is only a function is plotted, everything else is solved
    (and plotted when it can be).
    """
    problem_type = str(getattr(classification, "problem_type", "") or "")
    if problem_type == "plot_only":
        return Intent(solve=False, graph=True, source="rules", raw="plot_only")
    return Intent(solve=True, graph=True, source="rules", raw=problem_type)


def decide(intent_text: str, classification: Any) -> Intent:
    """The intent of the board: Gemini first, the rules as the fallback."""
    from_gemini = from_text(intent_text)
    if from_gemini is not None:
        return from_gemini
    return from_classification(classification)


__all__ = ["INTENTS", "Intent", "decide", "from_classification", "from_text"]
