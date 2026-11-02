# Aieva - Build Progress Log

> Append-only phase log. Newest entry at the bottom.
> Plan of record: `AIEVA_IMPLEMENTATION_PLAN.md` (13 phases, 0-12).

---

## Phase 0 - Manual prerequisites

**Status:** DONE (documentation only - no code depends on it)

### Done
- Created `docs/MANUAL_STEPS_NEEDED.md` with the exact checklist from the plan
  (Python 3.11, GitHub repo, Gemini key, Wolfram AppID, OpenAI key, server hosting,
  test hardware, Docker, test images) plus a "how to unblock" section and a status table.
- Created `../.env` with exactly the variables required by the plan:
  `GEMINI_API_KEY`, `GEMINI_MODEL`, `OPENAI_API_KEY`, `WOLFRAM_APP_ID`,
  `AIEVA_SERVER_URL`, `AIEVA_OFFLINE_MODE`, `AIEVA_CACHE_DIR`.
- Every API-key / hardware dependency is mocked or optional from this point on.

### Left / blockers
- **BLOCKER (human):** no Gemini API key yet -> the server runs in `AIEVA_MOCK_LLM=true`
  mode and the app falls back to manual LaTeX input.
- **BLOCKER (human):** no smart board identified yet -> device-specific work in Phase 11
  is planned against a generic Android target.

---

## Phase 1 - Scaffold, tooling and a running "hello" app

**Status:** DONE

### Done
- Full repository layout from plan section 3 (packages, `server/`, `tests/`, `docs/`,
  `scripts/`, GitHub Actions workflow).
- `pyproject.toml` with ruff + black + pytest configuration (`testpaths=tests`,
  markers `live` / `ui` / `slow`).
- `requirements.txt`, `requirements-server.txt`, `requirements-dev.txt`,
  `requirements-optional.txt` (optional extras never imported by the core).
- `.gitignore` (venv, `.env`, `.aieva_cache`, `__pycache__`, `bin/`, `.buildozer/`).
- `README.md` with install / `.env` / run / test / APK / troubleshooting sections.
- `aieva/config.py`: typed frozen `Settings` dataclass, `.env` loading through
  `python-dotenv`, defaults, `offline_mode`, `cloud_enabled` helper.
- `aieva/core/errors.py`: `AievaError`, `ParseError`, `OcrError`, `SolveError`,
  `VisualizationError`, `CloudError` (+ `PluginError`, `CacheError`).
- `aieva/ui/app.py` + `main.kv`: Kivy app titled "Aieva" with a 1280x720 desktop window.
- `.github/workflows/ci.yml`: ruff, black --check, pytest under `xvfb-run`,
  server smoke test in mock mode.
- Smoke tests: `import aieva`, `Settings` loads, error hierarchy.

### Left / blockers
- The local sandbox has **Python 3.13**, not 3.11. Everything in the stack supports
  3.11-3.13; 3.11 is only required for the Buildozer toolchain (Phase 11).
- Headless UI testing needs a virtual display: `Xvfb :99` (installed) or `xvfb-run`.
  `scripts/run_tests.sh` starts it automatically.

---

## Phase 2 - Core: models, safe parsing, plugin system, cache

**Status:** DONE

### Done
- `aieva/core/models.py`: `Step`, `ParsedInput`, `SolveResult`, `VisualizationResult`,
  `ParamSpec` (dataclasses, JSON round-trip helpers).
- `aieva/core/safe_parse.py`: `parse_text_expression`, `parse_equation`, `split_equation`,
  `validate_expression`.
  - strict character allow-list, deny-list of Python words, **no attribute access**;
  - SymPy `parse_expr` with a restricted `global_dict` (`__builtins__` empty) and a
    whitelisted `local_dict`; `^` -> power, implicit multiplication (`2x`, `3(x+1)`),
    `sin x` all work.
- `aieva/core/latex_adapter.py`: `latex_to_sympy` / `latex_to_equation` /
  `latex_to_sympy_list` / `normalize_latex` / `sympy_to_latex`.
  Three backends: `sympy.parsing.latex.parse_latex` (antlr 4.11 runtime added to
  `requirements.txt`) -> `latex2sympy2` (optional extra) -> regex normaliser.
  Integrals / sums / limits / matrices are rejected with a clear message.
- `aieva/core/plugin_base.py`: `SubjectPlugin` ABC (`parse`, `solve`, `visualize`,
  `capabilities`).
- `aieva/core/plugin_registry.py`: automatic discovery via `importlib` + `inspect`,
  `get_plugin("math")`, `available_plugins()`.
- `aieva/core/cache.py`: sha256 keyed disk cache with TTL, JSON + bytes payloads,
  `get/set/clear/stats`, atomic writes.
- `aieva/plugins/math/plugin.py`: `MathPlugin` (parse is live; solve/visualize delegate
  to the Phase 3/8 engines).
- Tests: 30 hostile strings all rejected, 27 LaTeX expressions verified, plugin
  auto-discovery from a dropped-in package, cache TTL / corruption / clearing.

### Left / blockers
- `aieva/plugins/math/solver.py` and `equations.py` are still stubs -> `MathPlugin.solve`
  and `.visualize` raise until Phase 3 / Phase 8.

---

## Phase 4 - UI shell: whiteboard, input bar, plot modal with sliders (completes 1.a)

**Status:** DONE

### Done
- `aieva/ui/theme.py`: palette, `dp`/`sp` helpers, 56 dp minimum touch target,
  pen palette, example inputs.
- `aieva/ui/workers.py`: `run_in_background()` - every slow job runs in a worker
  thread and comes back through `Clock.schedule_once`.
- `aieva/ui/widgets/toast.py`: own toast implementation (Kivy 2.3 has no
  `kivy.uix.toast`).
- `aieva/ui/widgets/input_bar.py`: text field + *Text* / *LaTeX* toggle + *Plot*
  button, example hints.
- `aieva/ui/widgets/whiteboard.py`: touch drawing, pen colours, eraser, clear,
  undo, configurable palm rejection, `export_to_image()` (Pillow based, so it
  works headless).
- `aieva/ui/widgets/slider_panel.py`: one labelled Kivy `Slider` per parameter
  with a live value and `-` / `+` fine tuning buttons.
- `aieva/ui/widgets/plot_modal.py`: `Popup` at 85 % of the window with the
  `FigureCanvasKivyAgg`, the slider panel, *Reset params*, *Copy equation
  (LaTeX)* and *Close*; redraws throttled to ~30 Hz with `Clock.schedule_once`.
- `aieva/ui/screens/home.py` (modes + equation history), `screens/whiteboard.py`
  (drawing screen + placeholder screen helper).
- `aieva/core/history.py`: JSON history of the equations (no database in v1).
- `aieva/ui/app.py`: `ScreenManager` with *Home*, *Whiteboard*, *Solve from
  Screen* (placeholder) and *Documents* (placeholder); typing an equation parses
  it in a worker thread and opens the plot modal; `ParseError` becomes a toast.
- `docs/DEMO_SCRIPT.md` with the eight demo scenarios (section A = the 1.a demo).
- Headless UI tests (`tests/integration/test_plot_modal.py`): the modal opens,
  a slider change updates the plotted data, reset restores the defaults, the
  fine tuning buttons move one step, the input bar switches modes, the
  whiteboard draws and exports, palm rejection ignores large contacts.
- `tests/conftest.py` starts a virtual X server (Xvfb) when no display exists.

### Left / blockers
- The *Solve from Screen* and *Documents* buttons are placeholders (Phase 8 /
  Phase 10).
- The palm rejection relies on the contact size reported by the platform; on
  platforms that do not report it the touch is never rejected (the setting is
  exposed for the board tuning in Phase 11).

---

## Architecture correction (team decision, after Phase 4)

Two corrections were requested by the team and applied **before** Phase 5:

1. **No APK is built.** The product targets Android smart boards, but the
   packaging step is out of scope for this cycle. Phase 11 therefore becomes
   "Android / smart-board readiness" (dependency hygiene, DPI scaling, board
   settings, palm-rejection tuning, performance) and the officially supported
   deliverable is the source application + fog server. Recorded as ADR-001 in
   `docs/DECISIONS.md`.
2. **The architecture accounts for the whole product.** Only mathematics is
   implemented, but nothing in the core or the UI is mathematics specific any
   more. Recorded as ADR-002 in `docs/DECISIONS.md`.

### What changed in the code

- `aieva/core/plugin_base.py`: new `PluginMeta` dataclass (name, display name,
  description, **optional dependencies**, capabilities, **UI hints**, order) and
  `SubjectPlugin.meta()` / `.is_available()`. A plugin can therefore declare
  `requires = ("rdkit",)` and the app knows it is not usable yet.
- `aieva/core/plugin_registry.py`: `subjects()` / `available_subjects()` /
  `subject_metas()` - the UI is built from the registry, never hard-coded.
- `aieva/core/models.py`: new `VisualizationSession` **protocol**
  (`figure`, `parameters`, `set_param`, `set_params`, `reset_params`). The UI
  drives this protocol, so Biology/Chemistry can expose their own sliders.
- `aieva/core/plugin_base.py` + `aieva/plugins/math/plugin.py`: new
  `SubjectPlugin.create_session()` hook (returns `None` for plugins without
  dynamic parameters); the maths plugin returns a `PlotSession`.
- `aieva/ui/screens/home.py`: the subject list is generated from the registry
  metadata; the history is subject aware.
- `aieva/core/history.py`: `HistoryEntry.subject` + `History.recent(count,
  subject)`.
- `aieva/ui/app.py`: resolves the plugin through `get_plugin(subject)` instead
  of importing `MathPlugin` directly.
- New tests: `tests/unit/test_plugin_metadata.py` (metadata, a second subject
  in a temp package, the session protocol, and a guard that **no core or plugin
  module imports Kivy**).

### Left / blockers
- The `SubjectPlugin.solve` / `visualize` return types are still generic
  (`Any`) so that non-mathematical plugins can return their own models; the
  maths plugin keeps the concrete types.

---

## Phase 5 - Feature 1.b: calculus visualisation

**Status:** DONE

### Done
- `aieva/core/numeric.py` (**brought forward from Phase 11** so that SciPy is
  optional from the start - it matters for the Android target): adaptive
  Simpson, Gauss-Kronrod (G7,K15) quadrature with a real error estimate,
  trapezoid/Simpson rules for sampled data, Brent's root finder,
  Ramer-Douglas-Peucker simplification, shoelace area.
- `aieva/plugins/math/calculus.py`:
  - `compute_integral` - exact value via `sympy.integrate`, numerical value via
    SciPy **or** the internal quadrature; a warning is raised when the two
    differ by more than 1e-6 or when SymPy returns an unevaluated `Integral`.
  - `integral_view` - shaded area (positive green / negative red), dashed
    bounds, annotated exact and numerical value.
  - `riemann_view` / `riemann_sum` - `left | right | midpoint | trapezoid`
    (rectangles / polygons), the sum, the exact value and the error.
  - `tangent_view` / `TangentSession` - symbolic derivative, moving tangent
    line, slope readout; `TangentSession.step(dt)` is driven by the Kivy clock
    (no Matplotlib timer loop).
  - `area_between` - intersections via `sympy.solve` with a numeric fallback
    (`brentq` on a sign scan), piecewise integration of `|f-g|`, shaded region.
  - `area_from_points`, `polygon_area`, `simplify_polygon`, `shape_area_view`
    - the "draw a shape, compute its area" pipeline with a
    *units per pixel* calibration.
- `aieva/ui/screens/calculus.py`: the **Calculus** screen with the mode panel
  (Integral / Riemann / Tangent / Area between / Shape area), the bound, `n`
  and `x0` sliders, the Riemann method spinner and the play/pause animation.
  Reachable from the home screen; every computation runs in a worker thread.
- Tests: `tests/unit/test_numeric.py` (17 tests), `tests/unit/test_calculus.py`
  (27 tests, including the required reference values
  int_0^pi sin x = 2, int_0^1 x^2 = 1/3, area between x and x^2 = 1/6,
  shoelace area of the unit square = 1, midpoint Riemann sum with n=1000 within
  1e-4) and `tests/integration/test_calculus_screen.py` (UI, headless).

### Left / blockers
- The "shape area" mode still needs the whiteboard strokes to be piped in
  (the whiteboard already exports the image; the *ordered points* extraction is
    wired in the Phase 8 whiteboard -> OCR flow).

---

## Phase 6 - Feature 1.c: linear algebra and complex numbers

**Status:** DONE

### Done
- `aieva/plugins/math/linalg.py` (headless, no Kivy import):
  - `parse_vectors` / `VectorSpec` - `a=(1,2), b=(3,1)` syntax with a strict
    2D/3D check.
  - `vector_view` - add / subtract / scale / dot / cross with an annotated
    result panel (the cross product needs 3D vectors).
  - `parse_matrix` / `as_matrix` / `transform_matrix` - square matrices only.
  - `matrix_view` - the unit square is transformed by M, the grid warps with
    it, the determinant is reported; optional `rotation` (deg) and `shear`
    sliders add a transformation on top of the matrix.
  - `eigen_values` (NumPy) + `exact_eigen_values` (SymPy) and `eigen_view` -
    the eigen vectors are drawn with their image `M v`; a matrix with complex
    eigen values produces a warning instead of a wrong picture.
  - `parse_system` / `solve_system` - `2x+y=5; x-y=1`; the solver reports
    `unique`, `none` (parallel lines) or `infinite` (coincident lines).
  - `system_view` - both lines are drawn and the intersection is marked.
  - `cube_view` - the 3x3 matrix maps the unit cube.
- `aieva/plugins/math/complexnum.py` (headless):
  - `parse_complex` / `format_complex` - `3 + 4i`, `-2i`, `5`.
  - `argand_view` - the Argand diagram with the unit circle, |z| and arg(z);
    operations `none | add | multiply | multiply_i | conjugate | power |
    roots`; the n-th roots are returned in `meta["roots"]`.
  - `domain_coloring` - the optional stretch goal behind a flag.
- `aieva/ui/widgets/controls.py` (**new**) - shared Kivy controls:
  `slider_row`, `matrix_grid`, `labelled_input`, `mode_button`; the calculus
  and the linear algebra screens use the same look and touch sizes.
- `aieva/ui/screens/linalg.py` (**new**) - the **Linear Algebra** screen with
  the modes Vectors / Matrix / Eigen / System / Complex, a 2x2 / 3x3 matrix
  entry grid, the rotation and shear sliders and the complex operation
  spinner. Wired into `aieva/ui/app.py` and the home screen.
- `aieva/plugins/math/plugin.py`: the capability list now advertises
  `calculus`, `linear_algebra` and `complex_numbers`.
- Tests: `tests/unit/test_linalg.py` (29 tests) and
  `tests/integration/test_linalg_screen.py` (6 tests, headless UI).

### Acceptance criteria (all verified)
- The rotation by 90 degrees `[[0,-1],[1,0]]` has the complex eigen values
  `+/- i` (and the view warns that there is no real eigen vector).
- `diag(2,3)` has the eigen values 2 and 3.
- The system `2x+y=5; x-y=1` is solved to `(2, 1)`.
- Parallel lines are detected: `x+y=1; 2x+2y=5` -> no solution and
  `x+y=1; 2x+2y=2` -> infinitely many solutions.
- The three cube roots of `z^3 = 1` are three points on the unit circle.

### Left / blockers
- The 3D cube view is drawn with Matplotlib's static 3D projection; the
  hand-rolled drag / pinch rotation of the plan arrives in Phase 7.
- The vector operations only work with explicit component vectors; a symbolic
  vector (for example `(x, x**2)`) is not accepted yet.

---

## Phase 7 - Feature 1.d: 2D and 3D plotting

**Status:** DONE

### Done
- `aieva/plugins/math/plot3d.py` (headless):
  - `parse_plot_spec` understands `z = f(x,y)` (surface), `x=..., y=..., z=...`
    in `t` (parametric curve) or in `u,v` (parametric surface), `r = f(theta)`
    (polar) and `x = ..., y = ...` / `y = f(x)` (2D).
  - `detect_dimension` routes the input: two free variables with a `z` go to
    3D, everything else stays 2D.
  - `surface_view` (colour map + optional wireframe + optional contour
    projection), `parametric_curve_view`, `parametric_surface_view`,
    `polar_view`, `parametric_2d_view`.
  - The mesh resolution follows the quality setting `low 30 / medium 60 /
    high 120`; NaN, infinite and absurd values (> 1e6) are masked.
  - Parameters (`z = a*sin(x)*cos(y)`) are reported as `ParamSpec`s and are
    driven by the same slider system as the 2D plots.
  - `Plot3DSession` - the camera (`elevation`, `azimuth`, `zoom`) is separate
    from the data, so a drag never recomputes the surface; the quality drops
    to `low` during an interaction and is restored on touch up.
- `aieva/ui/widgets/plot3d_view.py` (**new**) - `Plot3DCanvas` (a Matplotlib
  canvas that rotates instead of panning) and `Plot3DView` (the canvas plus
  the button fallback: rotate left / up / down / right, zoom in / out, reset
  and an auto-rotate toggle). One finger drag rotates, a two finger pinch
  zooms, the redraw is throttled to 30 Hz.
- `aieva/ui/screens/plot3d.py` (**new**) - the **3D Plots** screen with the
  expression input, the quality spinner, the wireframe / contour switches,
  the parameter sliders and the rotatable view. Wired into `aieva/ui/app.py`
  and the home screen.
- Tests: `tests/unit/test_plot3d.py` (27 tests) and
  `tests/integration/test_plot3d_screen.py` (6 tests, headless UI - including
  a simulated drag that has to rotate the camera).

### Acceptance criteria (all verified)
- `z = x**2 + y**2`, `z = sin(x)*cos(y)`, the sphere
  `x = cos(u)*cos(v), y = cos(u)*sin(v), z = sin(u)` and the helix
  `x = cos(t), y = sin(t), z = t` all render.
- The routing test picks 3D for the surfaces / curves and 2D for the polar and
  the plain functions.
- The buttons rotate, zoom and reset; a one finger drag rotates the camera.

### Left / blockers
- The pinch gesture is implemented on the canvas but cannot be verified
  without a real multi touch screen - the button fallback is the guarantee.
- The 3D redraw is Matplotlib's (about 100-250 ms for a medium mesh); the
  auto-rotate therefore runs at 20 Hz and the drag lowers the mesh.

---

## Instructor request - background OCR first

**Status:** scheduled for Phase 8 (the OCR pipeline) - see the note below.

The instructor asked for an application that **runs in the background and
performs the OCR** as the first visible piece of work. Phase 8 therefore
delivers, in this order:

1. `aieva/core/ocr/` - the OCR service (Gemini Vision, plus a mock backend
   that needs no key), the image pre-processing (Pillow / NumPy only) and a
   **background worker** that processes the requests off the UI thread.
2. `server/` - the FastAPI fog server with `POST /api/math/ocr`, the
   `X-Aieva-Key` header, the rate limit and the mock mode.
3. The desktop app talks to the worker through the same HTTP API, so the
   board never blocks on the OCR call.

---

## Phase 8 - Feature 1.e: fog server, OCR pipeline and the solver

**Status:** DONE

### Done

**The background OCR (the instructor request)**
- `aieva/core/ocr/worker.py`: `OcrWorker` - a daemon thread with a queue. A
  capture is submitted and the caller returns immediately; the result is
  delivered through a callback (the app hops back to the Kivy thread with
  `Clock.schedule_once`). `OcrWatcher` - a service that watches a folder,
  reads every new image and writes the result as JSON into an outbox.
- `python -m aieva.core.ocr.worker --inbox DIR --outbox DIR [--mock] [--once]`
  and `scripts/run_ocr_worker.sh` - the background application that performs
  the OCR. It needs no API key (the mock engine) and talks to the Aieva
  server when one is running.
- Inside the app the worker starts with the application (`AievaApp.build`)
  and stops with it (`on_stop`).

**The OCR itself**
- `aieva/core/ocr/preprocess.py`: grayscale, autocontrast, deskew (the skew
  is estimated with the projection profile), 3x3 median denoise, adaptive
  threshold, auto crop and upscale - **Pillow and NumPy only** (no OpenCV,
  so it also runs on a weak board).
- `aieva/core/ocr/engines.py`: `OcrEngine` + `GeminiOcr` (through the
  server), `ManualOcr` (the user types it), `Pix2TextOcr` (optional) and
  `MockOcr` (the tests and the offline demo).
- `aieva/core/ocr/pipeline.py`: preprocess -> try the engines in order ->
  validate every answer with the SymPy parser -> the first parsable answer
  wins -> otherwise a result with `needs_manual_input` (the UI turns it into
  an editable box prefilled with the guess). The results are cached by the
  hash of the image.
- `aieva/core/ocr/capture.py`: `CanvasSource` (the whiteboard), 
  `DesktopScreenSource` (`PIL.ImageGrab`) and `AndroidProjectionSource`
  (a stub - Phase 11).

**The server (`server/`)**
- `GET /health`, `POST /api/math/ocr`, `POST /api/math/explain`,
  `POST /api/math/wordproblem` - documented in `docs/API_CONTRACT.md`.
- The shared `X-Aieva-Key` header, a rate limit of 30 requests per minute
  and per IP, the size limits (5 MB per image, 4000 characters per text),
  two retries with an exponential backoff, strict JSON answers
  (`response_mime_type="application/json"`), a repair prompt when the answer
  is not JSON, and the mock mode (`AIEVA_MOCK_LLM=true`).
- `Dockerfile`, `scripts/run_server.sh`, `server/schemas.py`,
  `server/services/gemini.py`, `server/routers/*`.
- The model is configurable and the default was updated to
  `gemini-3.8-flash` - `gemini-2.0-flash` was shut down on 1 June 2026
  (checked against <https://ai.google.dev/gemini-api/docs/models>).

**The solver (feature 1.e)**
- `aieva/plugins/math/classify.py`: the rule based classifier with the
  types `equation_solve | inequality | system | derivative | integral |
  definite_integral | limit | simplify | expand_factor | matrix_op |
  plot_only | word_problem` (an LLM fallback only when the rules are unsure).
- `aieva/plugins/math/solver.py`: SymPy solves everything, every symbolic
  call runs with a 10 s time limit, the steps are generated deterministically
  from SymPy (isolate / complete square / quadratic formula with the
  discriminant, the derivative rules, the integral) and the LLM only adds the
  natural language around them. `verify_answer` compares an LLM answer with
  the SymPy answer.
- `aieva/ui/widgets/steps_panel.py`: the scrollable step list; the formula
  is rendered with Matplotlib's mathtext into a texture (with a text
  fallback).
- `aieva/ui/widgets/region_selector.py`: the draggable region overlay with
  confirm / cancel.
- `aieva/ui/screens/solver.py`: the **Solve from Screen** screen - capture,
  region, OCR in the background, the editable escape hatch, the steps and a
  **Visualise** button. Reachable from the whiteboard ("Solve board") and
  from the home screen.

### Acceptance criteria (all verified)
- The server tests (17) cover the health route, the mock mode, the model
  answer, the size limits, the API key, the rate limit and the retries.
- The OCR tests (18) cover the pre-processing, the engines, the pipeline, the
  cache and the **needs manual input** path.
- The solver tests (46) solve **34 problems** over all the problem types and
  check them against the known answers.
- The full local run: the server was started in mock mode, the app read a
  picture through it (`OCR result -> plain "y = x**2 + 3*x" -> classify ->
  solve`), and the background worker wrote `board.json` into the outbox.
- `pytest`: **396 tests, all green**; `ruff check .` and `black --check .`
  are clean.

### Left / blockers
- The Android screen projection is still a stub (Phase 11); the whiteboard
  and the desktop capture work today.
- The real Gemini call is written but was never executed (no key in the
  sandbox) - the mock mode and the model answer are tested.
- The word problem templates are Phase 9; the classifier already recognises
  a word problem and the server already answers with the structured model.

---

## Phase 9 - Word problems: the four templates

**Status:** DONE

### Done
- `aieva/plugins/math/wordproblems.py`: the structured model of a word
  problem (`WordProblem`, `ProblemVariable`, `WordProblemSolution`), the
  validation of the **untrusted** LLM answer (`from_dict` drops everything
  that is not a string / a number), the variable table for SymPy
  (`symbols()`), the sliders (`slider_specs()`), the **"Here is how I
  understood the problem" card** (`confirmation_card()`), the sanity checks
  (`_sanity_checks()`: a negative time, a negative value, a missing unit),
  the live session (`WordProblemSession`: a slider changes a value, the
  problem is solved and drawn again) and the **offline fallback**
  (`local_model()`: the keywords pick the template, the numbers in the text
  become the variables).
- `aieva/plugins/math/templates/`: the **four** template categories of the
  plan -
  - `kinematic.py`: the projectile (the parabola, the velocity vectors at
    t = 0, T/2 and T, the apex and the range marked) **and** the uniform
    motion (the position against the time, the meeting point marked);
  - `optimization.py`: the objective with the constraint, the maximum
    marked and annotated (the fence / box problems);
  - `rate.py`: the quantity against the time with the net rate **plus** a
    tank diagram with the level;
  - `geometry.py`: the shapes with the labelled dimensions (rectangle,
    circle, triangle, right triangle) drawn with Matplotlib patches.
  `templates/__init__.py` maps the problem type to the module
  (`get_template()`), so a new template is one file plus one line.
- `aieva/ui/screens/wordproblem.py`: the **Word Problem** screen - the text
  field, the server call (in a worker thread), the confirmation card with
  **editable values**, "Confirm and solve", the steps, the picture, the
  sliders and the **Kivy Clock animation of the ball** along the
  trajectory. When the server is not reachable the local model is used, so
  the screen also works offline.
- `server/routers/wordproblem.py`: `geometry` added to the supported types;
  the schema is validated with pydantic and a broken JSON answer is
  repaired once (Phase 8).
- `tests/fixtures/golden_json/`: **15 curated problems** (3 per template)
  with their golden JSON.
- `tests/unit/test_wordproblems.py` (51 tests): every curated problem gives
  the right number **and** a figure that can be written out; the hostile
  model, the missing variable, the bad angle, the empty tank, the same
  speed and the missing objective are all refused with a clear error.
- `tests/integration/test_wordproblem_screen.py` (5 tests, headless): the
  card, the solve, an edited value changes the answer, the animation starts
  and stops.
- `tests/live/test_wordproblem_live.py`: the live test against the real
  Gemini (skipped without a key).

### Acceptance criteria (all verified)
- 15 curated problems (the plan asks for 12 = 3 per template) with golden
  JSON; every one of them produces the correct numeric answer and a
  rendered figure in the tests (the LLM is mocked).
- The four template categories are fixed; `mixture` and `unsupported` are
  known in the schema but are not drawn - the user gets a plain message.
- The sanity checks show their warnings in the screen.
- `pytest`: **452 tests + 2 skipped (the live tests), all green**;
  `ruff check .` and `black --check .` are clean.

### Left / blockers
- The **mixture** template is in the schema of the plan but was left out on
  purpose (the scope of v1 is the four categories); it is a follow-up.
- The live test against the real Gemini was never executed (no key in the
  sandbox) - the mock mode and the local fallback are tested.

---

## Phase 10 - Document input (PDF / PPTX / DOCX)

**Status:** DONE

### Done
- `aieva/core/docs_parser/omml.py`: a **minimal OMML -> LaTeX converter**
  (the Office Math Markup of Word and PowerPoint). It knows the fractions,
  the scripts, the roots, the delimiters, the sums and integrals, the
  accents, the functions and the matrices; the operators (`≤`, `∑`, `√`,
  `∞`, ...) are translated; everything else keeps its text. It only reads
  the XML - no `eval` / `exec`.
- `aieva/core/docs_parser/docx.py`: the paragraphs, the tables and the
  pictures of a `.docx`; every OMML formula becomes a candidate with LaTeX.
- `aieva/core/docs_parser/pptx.py`: the shapes, the tables and the pictures
  of a `.pptx`; the picture gets its position on the slide (the bbox).
- `aieva/core/docs_parser/pdf.py`: the text of the pages (the lines that
  look like a formula), the embedded pictures and - for a **scanned** page
  (a page without any text) - the rendered page as an image. The optional
  `marker-pdf` package is detected (`marker_available()`).
- `aieva/core/docs_parser/extract.py`: the common part -
  `EquationCandidate(page, bbox, latex, text, image, source)`, the
  dispatcher `extract_equations(path)` (only `.pdf`, `.pptx`, `.docx`),
  `document_kind()`, `page_count()` and `unsupported_message()` (the clear
  message for `.doc` / `.ppt`).
- `aieva/ui/screens/documents.py`: the **Documents** screen - the file
  chooser, the page limit (lazy, by page), the list of the found equations
  and the two actions "Solve it" and "Plot it". The pictures go through the
  OCR pipeline (in a worker thread); the reading itself also runs in a
  worker thread, so the UI is never blocked.
- `scripts/make_fixtures.py` builds the four fixtures (so they can be
  rebuilt at any time).
- `tests/unit/test_docs_parser.py` (23 tests) and
  `tests/integration/test_documents_screen.py` (7 tests, headless).

### Acceptance criteria (all verified)
- The fixtures are in `tests/fixtures/docs/`: `equations.docx` (two OMML
  formulas), `slide.pptx` (an equation **picture** plus a formula as text),
  `text.pdf` (two formulas as text) and `scanned.pdf` (a picture only).
- The test extracts at least the expected number of equations per file:
  2 LaTeX from the docx, 1 picture + 1 text from the pptx, 2 texts from
  the text PDF and 1 scanned page from the other PDF.
- `pytest`: **482 tests + 2 skipped (the live tests), all green**;
  `ruff check .` and `black --check .` are clean.

### Left / blockers
- The LaTeX of a formula that was written as **text** (a PDF) stays plain
  text - it is parsed by the maths core, not converted to LaTeX. That is
  what `marker-pdf` would improve (it is optional and not installed).
- The old binary formats (`.doc`, `.ppt`) are refused with a clear message
  instead of being converted.

---

## Phase 11 - Android / smart-board readiness (no APK)

**Status:** DONE (the re-scoped phase - see ADR-001)

> The plan asked for an APK in this phase. The team decided **not to build
> one**: the desktop build is the supported target and the code stays
> Android-compatible. The rest of the phase (the renderer abstraction, the
> settings, the DPI / touch / palm work) was implemented as planned.

### Done
- `aieva/ui/widgets/plot_canvas.py`: the **PlotCanvas abstraction**. The
  figure is shown with the Kivy Matplotlib canvas (`kivyagg`) or - when that
  backend is not available (some Android builds) - as a **PNG texture** in a
  normal image widget. Every screen uses the abstraction, so the backend is
  a detail and not a change in the screens.
- `aieva/core/user_settings.py`: the settings a teacher changes while the
  application is running (the server URL, the quality, the offline mode, the
  thickness of the pen, the palm rejection). They are stored as JSON in the
  cache directory and are applied to the environment at the start.
- `aieva/ui/screens/settings.py`: the **Settings** screen with the server
  URL, the quality (low / normal / high), the offline mode, the pen
  thickness and the palm threshold.
- The whiteboard takes the pen width and the palm rejection from the user
  settings (`WhiteboardScreen.apply_settings`); the quality of the user maps
  to the mesh of the 3D renderer (`low` -> 30, `normal` -> 60, `high` -> 120).
- The home screen has a **Settings** button; the application applies the
  stored settings before the first screen is used.
- `docs/ANDROID_READINESS.md`: what is ready, what is missing (the APK, the
  MediaProjection capture, the measurements on a real board), the
  dependencies of an APK (without SciPy and OpenCV), the three deployment
  ways and the checklist of the packaging cycle.
- Tests: `tests/unit/test_user_settings.py` (16) and
  `tests/integration/test_settings_screen.py` (7).

### Acceptance criteria (all verified)
- **No APK and no Buildozer** were built - that was the decision of this
  cycle (ADR-001); the document says so honestly.
- The renderer works with both backends (the test renders a figure with the
  PNG fallback and checks the texture).
- The settings survive a restart (the file is written, read back and applied
  to the environment) and the whiteboard follows them.
- `pytest`: **505 tests + 2 skipped (the live tests), all green**;
  `ruff check .` and `black --check .` are clean.

### Left / blockers
- **BLOCKER (human):** no Android device or emulator in the sandbox - the
  FPS / latency numbers of the plan could not be measured on real hardware.
- **BLOCKER (human):** the packaging cycle (the APK, the signing key, the
  distribution) was not part of this cycle.
- The screen capture of the board (`AndroidProjectionSource`) is still a
  stub - the whiteboard capture and the photo import work.
- The 3D view still needs the Kivy Agg canvas (the rotation gesture); it has
  no PNG fallback.

---

## Phase 12 - QA, performance, docs and demo

**Status:** DONE (the last phase of v1 - the tag `v1.0.0` points at it)

### Done

**1. The test matrix**
- A unit test per module and an integration test per feature (1.a - 1.f, the
  documents, the settings, the error handler).
- The coverage of `aieva/core` + `aieva/plugins` is **83 %** (the target of
  the plan was 75 %; the UI is not measured).
- New in this phase: `tests/unit/test_robustness.py` (11),
  `tests/integration/test_error_handler.py` (6),
  `tests/unit/test_template_plugin.py` (9) and a throttle test in
  `tests/integration/test_plot_modal.py`.

**2. The robustness pass**
- `aieva/ui/error_handler.py`: a **global error handler** that catches every
  exception, writes the traceback into `aieva.log` (the working directory)
  and shows a short toast to the user. It is installed in
  `aieva/ui/app.py::build()` and hooks both `sys.excepthook` and the Kivy
  `ExceptionManager`.
- The empty input, a huge exponent (`x**999999999` - it used to kill the
  process with an out-of-memory, now `MAX_EXPONENT = 1000` in
  `core/safe_parse.py` refuses it in 0.0 s), a division by zero (`1/0` now
  raises a `SolveError` instead of returning `zoo`), an undefined region, a
  server that does not answer, a wrong key and a slider that is dragged too
  fast are all covered by tests - **no unhandled exception reaches the user**.

**3. The performance pass**
- **The render cache**: `core/cache.py` got `RENDER_NAMESPACE`, `render_key()`
  and `cached_render()`; the plot canvas stores the rendered PNG in the
  on-disk cache, so the same figure is not rendered twice.
- The **default 3D quality is now `low`** (a 30x30 mesh) - it keeps a board
  smooth; the user can raise it in the Settings screen.
- The **slider throttle** (30 Hz) is tested: 20 fast moves cause at most two
  re-renders.
- **The timings are logged**: `core/timing.py` (`timed()`, `elapsed_ms()`) is
  used by the OCR pipeline and by the parameter update of the equation
  engine.

**4. The documentation**
- `README.md`: install, `.env`, run the server, run the app, test, the
  feature map, the Android notes, the troubleshooting table.
- `docs/DEMO_SCRIPT.md`: the eight demos **A - H** with the exact steps, the
  expected results and a troubleshooting table.
- `docs/ADDING_A_SUBJECT.md`: how to add Biology / Chemistry / Physics.

**5. The future-ready check**
- `aieva/plugins/_template_plugin/` is a documented stub plugin (no Kivy, no
  core change) and `docs/ADDING_A_SUBJECT.md` explains how a new subject is
  plugged in - the architecture is proven, not only promised.

**6. A real bug that the test matrix found**
- `get_settings()` was an `lru_cache`; the `reload=True` flag was read
  *inside* the cached function, so a second call returned the **old** value.
  The settings are now cached in a plain dictionary and `reload=True` clears
  the cache *before* the lookup. This was the cause of three failures that
  only appeared in the full run.

### Acceptance criteria (all verified)
- `pytest`: **532 tests + 2 skipped (the live tests), all green**;
  `ruff check .` and `black --check .` are clean.
- The coverage of `aieva/core` + `aieva/plugins` is **83 %** (>= 75 %).
- Every input of the robustness list ends in a domain error, a toast or a
  clean fallback - never in a crash.
- The eight demos A - H are described step by step in
  `docs/DEMO_SCRIPT.md`.
- The template plugin is present and its test proves that a new subject does
  not touch the core.
- The tag `v1.0.0` points at this commit.

### Left / blockers
- **BLOCKER (human):** no APK is built in this cycle (ADR-001) - the desktop
  build is the supported target; the packaging checklist is in
  `docs/ANDROID_READINESS.md`.
- **BLOCKER (human):** there is no Gemini key in the sandbox, so the cloud
  was tested with the mock mode (`AIEVA_MOCK_LLM=true`); the live call needs
  a key and the steps are in `docs/MANUAL_STEPS_NEEDED.md`.
- **BLOCKER (human):** no Android device or emulator - the FPS / latency of
  the plan could not be measured on real hardware.
- The screen capture of the board (`AndroidProjectionSource`) is still a stub
  - the whiteboard capture and the photo import work.
- The 3D view needs the Kivy Agg canvas (the rotation gesture); it has no
  PNG fallback yet.

---

## Post-release cleanup (after `v1.0.0`)

The repository was made ready for GitHub: only the product is in it.

### Removed (dead weight, no functionality)
- Five **empty placeholder modules** that were never imported:
  `server/routers/solve_explain.py`, `aieva/core/ocr/base.py`,
  `aieva/core/ocr/gemini_ocr.py`, `aieva/core/ocr/manual_ocr.py` and
  `aieva/core/ocr/pix2text_ocr.py` (the real OCR engines live in
  `aieva/core/ocr/engines.py`).
- `PlaceholderScreen` - an unused *"coming soon"* screen in
  `aieva/ui/screens/whiteboard.py`.
- `tests/fixtures/images/` - an empty package with no image in it.
- The `preview/` folder (the local screenshots) is no longer tracked; it is
  generated by `scripts/make_preview.py` and ignored by git. Three screenshots
  that the README uses are kept in `docs/screenshots/`.

### Added
- A **professional `README.md`**: the badges are replaced by a feature table,
  the architecture diagram, the quick start, the configuration table, the test
  results, the project layout and the index of the documents.
- `LICENSE` (MIT) and a complete `.gitignore` (the caches, the secrets, the
  runtime folders, the build artefacts and the local preview).

### Verified
- `pytest`: **532 passed, 2 skipped**; `ruff check .` and `black --check .`
  are clean.

---

## Phase 13 - The background service of the board (instructor request)

**Status:** DONE (the service runs on its own; the cloud OCR still needs a key)

The instructor asked for an **application that works in the background of the
smart board** - fully automatic, without any hassle. The application itself
was already there; what was missing was the part that works *while nobody
touches the computer*.

### Done
- **New package `aieva/core/service/`** (pure Python, no Kivy - the core
  stays headless):
  - `config.py` - `ServiceConfig` (the source, the interval, the folders, the
    thresholds) read from the environment (`AIEVA_SERVICE_*`).
  - `state.py` - the status file (`ServiceState`, an atomic write).
  - `triggers.py` - `TriggerPolicy`: the board is only read again when it
    really changed (thumbnail comparison + a minimum pause + a limit per
    minute).
  - `sources.py` - `FolderSource` (the newest picture of a folder) and the
    choice of the source (`desktop` / `folder` / `auto`).
  - `runner.py` - `BackgroundService`: capture → change check → OCR → solve →
    draw → publish (the outbox, the history, the status file, the file of the
    floating window). It runs in a thread and survives every error.
  - `autostart.py` - the automatic start: a task of the Windows task scheduler
    (`ONLOGON` / `ONSTART`, started with `pythonw.exe`, so no console window),
    a systemd unit (Linux / Termux) and a launch agent (macOS).
  - `overlay.py` - the pure data of the floating window (no Kivy).
  - `__main__.py` - the command line: `run`, `once`, `status`,
    `install-autostart`, `uninstall-autostart`, `overlay`.
- **`python -m aieva`** starts the service (one command for the board).
- **`aieva/ui/board_overlay.py`** - the floating window above the board: it
  shows what was read, the solution and the graph, and disappears again after
  a few seconds. It is a separate process and only reads the result file.
- **The window of the teacher** and the service are one system:
  - the **Settings** tab got a *Background service* block (a switch, the live
    status, *Start*, *Stop*, *Start with the computer*);
  - the application starts the service with it and stops it when it closes;
  - `UserSettings.background_service` remembers the choice.
- **The scripts**: `scripts/start_service.ps1`, `scripts/stop_service.ps1`,
  `scripts/install_autostart.ps1`, `scripts/run_service.sh`.
- **The documentation**: `docs/BACKGROUND_SERVICE.md` (what it does, how to
  start it with the computer, the files it writes, the settings, the
  troubleshooting).
- **`requirements.txt`** now also names the document readers
  (`python-docx`, `python-pptx`, `pymupdf`) - the Phase 10 features need them.
- **42 new tests** (`tests/unit/test_service_*.py`).

### Verified
- `pytest`: **575 passed, 2 skipped**; `ruff check .` and `black --check .`
  are clean.
- A live run: the service read a picture of the board, solved it, drew the
  graph (`x² + y² = 9`), wrote the result into the outbox and stopped cleanly
  on `SIGTERM`.

### Left / blockers
- **BLOCKER (human):** without a Gemini key the OCR of a real board needs the
  fog server (`python -m aieva.core.service run` with
  `AIEVA_SERVER_URL`); the mock engine was used for the verification.
- **BLOCKER (human):** the capture of a real Android board still needs the
  MediaProjection (the stub of Phase 11); the desktop screen and the folder
  source work today.
- The floating window was verified on the desktop; on a board it needs a
  window manager that allows an always-on-top window.
