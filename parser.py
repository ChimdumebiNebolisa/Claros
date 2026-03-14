"""
PDF question extraction for Claros. Uses PyMuPDF with heuristics:
- Numbered lines (1. 2) etc.)
- Lines containing ?
- Lines with larger font than body
Fallback: if fewer than 2 questions, return full text as single block (id: 0).
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

import fitz  # PyMuPDF


@dataclass
class Question:
    id: int
    text: str


def _extract_lines_with_size(doc: fitz.Document) -> List[tuple[str, float]]:
    """Extract (line_text, font_size) for each line from PDF. Uses first span size per line."""
    lines: List[tuple[str, float]] = []
    for page in doc:
        block_dict = page.get_text("dict", sort=True)
        for block in block_dict.get("blocks", []):
            for line in block.get("lines", []):
                line_text_parts = []
                line_size = None
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if text:
                        line_text_parts.append(text)
                        if line_size is None and "size" in span:
                            line_size = span["size"]
                if line_text_parts:
                    text = " ".join(line_text_parts).strip()
                    if text:
                        lines.append((text, line_size if line_size is not None else 0.0))
    return lines


def _body_font_size(lines: List[tuple[str, float]]) -> float:
    """Median font size of lines that don't look like headers (no leading digit, no ?)."""
    sizes = [s for _, s in lines if s and s > 0]
    if not sizes:
        return 12.0
    sizes.sort()
    return sizes[len(sizes) // 2]


# Numbered line: "1." "2)" "10." etc.
_NUMBERED_START = re.compile(r"^\s*\d+[.)]\s*")
# Line contains a question mark
_HAS_QUESTION = re.compile(r"\?")


def _is_question_boundary(line: str, size: float, body_size: float) -> bool:
    if _NUMBERED_START.match(line):
        return True
    if _HAS_QUESTION.search(line):
        return True
    if body_size > 0 and size > body_size * 1.15:  # header-sized
        return True
    return False


def parse_pdf(pdf_path: str | Path) -> tuple[str, List[Question]]:
    """
    Parse PDF and extract questions. Returns (title, questions).
    Title is derived from first line or filename. If fewer than 2 questions,
    returns one question with id=0 and full text as fallback.
    """
    path = Path(pdf_path)
    doc = fitz.open(path)
    try:
        lines_with_size = _extract_lines_with_size(doc)
        if not lines_with_size:
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            full_text = full_text.strip() or "(No extractable text)"
            return path.stem, [Question(id=0, text=full_text)]

        body_size = _body_font_size(lines_with_size)
        title = lines_with_size[0][0][:80] if lines_with_size else path.stem

        questions: List[Question] = []
        current_chunks: List[str] = []

        for line_text, size in lines_with_size:
            if _is_question_boundary(line_text, size or 0, body_size):
                if current_chunks:
                    q_text = "\n".join(current_chunks).strip()
                    if q_text:
                        questions.append(Question(id=len(questions) + 1, text=q_text))
                current_chunks = [line_text]
            else:
                current_chunks.append(line_text)

        if current_chunks:
            q_text = "\n".join(current_chunks).strip()
            if q_text:
                questions.append(Question(id=len(questions) + 1, text=q_text))

        if len(questions) < 2:
            full_text = "\n".join(t for t, _ in lines_with_size).strip()
            return title, [Question(id=0, text=full_text)]

        return title, questions
    finally:
        doc.close()
