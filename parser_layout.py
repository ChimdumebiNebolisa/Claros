"""Layout heuristics for worksheet PDF parsing (headers, footers, body text)."""
from __future__ import annotations

from statistics import median


def median_body_font_size(lines_with_size: list[tuple[str, float]]) -> float:
    sizes = [s for _, s in lines_with_size if s > 0]
    if not sizes:
        return 0.0
    return float(median(sizes))


def is_likely_header_footer(line: str, font_size: float, body_size: float) -> bool:
    if not line.strip():
        return True
    if body_size > 0 and font_size > 0 and font_size < body_size * 0.85:
        return True
    lower = line.strip().lower()
    if lower.isdigit() and len(lower) <= 3:
        return True
    if "page " in lower and any(ch.isdigit() for ch in lower):
        return True
    return False


def filter_header_footer_lines(lines_with_size: list[tuple[str, float]]) -> list[tuple[str, float]]:
    body = median_body_font_size(lines_with_size)
    return [
        (text, size)
        for text, size in lines_with_size
        if not is_likely_header_footer(text, size, body)
    ]
