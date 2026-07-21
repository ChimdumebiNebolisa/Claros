"""OpenAI Responses adapter for the closed-world worksheet compiler."""
from __future__ import annotations

import base64

import config
from evaluation.pdf_gold_pilot.closed_world import (
    _SYSTEM_INSTRUCTION,
    _prompt,
    ClosedWorldPageResult,
    PilotPageInput,
    validate_closed_world_result,
)


class OpenAISemanticCompiler:
    """Use GPT-5.6 structured output, then retain deterministic ID validation."""

    def __init__(self, client=None, model: str | None = None):
        self._client = client
        self._model = model

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - dependency deployment check
                raise RuntimeError("openai package is required for the semantic compiler") from exc
            self._client = OpenAI(api_key=config.get_openai_api_key())
        return self._client

    def compile_page(self, page: PilotPageInput, page_image: bytes) -> ClosedWorldPageResult:
        image_data_url = "data:image/png;base64," + base64.b64encode(page_image).decode("ascii")
        response = self._get_client().responses.parse(
            model=self._model or config.get_openai_reasoning_model(),
            instructions=_SYSTEM_INSTRUCTION,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": _prompt(page)},
                        {"type": "input_image", "image_url": image_data_url},
                    ],
                }
            ],
            text_format=ClosedWorldPageResult,
            max_output_tokens=4096,
            store=False,
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise RuntimeError("OpenAI compiler returned no structured output")
        result = parsed if isinstance(parsed, ClosedWorldPageResult) else ClosedWorldPageResult.model_validate(parsed)
        validate_closed_world_result(page, result)
        return result
