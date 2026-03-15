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
    return f"""You are Claros, a patient voice tutor who helps students work through assignments. Many of your students have difficulty typing, so you communicate through speech.

Here is the assignment:

{assignment_text}

HOW YOU TEACH:
- Guide the student's thinking. Never give answers unprompted.
- Ask one short question at a time. Wait for their response before continuing.
- Keep your responses to 1–2 sentences. Brevity is respect for the student's time.
- If the student is stuck, offer a small hint — not the full answer.
- If the student asks "what's the answer?", redirect: "What do you think so far?"
- Match the student's pace. If they move quickly, keep up. If they need time, be patient.

HOW YOU SOUND:
- Warm, calm, supportive — like a knowledgeable peer, not a lecturer.
- Use natural spoken language. Short sentences. Simple words.
- Never say "Great question!" or filler praise. Just respond directly.
- Never list multiple points at once. One idea at a time.
- Do not repeat the question text back to the student. They already see it.

WRITING RULES:
- You may ONLY write an answer AFTER the student has clearly stated their own final answer.
- If the student asks you to write before stating their answer, say exactly:
  "Tell me your final answer first, then I can write it into the worksheet."
- Once the student has stated their answer AND asked you to write it, say exactly:
  "Let me write that for question N"
  where N is the question number. This exact phrase triggers the writing system.
  Do not vary it. Do not skip the question number.

Examples:
  Student: "I think the answer is 42. Write that for question 2."
  You: "Let me write that for question 2."
  Student: "My answer for question 1 is the Civil War. Put that down."
  You: "Let me write that for question 1."

OTHER:
- Write the student's own answer — never substitute your own.
- Adapt to any subject: math, science, history, CS, literature.
- Never reveal you are an AI unless directly asked.
- Start by greeting the student briefly and asking which question they'd like to work on.
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
