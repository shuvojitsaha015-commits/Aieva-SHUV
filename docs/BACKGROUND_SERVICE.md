# The background service of the board

Aieva is an **application that works in the background of the smart board**.
It looks at the board on its own, notices what was written there, reads the
mathematics, solves it and draws the graph - the teacher does not have to
press anything.

```
   board  ──▶  capture  ──▶  "did something change?"  ──▶  OCR  ──▶  solve  ──▶  graph
                            (no change = nothing happens)              │
                                                                          ▼
                                              the results (JSON) + the floating window
```

The service is a normal Python program (no Kivy), so it runs on a small
board computer, in the background, and it can be tested without a screen.

---

## Start it

**Windows (PowerShell)**

```powershell
.\scripts\start_service.ps1            # in the background, no window
.\scripts\start_service.ps1 -Overlay   # with the floating window above the board
.\scripts\stop_service.ps1             # stop it again
```

**Linux / macOS / Termux**

```bash
./scripts/run_service.sh
```

**Any platform, directly**

```powershell
python -m aieva.core.service run
python -m aieva                       # the same thing
```

The terminal can be closed right away - the service keeps running. To see
what it is doing:

```powershell
python -m aieva.core.service status
```

---

## Start with the computer (nothing to do in the morning)

**Windows**

```powershell
.\scripts\install_autostart.ps1           # starts when somebody logs in
.\scripts\install_autostart.ps1 -OnStart  # starts when the computer boots
```

The service is registered as a task of the task scheduler and starts with
``pythonw.exe`` - no console window ever appears on the board.

**Linux / Termux**

```bash
python -m aieva.core.service install-autostart
systemctl --user daemon-reload
systemctl --user enable --now aieva.service
```

**macOS**

```bash
python -m aieva.core.service install-autostart
launchctl load ~/Library/LaunchAgents/com.aieva.board-service.plist
```

Undo it with ``python -m aieva.core.service uninstall-autostart``.

---

## What it does, step by step

1. **Capture** - the screen of the board computer (``desktop``) or the newest
   picture of a folder (``folder``, for a board that shares its screen).
2. **Change check** - a small thumbnail of the board is compared with the
   last one. Nothing new on the board means nothing happens (the service
   sleeps).
3. **OCR** - the mathematics is read and checked with SymPy. A result that
   SymPy cannot parse is marked as "please check".
4. **Solve** - the equation is classified and solved with SymPy (the answer
   of SymPy wins over the answer of the cloud).
5. **Draw** - the graph of the equation is saved as a picture.
6. **Publish** - the reading, the solution and the picture are written into
   the outbox and shown in the floating window.

### The files it writes

| File | What it is |
|---|---|
| ``ocr_outbox/board-<time>.json`` | one file per reading (the reading, the solution, the steps, the picture) |
| ``ocr_outbox/history.jsonl`` | the last readings, one per line |
| ``.aieva_cache/service_state.json`` | the status of the service (running, readings, errors, the last result) |
| ``.aieva_cache/last_result.json`` | the file the floating window reads |
| ``.aieva_cache/captures/`` | the pictures of the board |
| ``.aieva_cache/plots/`` | the graphs |
| ``aieva.log`` | the log of the service |

---

## The floating window

With ``--overlay`` a small window floats above the board (top right). It shows
what was read, the solution and the graph - and disappears again after a few
seconds, so the board stays clean.

---

## The window of the teacher

The application (``python -m aieva.ui.app``) and the service are the same
system:

* the **Settings** tab has a *Background service* block: a switch, the status
  and the buttons *Start*, *Stop* and *Start with the computer*;
* the application starts the service with it (unless the switch is off) and
  stops it when the window is closed;
* the service also runs completely without the window - that is the point
  for a board.

---

## The settings

They are read from the environment (``.env``):

| Variable | Meaning | Default |
|---|---|---|
| ``AIEVA_SERVICE_SOURCE`` | ``auto`` / ``desktop`` / ``folder`` | ``auto`` |
| ``AIEVA_SERVICE_INTERVAL`` | how often the board is looked at (s) | ``2`` |
| ``AIEVA_SERVICE_MIN_INTERVAL`` | the shortest time between two readings (s) | ``2`` |
| ``AIEVA_SERVICE_THRESHOLD`` | how much the board has to change (0 - 1) | ``0.004`` |
| ``AIEVA_SERVICE_MAX_RUNS`` | the most readings per minute | ``12`` |
| ``AIEVA_SERVICE_FOLDER`` | the folder with the pictures of the board | ``ocr_inbox`` |
| ``AIEVA_SERVICE_OUTBOX`` | where the results are written | ``ocr_outbox`` |
| ``AIEVA_SERVICE_STATE`` | the status file | ``.aieva_cache/service_state.json`` |
| ``AIEVA_SERVICE_SOLVE`` | solve the reading | ``true`` |
| ``AIEVA_SERVICE_PLOT`` | draw the reading | ``true`` |
| ``AIEVA_SERVICE_OVERLAY`` | show the floating window | ``false`` |
| ``AIEVA_SERVICE_MOCK`` | use the mock OCR (no cloud) | ``false`` |

---

## Troubleshooting

| What you see | What it means |
|---|---|
| ``No capture source is available`` | neither a screen nor a folder with pictures was found |
| ``There is no picture in ocr_inbox`` | the folder source is empty (the board has to share its screen) |
| ``The board could not be read`` | the capture failed - the log has the details |
| the service runs, but nothing happens | the board did not change enough - lower ``AIEVA_SERVICE_THRESHOLD`` |
| the reading is empty | the OCR needs the cloud: set ``GEMINI_API_KEY`` in ``.env`` or start the server |
| ``the floating window does not appear`` | the overlay needs a display; on a board it is the screen of the board |

The log is the best friend:

```powershell
Get-Content aieva.log -Tail 40
```

---

## The design

* the service never blocks the interface of the teacher (it runs in a thread),
* the OCR, the solution and the drawing all happen **outside** the user
  interface thread,
* the mathematics is always checked with SymPy - the answer of the cloud is
  never trusted,
* the service survives every error: a broken picture is remembered and
  skipped, the next cycle tries again.
