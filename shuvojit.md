# Aieva — the smart board assistant (Windows)

**Aieva** reads what the teacher writes on the board, solves it, explains it
and draws it — without the teacher leaving the board.

It is a **Windows desktop application** that runs in the background of the
smart board: it starts with the computer, lives in the system tray, and a
small control on the left edge of the screen is all the teacher needs.

> The short front page of the project is [`README.md`](README.md); the
> two-page submission document is
> [`docs/Aieva_Project_Documentation.pdf`](docs/Aieva_Project_Documentation.pdf).

---

## 1. The libraries and the technologies

### The board (what is on the screen)

| Library | Version | Why it is there |
|---|---|---|
| **Kivy** | ≥ 2.3 | The whole interface. It is touch-first and works with a smart board (big targets, no mouse needed). One code base for the board, the control and the window of the teacher. |
| **kivy-garden.matplotlib** | (with Kivy) | Draws the Matplotlib figures **inside** a Kivy window. Without it the graphs would have to be shown as a picture. |
| **pystray** | latest | The icon of Aieva in the **system tray** of Windows. It is imported lazily, so the rest of Aieva still works on a machine without it. |
| **Pillow** | latest | The pictures of the board: the capture of the screen, the pre-processing, the icon of the tray. |
| **numpy** | latest | The numbers of the graphs (the grids, the surfaces, the integrals). |
| **pillow + numpy** | latest | The pre-processing of the picture before it is read (the deskew, the noise, the threshold) - **without OpenCV**, so the app also runs on a weak board computer. |
| **requests / httpx** | latest | The talk with the fog server. |

### The maths (what the answer is)

| Library | Version | Why it is there |
|---|---|---|
| **SymPy** | ≥ 1.12 | The maths itself: the solving, the simplifying, the derivatives, the integrals, the limits, the systems, the exact answers. **The answer of Aieva is always computed by SymPy — the language model never computes anything.** |
| **antlr4-python3-runtime** | **4.11.\*** | The parser of SymPy for LaTeX. The version is pinned: 4.7 breaks `sympy.parsing.latex`. |
| **mpmath** | latest | The exact arithmetic of SymPy. |
| **SciPy** | latest | The numerical helpers (the integration, the optimisation). |
| **Matplotlib** | latest | The drawing of the graphs, the surfaces and the charts. |
| **latex2sympy2** | latest | The second way to read LaTeX (when the SymPy parser refuses it). It is in `requirements-optional.txt` — Aieva works without it. |

### The cloud (the fog server)

| Library | Version | Why it is there |
|---|---|---|
| **FastAPI** | latest | The small server that stands in front of Gemini. It is the only place the API key lives — the board itself never sees it. |
| **uvicorn** | latest | The server that runs FastAPI. |
| **google-genai** | latest | The talk with **Gemini** (the OCR of the board, the explanation). |
| **python-multipart** | latest | The upload of the picture (`POST /api/math/ocr`). |
| **pydantic** | latest | The answers of the server are checked before they go out. |

### The documents (the extra screens)

`python-docx`, `python-pptx` and `pymupdf` read Word, PowerPoint and PDF
files, so the teacher can drop a file into Aieva and get its equations.

### The tools of the development

`pytest`, `pytest-cov`, `pytest-mock` and `respx` for the tests, **ruff** and
**black** for the code. They are in `requirements-dev.txt`.

### The technologies around it

* **Windows Task Scheduler** — the service starts with the computer.
* **The startup folder of the user** — the way out when there are no
  administrator rights.
* **The system tray** (`pystray` on Windows) — the icon of Aieva.
* **A file as the channel** — the control and the service are two programs;
  they talk through two small files (the request and the result). No port, no
  socket, nothing that can block.
* **The Gemini API** — the board is read with the *Gemini* model. **Aieva
  needs the network and the key. There is no offline version.**

---

## 2. The installation

### 2.1 What the computer needs

* **Windows 10 or 11** (the board PC).
* **Python 3.11 or newer** — <https://www.python.org/downloads/windows/>.
  During the installation **“Add python.exe to PATH”** must be ticked.
* **The fog server** with a **Gemini API key** — either on the board PC
  itself or on a server in the school network.
* The **network**: the board is read through the cloud.

### 2.2 The one command setup

Open **PowerShell** in the project folder and run:

```powershell
.\scripts\setup.ps1
```

It creates the virtual environment, installs everything and writes the `.env`
file.

### 2.3 The Gemini key

Put the key into `.env`:

```ini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.8-flash
AIEVA_SERVER_URL=http://127.0.0.1:8000
```

`AIEVA_SERVER_URL` is where the fog server lives. When the server runs on the
board PC itself, `http://127.0.0.1:8000` is right.

#### Two keys or more (the quota of one key is small)

A single Gemini key has a small quota — a busy class can use it up. Put
**several** keys in the `.env` and Aieva uses them one after the other:

```ini
GEMINI_API_KEY=first-key-here
GEMINI_API_KEYS=second-key-here,third-key-here
```

* the keys are separated by a comma (a semicolon works too),
* the key of `GEMINI_API_KEY` stays the **first** one of the list,
* the same key twice is only used once,
* when a key fails (its quota is gone, it is refused) the **next key is
  tried at once** — without any waiting and without any error on the
  screen,
* when every key fails, the whole list is tried again with a slow backoff.

The fallback stays **inside Gemini** on purpose: the OCR of the board needs a
model that reads a picture, and both answers must have the same shape. A
second company would only be a second thing that can go wrong. The doctor
says how many keys it found (`python -m aieva.core.doctor`).

### 2.4 The fog server

```powershell
.\scripts\run_server.ps1
```

It reads `GEMINI_API_KEY` and `GEMINI_API_KEYS` from the `.env`. The server
must be running before the board is read — start it at the boot (a second
task of the task scheduler) or leave it running in a window.

### 2.5 The automatic start

```powershell
.\scripts\install_autostart.ps1
```

It registers a task of the **task scheduler**:

1. **ONSTART** — the service starts when the computer **boots**. This needs
   administrator rights (run PowerShell as administrator).
2. Without administrator rights the task falls back to **ONLOGON** — the
   service starts when the teacher logs in.
3. When the task scheduler refuses both, a file in the **startup folder** of
   the user does the job.

The script says which one was used. To force the variant without
administrator rights: `.\scripts\install_autostart.ps1 -OnLogon`.

### 2.6 The check

```powershell
.\.venv\Scripts\python.exe -m aieva.core.doctor
```

It checks the Python, the packages, the `.env`, the fog server, the OCR
(Gemini), the capture of the board, the automatic start and the service — and
says exactly what to do when something is missing.

### 2.7 The commands of Aieva

| Command | What it does |
|---|---|
| `python -m aieva.core.service run` | watch the board in the background |
| `python -m aieva.core.service run --overlay --tray` | the same, with the floating control and the icon of the tray |
| `python -m aieva.core.service once` | one reading (a quick check) |
| `python -m aieva.core.service status` | what the service is doing right now |
| `python -m aieva.core.service scan` | read the board once, right now |
| `python -m aieva.core.service install-autostart` | start with the computer |
| `python -m aieva.core.service uninstall-autostart` | stop starting with the computer |
| `python -m aieva.core.service overlay` | the floating control on its own |
| `python -m aieva.core.service tray` | the icon of the tray on its own |
| `python -m aieva.ui.app` | the full application of the teacher |
| `python -m aieva.core.doctor` | is this computer ready for the board? |

The PowerShell wrappers of the school are in `scripts/`:
`setup.ps1`, `run_server.ps1`, `start_service.ps1`, `stop_service.ps1`,
`run_app.ps1` and `install_autostart.ps1`.

---

## 3. The workflow of a lesson

### 3.1 The morning

The board PC is switched on. The task of the task scheduler starts the
**service** — it watches the board, without a window. With it come the
**icon in the system tray** and the **control on the left edge**. The teacher
does not do anything.

The control is a slim pill in the middle of the left edge. It never covers
the writing.

### 3.2 The teacher writes something

Two ways to read the board:

| How | What happens |
|---|---|
| **Scan** (the button of the control) | the board is read at once — the part the teacher picked last, or the whole board |
| **Drag** (the button of the control) | a picture of the board opens; the teacher drags a rectangle over the writing; that part is read. The area is remembered, so the next **Scan** reads the same part again |
| **F8** (`Ctrl+Alt+A`) | the board is read without touching the screen at all |

### 3.3 What happens behind the scenes

1. **The picture is captured** (the screen of the board).
2. **Gemini reads it** through the fog server. It answers with the
   expression (LaTeX and a SymPy string), a confidence note, **what has to be
   done** (`solve`, `graph`, `both` or `none`) and — when the board shows a
   table — the values of the table.
3. **SymPy checks the reading.** A reading that cannot be parsed is reported
   as uncertain instead of being used.
4. **The maths pipeline runs** — the solver of SymPy works out the answer and
   the steps of the solution.
5. **The graph is drawn** — the 2D curve, the implicit curve, the 3D surface
   or the chart of the table.
6. **The result is published** into a small file.

### 3.4 What the teacher sees

A popup opens **next to the problem**:

* the **reading** (what Gemini understood),
* the **answer**,
* the **explanation** — the steps of the solution,
* the **picture** — the graph or the chart.

After a few seconds the popup closes and the control is all that is left.
The key **F8** and the button **Scan** read the same part of the board again.

### 3.5 The full application

The full window of the teacher is opened from the **icon in the system tray**
(*Open Aieva*). It has the screens for the solver, the calculus, the
algebra, the 3D plots, the word problems and the documents — and it is a
*separate* program: the board keeps watching while the teacher works in it.

The icon in the tray also has:

| Entry | What it does |
|---|---|
| **Open Aieva** | starts the full application |
| **Scan the board** | asks the service to read the board right now |
| **Stop the service** / **Start the service** | pauses and resumes the watching |
| **Quit** | stops everything |

### 3.6 The board as the canvas

Aieva can also *be* the board: with `AIEVA_BOARD_MODE=1` the canvas of
Aieva fills the screen, the navigation bar disappears and the screen never
goes to sleep. The writing is published to the service directly — **no screen
capture and no permissions are needed**.

---

## 4. The files of the project

```
aieva/
  core/            the heart - it knows nothing about the screen
    charts.py        the chart renderer (every subject can use it)
    ocr/             the capture of the board, the engines, the pipeline
    service/         the background service, the control, the tray, the autostart
    llm/             the client of the fog server and the prompts
    safe_parse.py    the safe reading of a mathematical text
  plugins/
    math/            the maths of the subject (the solver, the graphs, the templates)
  ui/
    app.py           the full application
    board_overlay.py the control on the left edge and the popup
    widgets/         the lens, the region selector, the plot canvas, the steps
server/             the fog server in front of Gemini
scripts/            the PowerShell scripts of the school
tests/              the tests (unit and integration)
```

## 5. The honest limits

* **Gemini is the OCR.** Aieva needs the network and the key. There is no
  offline version.
* **No engine reads every handwriting perfectly.** Glare, occlusion, a low
  resolution or an unusual notation can be misread. Every answer is checked
  by SymPy and the confidence note of Gemini is shown with it.
* **The Windows parts cannot be checked on a Linux machine.** The task of the
  task scheduler, the icon of the tray, the place of the windows and the
  PowerShell scripts are written and unit-tested, but they have to be tried
  on a real board PC.

---

## 6. The tests

```bash
python -m pytest tests -q
python -m ruff check .
python -m black --check .
```

The suite covers the OCR pipeline, the background service, the maths, the
graphs, the charts, the tray, the control on the edge, the intent of Gemini,
the pool of the Gemini keys and the scripts of Windows.

The last full run: **783 passed, 3 skipped** (the three skipped ones need a
real Gemini key).

> The tests need the packages of `requirements.txt` **and**
> `requirements-server.txt` (`fastapi`, `httpx`, `python-multipart`,
> `google-genai`) — `pip install -r requirements.txt -r requirements-server.txt
> -r requirements-dev.txt`. Without them the integration tests cannot even be
> collected.
