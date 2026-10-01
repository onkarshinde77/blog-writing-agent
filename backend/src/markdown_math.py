"""Normalize common model-produced LaTeX into portable Markdown math."""
from __future__ import annotations

import re


_FENCED_CODE = re.compile(r"(```[\s\S]*?```|~~~[\s\S]*?~~~)")
_INLINE_CODE = re.compile(r"(`+)(.+?)\1")
_SQUARE_EQUATION = re.compile(r"(?m)^([ \t]*)\[\s*(.+?)\s*\]([ \t]*)$")
_PAREN_MATH = re.compile(r"\(([^()\n]{1,240})\)")
_DISPLAY_DOLLARS = re.compile(r"\$\$(.+?)\$\$", re.S)
_ESCAPED_DOLLARS = re.compile(r"\\{1,2}\$(?!\$)([^$\n]{1,1200}?)\\{1,2}\$(?!\$)")
_DISPLAY_BRACKETS = re.compile(r"\\{1,2}\[([\s\S]+?)\\{1,2}\]")
_INLINE_LATEX = re.compile(r"\\{1,2}\(([\s\S]+?)\\{1,2}\)")
_BARE_LATEX_LINE = re.compile(
    r"(?m)^([ \t]*)(?=.*\\[A-Za-z]+)(?=.*(?:=|[_^]))(.+?)([ \t]*)$"
)


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

    def escaped_dollars(match: re.Match[str]) -> str:
        expression = match.group(1).strip().replace(r"\\", "\\")
        if _is_math_expression(expression):
            return f"${expression}$"
        return match.group(0)

    # Some model responses escape math delimiters as `\$...\$`, which
    # prevents remark-math from recognizing them as equations.
    text = _ESCAPED_DOLLARS.sub(escaped_dollars, text)

    # A model may emit either one or two backslashes before TeX delimiters.
    # Keep display-math $$ delimiters on their own lines, even when the model
    # puts an equation on a prose line.
    def display_block(match: re.Match[str]) -> str:
        expression = match.group(1).strip().replace(r"\\", "\\")
        return f"\n\n$$\n{expression}\n$$\n\n"

    text = _DISPLAY_BRACKETS.sub(display_block, text)
    text = _DISPLAY_DOLLARS.sub(display_block, text)

    def inline_latex(match: re.Match[str]) -> str:
        expression = match.group(1).strip().replace("\\\\", "\\")
        return f"${expression}$"

    text = _INLINE_LATEX.sub(inline_latex, text)

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

    # Handle unwrapped standalone LaTeX equations as display math as well.
    def bare_latex_equation(match: re.Match[str]) -> str:
        expression = match.group(2).strip().replace(r"\\", "\\")
        return f"{match.group(1)}\n$$\n{expression}\n$$"

    text = _BARE_LATEX_LINE.sub(bare_latex_equation, text)

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
