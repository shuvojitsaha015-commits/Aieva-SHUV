# Manual Steps Needed (Human Action Required)

> These are the steps that **only a human can do**. The build continues with mocks and stubs while
> they are outstanding. Every item lists the exact command or URL to use.

- [ ] **Python 3.11** installed. Verify with `python --version`.
- [ ] **Git + GitHub repo** created, all 4 members added as collaborators. Branch rule: `main` (stable), `dev` (integration), and `feature/<name>` branches.
- [ ] **Gemini API key.** Go to https://aistudio.google.com, click "Get API key", and put it in `.env` as `GEMINI_API_KEY=...`. (Free tier is enough.) The model is configurable - `GEMINI_MODEL=gemini-3.8-flash` is the current stable Flash model (`gemini-2.0-flash` was shut down on 1 June 2026, see <https://ai.google.dev/gemini-api/docs/models>).
- [ ] **(Optional) Wolfram Alpha AppID**, for verification only. `.env`: `WOLFRAM_APP_ID=...`
- [ ] **(Optional) OpenAI key** as an LLM fallback. `.env`: `OPENAI_API_KEY=...`
- [ ] **Cloud/fog server hosting.** For development, run the FastAPI server on localhost. For the demo, one team member's laptop on the same Wi-Fi as the board, **or** a free host (Render/Railway/Fly.io). Record the final URL in `.env` as `AIEVA_SERVER_URL=...`.
- [ ] **Test hardware:** know the smart board's Android version and screen resolution. Write them into `docs/PROGRESS.md`. If no board is available, use an Android phone or tablet.
- [ ] ~~**For Phase 11 only:** Docker Desktop installed, or a Linux/WSL2 machine for Buildozer.~~ **Not needed** - no APK is built in this cycle (see `docs/DECISIONS.md`, ADR-001).
- [ ] **Test images:** the team photographs or screenshots 15–20 sample equations (printed, handwritten, whiteboard) into `tests/fixtures/images/`, with a `labels.json` giving the expected LaTeX for each.

---

## How to unblock each item

### 1. Python 3.11

```bash
python3.11 --version     # expect: Python 3.11.x
```

If your OS only ships 3.12/3.13, the project still works (SymPy 1.12+ and Kivy 2.3+ both support
3.11-3.13). 3.11 is only *required* for the Android/Buildozer toolchain in Phase 11.

### 2. GitHub repo + collaborators

```bash
git remote add origin https://github.com/<org>/aieva.git
git push -u origin main
```

Then add the 4 members as collaborators (Settings -> Collaborators) and create the
`dev` and `feature/<name>` branches.

### 3. Gemini API key

1. Open <https://aistudio.google.com> -> **Get API key** -> copy the key.
2. `cp .env.example .env`
3. Put the key in `.env`:

   ```
   GEMINI_API_KEY=your_key_here
   ```

Without a key the server still runs in mock mode (`AIEVA_MOCK_LLM=true`), which is what the
automated tests use.

### 4. Wolfram Alpha AppID (optional)

<https://developer.wolframalpha.com/> -> get an AppID -> `WOLFRAM_APP_ID=...` in `.env`.
Only used to double-check SymPy answers; the app works without it.

### 5. OpenAI key (optional fallback)

`OPENAI_API_KEY=...` in `.env`. Only used as a fallback LLM provider.

### 6. The background OCR worker (the instructor request)

The OCR runs in the background - as a service that watches a folder:

```bash
./scripts/run_ocr_worker.sh                      # watches ./ocr_inbox -> ./ocr_outbox
./scripts/run_ocr_worker.sh --inbox /tmp/shots --outbox /tmp/results
./scripts/run_ocr_worker.sh --mock --once        # read what is there and exit
```

Every new image in the inbox is read (through the server, or with the mock
engine) and the result is written as `<name>.json` into the outbox. Inside the
app the same worker runs as a daemon thread, so the UI is never blocked.

### 7. Cloud/fog server hosting

Local development (nothing to buy):

```bash
./scripts/run_server.sh          # http://127.0.0.1:8000
```

Free hosting for the demo: deploy the `server/Dockerfile` to Render/Railway/Fly.io, then set

```
AIEVA_SERVER_URL=https://<your-host>
```

in `.env` **on the board/device** so the app talks to the cloud copy.

### 8. Test hardware

Record in `docs/PROGRESS.md`:

```
Smart board: <brand/model>
Android version: <e.g. 11>
Screen resolution: <e.g. 1920x1080>
DPI / density: <e.g. 160dpi>
```

If no board exists, use any Android phone or tablet with a screen-capture app.

### 9. Docker Desktop - NOT needed

No APK is built in this cycle (see `docs/DECISIONS.md`, ADR-001), so Docker is
only required if the team later decides to package the app for the board.

### 10. Test images (OCR fixtures)

Drop 15-20 cropped equation images into `tests/fixtures/images/` and create
`tests/fixtures/images/labels.json`:

```json
{
  "line_01.png": "y = mx + c",
  "circle_01.png": "x^{2} + y^{2} = r^{2}"
}
```

The agent ships `scripts/make_fixtures.py`, which generates *synthetic* placeholder images so the
OCR pipeline is testable offline; the real photographs should replace them.

---

## Status

| Item | Status | Notes |
|---|---|---|
| Python 3.11 | Pending | Sandbox has 3.13; supported. |
| GitHub repo | Pending | Local git repo exists; remote not configured. |
| Gemini API key | Pending | Server runs in `AIEVA_MOCK_LLM=true` mode meanwhile. |
| Wolfram AppID | Pending | Optional; SymPy is the primary verifier. |
| OpenAI key | Pending | Optional fallback. |
| Server hosting | Pending | Local server provided by `scripts/run_server.sh`. |
| Background OCR worker | Ready | `./scripts/run_ocr_worker.sh` - runs without a key (mock engine). |
| Test hardware | Pending | Recorded in `docs/PROGRESS.md` once known. |
| Docker | Not needed | No APK is built in this cycle (ADR-001). |
| Test images | Pending | Synthetic placeholders generated; real photos wanted. |
