"""Privacy contract tests for operational metrics."""
import logging

import pytest

from observability import record_metric


def test_metric_event_uses_fixed_safe_labels(caplog):
    with caplog.at_level(logging.INFO):
        record_metric("write_conflict", status="conflict", reason="storage")

    assert "metric event=write_conflict status=conflict reason=storage" in caplog.text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"event": "unknown_event"},
        {"event": "export", "status": "answer text"},
        {"event": "export", "reason": "question text"},
    ],
)
def test_metric_rejects_unbounded_content_labels(kwargs):
    with pytest.raises(ValueError):
        record_metric(**kwargs)
