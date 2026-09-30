"""Normalize common model-produced LaTeX into Markdown math Streamlit can render."""
from __future__ import annotations

import re


_FENCED_CODE = re.compile(r"(```[\s\S]*?```|~~~[\s\S]*?~~~)")
_INLINE_CODE = re.compile(r"(`+)(.+?)\1")
_SQUARE_EQUATION = re.compile(r"(?m)^([ \t]*)\[\s*(.+?)\s*\]([ \t]*)$")
_PAREN_MATH = re.compile(r"\(([^()\n]{1,240})\)")


def _display_math(match: re.Match[str]) -> str:
    expression = match.group(2).strip()
    if expression.startswith("$$") and expression.endswith("$$"):
        return f"{match.group(1)}\n{expression}\n{match.group(3)}"
    if expression.startswith("$") and expression.endswith("$"):
        expression = expression[1:-1].strip()
    return f"{match.group(1)}\n$$\n{expression}\n$${match.group(3)}"


def _is_math_expression(expression: str) -> bool:
    value = expression.strip()
    variable = r"(?:[A-Za-z](?:_[A-Za-z0-9{}]+)?|\d+)"
    if re.fullmatch(r"[A-Za-z](?:[_^](?:\{[^{}]+\}|[A-Za-z0-9]+))?", value):
        return True
    return bool(
        re.search(r"\\[A-Za-z]+|(?:[_^]\{?[^\s{}]+\}?)|(?:<=|>=|=|<|>)", value)
        or re.fullmatch(rf"{variable}(?:\s*[+*/-]\s*{variable})+", value)
    )


def _normalize_plain_markdown(text: str) -> str:
    # Protect inline code so examples such as `(x_i)` remain code, not rendered math.
    code_spans: list[str] = []

    def hold_code(match: re.Match[str]) -> str:
        code_spans.append(match.group(0))
        return f"\x00INLINECODE{len(code_spans) - 1}\x00"

    text = _INLINE_CODE.sub(hold_code, text)
    text = re.sub(r"(?ms)^([ \t]*)\\\[(.*?)\\\]([ \t]*)$", _display_math, text)
    text = re.sub(r"\\\((.+?)\\\)", lambda m: f"${m.group(1).strip()}$", text, flags=re.S)

    def square_equation(match: re.Match[str]) -> str:
        expression = match.group(2).strip()
        if not _is_math_expression(expression):
            return match.group(0)
        if expression.startswith("$$") and expression.endswith("$$"):
            expression = expression[2:-2].strip()
        elif expression.startswith("$") and expression.endswith("$"):
            expression = expression[1:-1].strip()
        return f"{match.group(1)}\n$$\n{expression}\n$${match.group(3)}"

    text = _SQUARE_EQUATION.sub(square_equation, text)

    def inline_equation(match: re.Match[str]) -> str:
        expression = match.group(1).strip()
        if not _is_math_expression(expression):
            return match.group(0)
        return f"${expression}$"

    text = _PAREN_MATH.sub(inline_equation, text)
    for index, code in enumerate(code_spans):
        text = text.replace(f"\x00INLINECODE{index}\x00", code)
    return text


def normalize_markdown_math(markdown: str) -> str:
    """Convert common raw LaTeX delimiters to `$` / `$$` without editing code fences."""
    chunks = _FENCED_CODE.split(str(markdown or ""))
    return "".join(
        chunk if index % 2 else _normalize_plain_markdown(chunk)
        for index, chunk in enumerate(chunks)
    )
