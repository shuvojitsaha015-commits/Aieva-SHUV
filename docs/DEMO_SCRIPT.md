# Aieva - Demo Script

The exact steps for the eight demo scenarios. Each scenario lists what to do,
what should happen and how to verify it.

**Before the demo**

```bash
cd aieva
source .venv/bin/activate          # Windows: .venv\Scripts\activate
cp .env.example .env               # add GEMINI_API_KEY if you have one
./scripts/run_server.sh            # terminal 1 - the fog server (mock mode is fine)
./scripts/run_app.sh               # terminal 2 - the Kivy application
```

Without a Gemini key the server runs in **mock mode** (`AIEVA_MOCK_LLM=true`):
it answers with canned but valid responses, so every scenario below still works.

**The settings** (Home -> Settings): the URL of the server, the quality of the
renderer, the offline mode, the thickness of the pen and the palm rejection.
They are saved in `<cache>/user_settings.json` and are used at the next start.

---

## A. Type an equation and move the sliders (feature 1.a)

1. Start the app -> the **Home** screen appears.
2. Click **Type Equation**.
3. Type `y = mx + c` in the input bar (the *Text* mode is selected by default).
4. Press **Plot**.
5. A popup opens with the straight line and **two sliders**: `m` and `c`.
6. Drag the `m` slider from `1` to `3`: the line rotates around the y-axis.
7. Drag the `c` slider: the line moves up and down.
8. Press **Reset params** to go back to the defaults.
9. Press **Copy equation (LaTeX)** - the LaTeX of the equation is on the clipboard.
10. Close the popup. Type `x^2+y^2=r^2` and press **Plot**.
11. A circle appears with a single slider `r` (default `5`, range `0.1 .. 20`).
    Dragging `r` resizes the circle.

**Verify:** the line and the circle follow the sliders smoothly, the title shows
the LaTeX, the corner label shows the live parameter values.

---

## B. Write an equation on the whiteboard and plot it (feature 1.a)

1. Go back to **Home** and click **Whiteboard**.
2. Draw `x^2 + y^2 = r^2` with the pen (pick a colour with the buttons).
3. Click **Solve board** - the OCR pipeline runs (Phase 8).
   * With a Gemini key the equation is recognised.
   * Without a key (or when the recognition fails) the app opens an editable
     box pre-filled with the best guess - correct it and confirm.
4. The recognised equation is plotted with the `r` slider.
5. Use **Clear** / **Undo** to tidy the board.

---

## C. Calculus: integral, Riemann sums, tangent animation (feature 1.b)

1. Home -> **Type Equation** -> switch to **LaTeX** -> type
   `\int_{0}^{\pi} \sin(x) dx` -> **Solve**.
   The exact value `2` is shown, together with a shaded area.
2. Switch the mode to **Calculus** and choose **Riemann sums**.
   * Move the `n` slider from 1 to 200 and watch the rectangles converge.
   * Compare the methods *left*, *right*, *midpoint* and *trapezoid*.
3. Choose **Tangent line** and press **Play**.
   The tangent line slides along the curve; the slope text updates.
4. Choose **Area between curves** for `y = x` and `y = x^2` on `[0, 1]`
   (the exact area `1/6` is shown).

---

## D. Matrix transformation, eigen values and complex numbers (feature 1.c)

1. Home -> **Linear Algebra**.
2. Mode **Matrix**: enter the matrix `0, -1 / 1, 0` (a 90 degree rotation) in
   the 2x2 grid. The grid and the unit square are warped; the determinant `1`
   is annotated. The *rotation* and *shear* sliders add a transformation on
   top of the matrix.
3. Mode **Eigen**: the same matrix shows the (complex) eigen values `i` and
   `-i` and the message "there is no real eigen vector to draw".
4. Enter `2, 0 / 0, 3`: the eigen values `2` and `3` appear with their
   eigenvectors drawn as arrows.
5. Mode **System**: enter `2x + y = 5; x - y = 1` - the intersection point
   `(2, 1)` is highlighted. Try `x+y=1; 2x+2y=5` for the parallel lines.
6. Mode **Complex**: enter the complex number `3 + 4i`: the Argand diagram
   shows the point, the modulus `5` and the argument. Operation **x i** shows
   the 90 degree rotation, **roots** with `n = 3` shows the three cube roots
   of `1` on the unit circle.

---

## E. A 3D surface with rotate and zoom (feature 1.d)

1. Home -> **3D Plots** -> type `z = x**2 + y**2` -> **Draw**.
   The surface is rendered in 3D.
2. Drag with one finger (or the mouse) inside the plot: the surface rotates.
3. Pinch (or use the **zoom +/-+ buttons**) to zoom in and out.
4. Use **Rotate <-/->/^/v** and **Reset view** for a deterministic demo.
5. The quality spinner (`low` / `medium` / `high`) changes the mesh of the
   surface - `low` (30x30) is the default, because it is fast on a weak
   board. The same value can be set for the whole application in
   **Home -> Settings**.

---

## F. Solve a problem from a screen region (feature 1.e)

1. Home -> **Solve from Screen**.
2. The screen becomes a semi transparent overlay: drag a rectangle around the
   problem.
3. Confirm with **OK** (or press **Cancel**).
4. The crop is sent to the OCR engine. Correct the LaTeX in the editable box
   if the recognition is not perfect.
5. The step-by-step solution appears in the scrollable panel, with the SymPy
   answer verified. If the LLM answer differed, a warning is shown.
6. Press **Visualize** to open the matching plot modal.

---

## G. A projectile word problem (feature 1.f)

1. Home -> **Word Problem**.
2. Example: *"A ball is thrown with 20 m/s at 45 degrees. How high does it fly
   and how far?"* (the three **example** buttons fill the field for you).
3. Press **Analyse**: the server turns the text into a structured model.
   * With a Gemini key the model comes from the model.
   * Without a server (or without a key) the **local model** is used - the
     keywords pick the template and the numbers in the text become the
     variables.
4. The **"How I understood the problem"** card lists the variables (with an
   editable value), the equations, the unknowns and the assumptions - correct
   a value if needed and press **Confirm and solve**.
5. The solution (the steps and the numbers) appears on the right, the
   trajectory is drawn as a parabola with the velocity vectors, the apex and
   the range marked.
6. Use the sliders (`v0`, `theta`) to change the initial conditions - the
   answer and the picture follow.
7. Press **Animate**: the ball flies along the trajectory (a Kivy clock
   animation, no VPython).

---

## H. Load a document and plot an equation (Phase 10)

1. Home -> **Documents**.
2. Pick a `.pdf`, `.pptx` or `.docx` file in the file list and press
   **Read the document**. The page limit (`5`, `10`, `20`, `all`) keeps a big
   document responsive - the reading happens in a worker thread.
3. The list on the right shows every equation that was found:
   * a **formula in OMML** (Word / PowerPoint) becomes LaTeX at once,
   * a **formula as text** (a PDF) is shown as it is,
   * a **picture** is read by the OCR pipeline in the background - the status
     line says when it is done.
4. Tap an equation -> **Solve it** (the solver screen with the steps) or
   **Plot it** (the plot modal).
5. An old `.doc` or `.ppt` gets a clear message: *"please save the file as
   .docx (or as a PDF)"*.

---

## Troubleshooting during the demo

| Problem | Fix |
|---|---|
| The app does not start on a headless machine | `xvfb-run -a ./scripts/run_app.sh` |
| "Could not read that equation" | switch to *LaTeX* mode and check the syntax |
| The server is not reachable | start `./scripts/run_server.sh`, check `AIEVA_SERVER_URL` |
| OCR says "needs manual input" | expected fallback - edit the pre-filled LaTeX |
| The word problem stays empty | the server is not reachable - the local model is used automatically |
| The 3D view is slow | **Home -> Settings -> Quality: low** (the mesh is 30x30) |
| An error appears as a toast | the details are in `aieva.log` (the folder of the application) |
