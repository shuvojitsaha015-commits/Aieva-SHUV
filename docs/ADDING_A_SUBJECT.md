# How to add a new subject (Biology, Chemistry, Physics, ...)

Aieva v1 ships **Mathematics only**. The architecture was built so that the
next subject is **one new directory** - no change in the core, no change in
the UI.

This document is the walk-through. It works for every subject that can be
described with a picture (Matplotlib) and a few steps.

---

## 1. The contract

Every subject is a **plugin**: a class that inherits from
`aieva.core.plugin_base.SubjectPlugin` and implements three methods.

| Method | What it does | Returns |
|---|---|---|
| `parse(parsed_input)` | normalises the raw text / LaTeX / OCR answer into something the subject understands | the same `ParsedInput` (with `sympy_expr` filled in) |
| `solve(parsed_input)` | solves the problem and explains it | a `SolveResult` (the answer, the steps, the warnings) |
| `visualize(parsed_input, **opts)` | draws the problem | a `VisualizationResult` (a Matplotlib figure + the parameters of the sliders) |

Two optional methods:

| Method | What it does |
|---|---|
| `create_session(parsed_input, **opts)` | returns an **interactive** session (figure + `set_param()`), so the UI can offer sliders |
| `capabilities()` | the list of the features of the subject - the UI builds its menus from it |

The class attributes describe the subject to the UI:

```python
name = "biology"                    # the key of the registry
display_name = "Biology"            # the button on the home screen
description = "Cells, genetics, ..."  # one line under the name
requires = ("rdkit",)               # the optional packages (checked at the start)
ui_hints = {"viewer": "matplotlib", "editor": "text"}
order = 20                          # the position in the subject list
```

---

## 2. The five steps

### Step 1 - copy the template

```bash
cp -r aieva/plugins/_template_plugin aieva/plugins/biology
```

The directory name must **not** start with an underscore, otherwise the
registry ignores it (that is how the template itself stays invisible).

### Step 2 - write the plugin

`aieva/plugins/biology/plugin.py`:

```python
from __future__ import annotations

from typing import Any

import matplotlib
matplotlib.use("Agg", force=False)
import matplotlib.pyplot as plt

from aieva.core.errors import ParseError
from aieva.core.models import ParsedInput, SolveResult, Step, VisualizationResult
from aieva.core.plugin_base import SubjectPlugin


class BiologyPlugin(SubjectPlugin):
    name = "biology"
    display_name = "Biology"
    description = "Cells, genetics and the heart."
    requires = ()
    ui_hints = {"viewer": "matplotlib", "editor": "text"}
    order = 20

    def parse(self, parsed_input: ParsedInput) -> ParsedInput:
        raw = (parsed_input.raw or "").strip()
        if not raw:
            raise ParseError("Nothing to parse")
        # the biology specific reading of the input
        parsed_input.sympy_expr = raw
        return parsed_input

    def solve(self, parsed_input: ParsedInput) -> SolveResult:
        return SolveResult(problem_type="biology", answer_text="...", steps=[])

    def visualize(self, parsed_input: ParsedInput, **opts: Any) -> VisualizationResult:
        figure, axes = plt.subplots()
        axes.plot([0, 1], [0, 1])
        return VisualizationResult(figure=figure, parameters=[], meta={"kind": "biology"})
```

### Step 3 - check the rules

* **no Kivy import** - the plugin is headless and testable
  (`tests/unit/test_plugin_metadata.py` proves that the core and the plugins
  never import Kivy);
* **no `eval` / `exec`** on the text of the teacher or of the LLM;
* no secret in the code - the configuration comes from
  `aieva.config.get_settings()`;
* the heavy work (SymPy, a big data set, a network call) belongs into a
  **worker thread** - the UI calls the plugin through
  `aieva.ui.workers.run_in_background`.

### Step 4 - test it

```python
# tests/unit/test_biology.py
from aieva.core.models import ParsedInput
from aieva.plugins.biology.plugin import BiologyPlugin


def test_the_plugin_parses():
    plugin = BiologyPlugin()
    parsed = plugin.parse(ParsedInput(raw="cell"))
    assert parsed.sympy_expr is not None
```

The plugin is found automatically - the registry scans
`aieva/plugins/*/plugin.py` at the start of the application.

### Step 5 - the subject appears in the UI

The home screen is built from the metadata of the registry
(`aieva/ui/screens/home.py`), so the new subject button shows up without a
single change in the interface. The screens of the mathematics stay as they
are; a subject with its own screens gets its own module in
`aieva/ui/screens/`.

---

## 3. What the subject gets for free

| Service | Where | What it does |
|---|---|---|
| the safe parser | `aieva/core/safe_parse.py` | parses a text expression without `eval` |
| the LaTeX adapter | `aieva/core/latex_adapter.py` | LaTeX -> SymPy |
| the OCR | `aieva/core/ocr/` | reads the board (in the background) |
| the LLM | `aieva/core/llm/` + `server/` | explains and structures (through the fog server) |
| the cache | `aieva/core/cache.py` | the OCR results and the rendered pictures |
| the document reader | `aieva/core/docs_parser/` | the equations of a PDF / PPTX / DOCX |
| the plot canvas | `aieva/ui/widgets/plot_canvas.py` | shows the figure (Kivy canvas or PNG texture) |
| the sliders | `aieva/ui/widgets/slider_panel.py` | the parameters of the session |
| the steps panel | `aieva/ui/widgets/steps_panel.py` | the step by step solution |
| the history | `aieva/core/history.py` | the recent inputs (per subject) |
| the settings | `aieva/core/user_settings.py` | the server URL, the quality, the offline mode |

---

## 4. The recipe for a subject with its own screens

1. the plugin (above) for the maths of the subject;
2. a screen in `aieva/ui/screens/<subject>.py` that calls **only** the
   plugin (never the maths directly);
3. a button on the home screen - but only when the subject needs a screen of
   its own; the subject button itself comes from the metadata.

The mathematics plugin (`aieva/plugins/math/`) is the reference: seven
modules, one plugin class, eight screens.

---

## 5. The checklist

- [ ] the directory is `aieva/plugins/<subject>/` (no leading underscore);
- [ ] the class inherits from `SubjectPlugin` and implements `parse`,
      `solve` and `visualize`;
- [ ] `name`, `display_name` and `description` are set;
- [ ] `requires` lists the optional packages (the subject is hidden when
      they are missing);
- [ ] no Kivy import, no `eval`, no secret;
- [ ] a unit test per method and an integration test per screen;
- [ ] the subject appears on the home screen without a change in the UI.
