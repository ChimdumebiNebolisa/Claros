"""Gemini service unit tests without live provider calls."""
import asyncio

import gemini_service


async def _collect(agen):
    return [piece async for piece in agen]


def test_stamp_confirmed_answer_preserves_the_exact_authorized_text():
    approved = "Case Sensitive $x$  \u03c0"
    chunks = asyncio.run(_collect(gemini_service.stamp_confirmed_answer(approved)))
    assert chunks == [approved]
