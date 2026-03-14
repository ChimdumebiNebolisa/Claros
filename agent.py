"""
Claros agent: system prompt builder and [WRITE:question_id] / [END_WRITE:question_id] token detection.
Emits write_start, write_token, write_end events for the frontend.
"""
import re
from typing import Iterator


_WRITE_START_RE = re.compile(r"\[WRITE\s*:\s*(\d+)\]\s*", re.IGNORECASE)
_END_WRITE_RE = re.compile(r"\[END_WRITE\s*:\s*(\d+)\]\s*", re.IGNORECASE)


def build_system_prompt(assignment_text: str) -> str:
    """Build Claros system prompt with assignment context."""
    return f"""You are Claros, a Socratic study tutor. You have been given the following assignment:

{assignment_text}

Your behavior rules:
1. Default to TEACH mode. Guide the student with questions. Never give away answers unprompted.
2. When the student asks for an answer (e.g. "what's the answer?", "write my answer", "put that down"), speak the answer aloud. Written answers are handled separately — you do not need to emit any special tokens.
3. Answers must reflect what the student discussed with you — not generic textbook answers.
4. Be concise. Sound like a knowledgeable peer, not a textbook.
5. Subject scope: any subject — CS, math, history, science, literature. Adapt accordingly.
6. Never reveal you are an AI unless directly asked.
"""


class WriteTokenParser:
    """Stateful parser for streaming text. Call feed(text) to get write_start/write_token/write_end events."""

    def __init__(self) -> None:
        self._current_qid: int | None = None
        self._accumulated: str = ""
        self._buffer: str = ""

    def feed(self, text: str) -> list[dict]:
        """Process a chunk of text. Returns list of events: write_start, write_token, write_end."""
        events: list[dict] = []
        combined = self._buffer + text
        self._buffer = ""
        i = 0
        while i < len(combined):
            if self._current_qid is None:
                m = _WRITE_START_RE.match(combined, i)
                if m:
                    self._current_qid = int(m.group(1))
                    events.append({"event": "write_start", "question_id": self._current_qid})
                    i = m.end()
                    continue
                m = _END_WRITE_RE.match(combined, i)
                if m:
                    i = m.end()
                    continue
                # Keep suffix in case "[WRITE:1]" spans chunk boundary
                tail = combined[i:]
                self._buffer = tail if len(tail) <= 30 else tail[-30:]
                break
            else:
                m_end = _END_WRITE_RE.search(combined, i)
                m_start = _WRITE_START_RE.search(combined, i)
                end_pos = m_end.start() if m_end else len(combined)
                start_pos = m_start.start() if m_start else len(combined)
                next_delim = min(end_pos, start_pos)
                if next_delim == len(combined):
                    self._accumulated += combined[i:]
                    break
                self._accumulated += combined[i:next_delim]
                if m_end and (not m_start or m_end.start() <= m_start.start()):
                    sentence = self._accumulated.strip()
                    if sentence:
                        events.append({"event": "write_token", "question_id": self._current_qid, "text": sentence + " "})
                    events.append({"event": "write_end", "question_id": self._current_qid})
                    self._current_qid = None
                    self._accumulated = ""
                    i = m_end.end()
                else:
                    sentence = self._accumulated.strip()
                    if sentence:
                        events.append({"event": "write_token", "question_id": self._current_qid, "text": sentence + " "})
                    events.append({"event": "write_end", "question_id": self._current_qid})
                    self._current_qid = int(m_start.group(1))
                    events.append({"event": "write_start", "question_id": self._current_qid})
                    self._accumulated = ""
                    i = m_start.end()
        if self._buffer and len(self._buffer) > 200:
            self._buffer = self._buffer[-200:]
        return events
