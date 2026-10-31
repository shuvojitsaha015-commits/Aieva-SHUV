# The Aieva API contract

The Aieva server is the **fog** part of the product: it is the only component
that talks to the cloud. Everything else (parsing, solving, plotting) runs on
the device.

* base URL: `http://<host>:8000` (the desktop default is `http://127.0.0.1:8000`)
* every route below `/api/` needs the header `X-Aieva-Key: <key>` when the
  server was started with `AIEVA_SERVER_KEY`
* answers are JSON, errors are `{"detail": "..."}`
* the interactive documentation is at `/docs` (OpenAPI)

---

## `GET /health`

Is the server alive and is it the real thing or the mock?

```json
{
  "status": "ok",
  "mock": true,
  "model": "gemini-3.8-flash",
  "version": "1.0.0"
}
```

---

## `POST /api/math/ocr`

Reads the mathematics out of a picture.

**Request:** `multipart/form-data` with the field `image` (PNG, JPEG, ...).
The image may be at most **5 MB**.

**Answer:**

```json
{
  "latex": "y = x^2 + 3x",
  "plain": "y = x**2 + 3*x",
  "confidence_note": "the coefficient could also be a 5",
  "kind": "equation"
}
```

* `kind` is one of `expression`, `equation`, `text`, `unknown`
* `plain` is meant to be parsable by SymPy (`**` is the power)
* the answer is always strict JSON - the model is called with
  `response_mime_type="application/json"`

**Errors:** `400` (empty image), `413` (image too large), `502` (the model
failed).

---

## `POST /api/math/explain`

Explains a solution that SymPy already verified on the device.

**Request:**

```json
{
  "problem_latex": "x^2 + 3x - 2 = 0",
  "sympy_answer": "x = \\frac{-3 \\pm \\sqrt{17}}{2}",
  "hints": "show the discriminant"
}
```

**Answer:**

```json
{
  "steps": [
    {
      "title": "Bring everything to one side",
      "explanation": "Subtract the right hand side so that the equation becomes zero.",
      "latex": "x^2 + 3x - 2 = 0"
    }
  ],
  "note": ""
}
```

The LLM **explains** but never changes the verified answer - the client shows
the SymPy result and only adds the words around it.

---

## `POST /api/math/wordproblem`

Turns a word problem into the structured model of the templates.

**Request:** `{"text": "A ball is thrown with 20 m/s at 45 degrees..."}`
(at most **4000 characters**).

**Answer:**

```json
{
  "problem_type": "kinematic_projectile",
  "variables": [
    {"name": "v0", "description": "initial speed", "value": 20, "unit": "m/s"}
  ],
  "equations": ["y = v0*sin(theta)*t - 0.5*g*t**2"],
  "unknowns": ["max_height"],
  "visualization_hint": "trajectory with velocity vectors",
  "parameters_for_sliders": ["v0", "theta"],
  "assumptions": ["g = 9.8 m/s^2"],
  "note": "",
  "raw": {}
}
```

`problem_type` is one of `kinematic_projectile`, `uniform_motion`,
`optimization`, `rate_tank`, `mixture`, `geometry` or `unsupported`.

---

## Protection

| What | How |
|---|---|
| Random use | the `X-Aieva-Key` header (`AIEVA_SERVER_KEY`) |
| Abuse | 30 requests per minute and per IP (`429` when it is too many) |
| Big payloads | 5 MB per image, 4000 characters per text (`413` / `422`) |
| Flaky network | two retries with an exponential backoff (0.5 s, 1 s) |
| No key | `AIEVA_MOCK_LLM=true` answers with canned data |

---

## The client

The desktop app talks to the server through
`aieva/core/llm/client.py`:

```python
from aieva.core.llm.client import AievaServerClient

client = AievaServerClient()
print(client.health())
steps = client.explain("x^2 + 3x - 2 = 0", "x = 1")
```

When the server cannot be reached the app keeps working: the solver uses the
deterministic SymPy steps and the OCR falls back to the manual input.
