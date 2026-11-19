# Aieva on the Android smart board - readiness

> **Scope of this document.** Aieva v1 is **not** packaged as an APK in this
> cycle (see [ADR-001](DECISIONS.md)). The **desktop build is the supported
> target**; the code is written so that the same sources run on an Android
> board. This document says honestly what is ready, what is not, and what the
> packaging cycle has to do.
>
> **The classroom only has smart boards.** The question is therefore not
> "does it run on a laptop" but "does the always-on application work on the
> board". The answer has two parts:
>
> 1. **Aieva IS the board.** The teacher writes on Aieva's own canvas, so
>    Aieva knows what is written - **no screen capture, no permission, no
>    Android specific code**. This path is implemented and tested
>    (`aieva/core/service/canvas.py`).
> 2. **Reading other applications** (a PDF that is open on the board) needs
>    the MediaProjection. The Python side and the Java helper are written
>    (`aieva/core/ocr/android_bridge.py`, `aieva/android/java/`), but they
>    have **not** been run on a physical board yet.

---

## 1. What "ready" means here

| Question | Answer |
|---|---|
| Does the UI run on Android? | The UI is **native Kivy** - no WebView, no browser, no JavaScript runtime. The same Python sources run. |
| Do the maths libraries build for Android? | `sympy`, `mpmath`, `numpy`, `pillow` and `matplotlib` are pure Python / wheels with an Android port. **SciPy and OpenCV are not needed** (see §4). |
| Where does the heavy work happen? | On the **fog server** (OCR, the LLM, the word problems). The board only draws and touches. |
| Is there an APK? | **Not yet.** The recipe (`buildozer.spec`) is written, but there is no Android SDK in the build environment and no signed artifact. This is a deliberate decision of this cycle, not an oversight. |

---

## 2. What is already implemented

### 2.1 The screen (DPI and touch)

* Every size is **density independent** (`kivy.metrics.dp` / `sp`) - the
  layout is identical on a phone, on a 1080p board and on a 4K interactive
  panel. See `aieva/ui/theme.py`.
* Every touch target is at least **56 dp** tall (`theme.MIN_TOUCH_DP`); the
  buttons, the sliders and the file list all use it.
* The high contrast palette (`theme.py`) was chosen for a bright classroom
  board.
* Multi touch is enabled for the pinch zoom (`Config` in `aieva/ui/app.py`),
  the whiteboard rejects a **palm** that rests on the board (a contact that
  is bigger than `palm_threshold` pixels is ignored - see
  `aieva/ui/widgets/whiteboard.py`).

### 2.2 The renderer (the `PlotCanvas` abstraction)

`aieva/ui/widgets/plot_canvas.py` hides the difference between the two ways
a Matplotlib figure can be shown:

| Backend | When | How |
|---|---|---|
| `kivyagg` | the desktop (and every board where `kivy_garden.matplotlib` works) | the figure is drawn into a real Kivy canvas |
| `png` | a board without the Kivy Matplotlib backend | the figure is rendered to a **PNG texture** and shown in an image widget |

The application always uses `PlotCanvas`, so **no screen has to be changed**
when the backend differs. The sliders redraw the PNG on every throttled
update (30 Hz), which is fast enough for a board.

> The 3D view (`aieva/ui/widgets/plot3d_view.py`) is the one exception: it
> subclasses the Kivy Agg canvas because it needs the touch handling of a
> live canvas. On a board without that backend it falls back to the PNG
> picture without the rotation gesture.

### 2.3 The performance tiers

The quality is a setting of the user (`Settings screen` ->
`aieva/core/user_settings.py`) and maps to the mesh of the renderer:

| Quality (user) | Mesh of the 3D renderer | Points of the 2D curve | Typical use |
|---|---|---|---|
| `low` | 30 x 30 | 400 | a slow board, a big class |
| `normal` (default) | 60 x 60 | 400 | the usual case |
| `high` | 120 x 120 | 400 | a small class, a close-up |

While a finger drags the 3D picture the renderer drops to `low` and the
update rate is throttled to 30 Hz; when the finger lifts, the quality comes
back (`aieva/ui/widgets/plot3d_view.py`).

### 2.4 The background work

Nothing heavy runs on the UI thread:

* the OCR runs in the **background worker** (`aieva/core/ocr/worker.py`),
  either in the app or in the separate worker process
  (`python -m aieva.core.ocr.worker`),
* the LLM and the symbolic work run in worker threads
  (`aieva/ui/workers.py`),
* the document reading and the picture OCR run in worker threads too.

A board with a slow CPU therefore stays responsive while the server thinks.

### 2.5 The settings a teacher needs

The **Settings** screen (home -> Settings) holds the server URL, the quality,
the offline mode, the thickness of the pen and the palm rejection. They are
stored in `<cache>/user_settings.json` and are applied to the environment, so
they survive a restart.

---

## 3. What is missing for a real device

| Item | State | Note |
|---|---|---|
| The APK itself | **missing** | no Android SDK, no signing key and no decision about the distribution in this cycle |
| `buildozer.spec` | **written** | the recipe is in the root of the repository; the artifact is built in the packaging cycle |
| `Dockerfile.buildozer` | **missing on purpose** | same as above |
| The screen capture of the board | **written, not tested on a device** | `AndroidProjectionSource` talks to a `MediaProjectionBridge` (tested with a fake); the Java helper (`aieva/android/java/AievaProjection.java`) asks for the permission and reads the frames. It still has to run on a real board. |
| The canvas of Aieva as the picture of the board | **done** | `aieva/core/service/canvas.py` - the app publishes its canvas, the service reads it. No capture, no permission - this is the path that works on an Android board today. |
| The APK | **recipe written** | `buildozer.spec` exists (with the Java helper, the permissions and the landscape orientation) - the artifact itself is not built. |
| The automatic start on the board | **done for Termux** | `scripts/install_termux_autostart.sh` writes the systemd unit of the user, `scripts/termux_boot.sh` is the boot script for the boards without systemd. |
| The measurements on a board | **missing** | no FPS / latency numbers from real hardware - the timings of this repository come from a desktop |
| The `kivy_garden.matplotlib` on Android | **not verified** | the PNG fallback exists for exactly this case, but it was never run on a device |

---

## 4. The dependencies of an APK

```
python3, kivy, numpy, matplotlib, pillow, sympy, mpmath, requests, pyjnius, android
```

**Not** in the APK: `scipy` and `opencv-python`.

* `scipy.integrate.quad` was replaced by an **internal Gauss-Kronrod**
  integrator (`aieva/core/numeric.py`, error ~1e-12) - SciPy is optional.
* The OpenCV pre-processing was replaced by a **Pillow/NumPy**
  implementation (grayscale, autocontrast, adaptive threshold, deskew) -
  `aieva/core/ocr/preprocess.py`.

Permissions: `INTERNET` (the fog server), `READ_EXTERNAL_STORAGE` /
`WRITE_EXTERNAL_STORAGE` (the documents, depending on the target API level).
Orientation: landscape, fullscreen.

---

## 5. How to deploy on the board

Three ways, in the order of the effort:

1. **The desktop build on a mini-PC** (the supported target today)
   - the board is a touch screen, the mini-PC is behind it;
   - the server runs on the mini-PC (or on a small server in the network);
   - `python -m aieva.ui.app` + `uvicorn server.main:app`.
2. **A Python runtime on the board** (Termux + a Kivy build)
   - the same sources, the same server;
   - the touch targets and the DPI scaling already fit the board;
   - `scripts/install_termux_autostart.sh` starts the service with the board
     (systemd unit of the user) - after that nothing has to be typed.
3. **An APK** (a later packaging cycle)
   - write `buildozer.spec` with the dependencies of §4,
   - build it in a container (so every teammate gets the same artifact),
   - test the demos A - H of `docs/DEMO_SCRIPT.md` on the device and write
     the FPS numbers into `docs/PROGRESS.md`.

---

## 6. The checklist of the packaging cycle

- [x] `buildozer.spec` with the requirements of §4, the permissions and the
      landscape orientation.
- [ ] `Dockerfile.buildozer` + `scripts/build_apk.sh` (a reproducible build).
- [ ] Verify that `kivy_garden.matplotlib` works on the device - otherwise
      the `png` backend of `PlotCanvas` is used automatically.
- [x] The MediaProjection capture in Python (`AndroidProjectionSource` +
      the bridge) - **the Java helper still has to prove itself on a board**.
- [ ] The demos A - H on the device, with the FPS / latency in
      `docs/PROGRESS.md`.
- [ ] The tag `v1.0.0` (see [ADR-003](DECISIONS.md) for the versioning).
