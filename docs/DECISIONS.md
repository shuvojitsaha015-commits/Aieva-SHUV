# Architecture Decision Record

Short, permanent record of the decisions that shape the product. New decisions
are appended at the bottom.

---

## ADR-001 - No APK is built in this project cycle

**Status:** accepted (team decision, 2026-10-31)

**Context.** Aieva runs on Android smart boards, but building an APK with
Buildozer (numpy + matplotlib + sympy on python-for-android) is the single
biggest schedule risk of the project and the team does not want to spend the
time on it now.

**Decision.**

* We **do not** build an APK. The deliverable of this cycle is the source
  application plus the fog/cloud server.
* The application stays **Android ready** instead of Android packaged:
  * Kivy is the UI framework (the same code runs on a board);
  * the core has **no hard dependency on SciPy or OpenCV** (Phase 11 replaces
    them with an internal adaptive quadrature and a Pillow/NumPy pre-processing
    path), so the dependency set stays small enough for a later packaging step;
  * heavy work (OCR, LLM) runs on the server, so no on-device ML runtime is
    needed;
  * the smart-board specific work (DPI scaling, palm rejection, quality
    settings, a settings screen) is still done - it is needed for the board
    regardless of how the app is deployed.
* Packaging instructions (Buildozer / Docker) are documented in the README but
  the build itself is left to a later cycle.

**Consequences.** The fallback described in the implementation plan ("ship the
desktop build") is the official outcome of Phase 11.

---

## ADR-002 - The architecture is multi-subject from day one

**Status:** accepted (team decision, 2026-10-31)

**Context.** The vision spans Mathematics, Biology, Chemistry, Physics and
Voice. Rewriting the core every time a subject is added would be expensive,
and the master handoff document asks for "configuration driven" plugins.

**Decision.** Everything that a future subject touches is written subject
agnostic *now*, even though only mathematics is implemented:

| Concern | Decision |
|---|---|
| Plugin contract | `SubjectPlugin` (parse / solve / visualize / create_session) plus a `PluginMeta` describing name, description, optional dependencies, capabilities and UI hints. |
| UI | The subject list is generated from the registry metadata - no subject is hard-coded in a screen. |
| Dynamic parameters | The UI drives a `VisualizationSession` **protocol**, not a maths class, so Biology/Chemistry can expose their own sliders. |
| Shared services | OCR, document parsing, LLM access and the cache live in `core/` and know nothing about mathematics. |
| Server | Routes are `/api/{subject}/{capability}`; the client sends the subject name. |
| Voice | A future voice layer only has to turn speech into an intent and call the same plugin interface - no change to the core. |

**Consequences.** Adding a subject is one new package under `aieva/plugins/`
plus (optionally) new routes on the server. `docs/ADDING_A_SUBJECT.md`
(Phase 12) documents the procedure and `aieva/plugins/_template_plugin/` is
the executable template.

---

## ADR-003 - Matplotlib is the single rendering engine

**Status:** accepted

**Context.** The proposal mentions Plotly for the slider UX and the master
document mentions an optional WebView.

**Decision.** Matplotlib renders every figure (2D and 3D) and the sliders are
**native Kivy widgets**. One engine means one output contract
(`VisualizationResult`), no WebView, no JavaScript bridge and no second
rendering path to maintain on a slow board.

**Consequences.** The slider UX is functional rather than Desmos-like; that
trade-off is accepted in the gap analysis.
