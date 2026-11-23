"""Tiny helpers for the generated Markdown reports."""
from __future__ import annotations

from pathlib import Path


def write_text(path: Path, text: str) -> None:
    """UTF-8 with Unix line endings on every OS, so regenerated files diff cleanly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def fmt(value, digits: int = 3) -> str:
    if value is None:
        return "–"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def table(rows: list[dict], columns: list[tuple[str, str]], digits: int = 3) -> str:
    """``columns`` is a list of (key, header) pairs."""
    head = "| " + " | ".join(h for _, h in columns) + " |"
    rule = "|" + "|".join("---" for _ in columns) + "|"
    body = ["| " + " | ".join(fmt(r.get(k, ""), digits) for k, _ in columns) + " |" for r in rows]
    return "\n".join([head, rule, *body])


def pct(value: float, digits: int = 1) -> str:
    return f"{100 * value:.{digits}f}%"
