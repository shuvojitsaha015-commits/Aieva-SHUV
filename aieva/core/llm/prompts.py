"""The prompts that are sent to the LLM.

They live in the core (and not in the server) so that the desktop app, the
server and the tests all use exactly the same wording.
"""

from __future__ import annotations

#: The OCR prompt - the model has to answer with strict JSON.
OCR_PROMPT = """You are the OCR engine of a maths teaching board.
Read the mathematical expression in the image and answer with STRICT JSON:

{
  "latex": "the expression in LaTeX, for example y = x^2 + 3x",
  "plain": "the same expression as a SymPy parsable string, for example y = x**2 + 3*x",
  "confidence_note": "one short sentence about how sure you are and what could be wrong",
  "kind": "expression | equation | text | unknown",
  "intent": "solve | graph | both | none",
  "answer": "the direct final solution/answer if this is an equation, integral, derivative, or calculus problem",
  "steps": [{"title": "step title", "explanation": "clear step explanation", "latex": "step formula"}],
  "chart": null
}

Rules:
* "plain" MUST be parsable by SymPy (use ** for the power, * for the product).
* "intent" says what should be done with the problem:
  - "solve"   the teacher wants the answer (an equation to solve, a value to find)
  - "graph"   the teacher wants the picture (a function to plot, a curve to see)
  - "both"    the answer and the picture are wanted
  - "none"    there is no mathematics on the board
* "chart" is for a TABLE of values (a row of numbers, a small table of
  measurements). It is null when there is no table. When there is one, answer
  with:
  {"title": "what the table shows", "labels": ["name", "name"],
   "values": [1.5, 2.5], "kind": "bar | line | pie", "unit": "the unit"}
  - "labels" and "values" must have the same length
  - "kind" is "bar" for a comparison, "line" for a development over the labels
    and "pie" when the values are shares of a whole
* Only output the JSON object, no explanation and no markdown fence.
* If the image contains no maths, use "kind": "unknown", "intent": "none" and an
  empty "latex".
"""

#: The explanation prompt - the LLM explains, it must not change the answer.
EXPLAIN_PROMPT = """You are a maths tutor. Explain the following solution step by step.

The problem (LaTeX):
{problem_latex}

The verified answer (computed with SymPy, it is correct - never change it):
{sympy_answer}

Additional hints from the teacher:
{hints}

Answer with STRICT JSON:
{
  "steps": [
    {"title": "short title", "explanation": "one or two sentences in plain language",
     "latex": "the formula of this step in LaTeX"}
  ]
}

Rules:
* Between 2 and 8 steps.
* The last step must show the verified answer unchanged.
* Only output the JSON object, no markdown fence.
"""

#: The word problem prompt - the structured model of Phase 9.
WORDPROBLEM_PROMPT = """You turn a word problem into a structured model.

The problem:
{text}

Answer with STRICT JSON:
{
  "problem_type": "kinematic_projectile | uniform_motion | optimization | rate_tank | mixture | geometry | unsupported",
  "variables": [
    {"name": "v0", "description": "initial speed", "value": 20, "unit": "m/s"}
  ],
  "equations": ["y = v0*sin(theta)*t - 0.5*g*t**2"],
  "unknowns": ["max_height"],
  "visualization_hint": "trajectory with velocity vectors",
  "parameters_for_sliders": ["v0", "theta"],
  "assumptions": ["g = 9.8 m/s^2"]
}

Rules:
* "equations" must be parsable by SymPy.
* If the problem is not one of the listed types, use "unsupported" and leave
  the other fields empty.
* Only output the JSON object, no markdown fence.
"""

#: The prompt that repairs a broken JSON answer.
REPAIR_PROMPT = """The answer you sent was not valid JSON. Answer again with STRICT JSON only,
without any explanation and without a markdown fence. This is what you sent:

{broken}
"""


def render_prompt(template: str, **values: str) -> str:
    """Fill the placeholders of a prompt - without touching the JSON braces.

    ``str.format`` would read every ``{...}`` of the prompt as a
    placeholder. The prompts of Aieva show the wanted JSON to the model,
    so they are full of braces and ``format`` died with

        KeyError: '\n  "problem_type"'
    """
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


__all__ = [
    "EXPLAIN_PROMPT",
    "OCR_PROMPT",
    "REPAIR_PROMPT",
    "WORDPROBLEM_PROMPT",
    "render_prompt",
]
