"""Parser evaluation corpus must stay non-vacuous."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_eval_parser():
    path = ROOT / "scripts" / "eval_parser.py"
    spec = importlib.util.spec_from_file_location("claros_eval_parser", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parser_eval_corpus_has_labeled_cases():
    evaluate = _load_eval_parser().evaluate
    corpus = ROOT / "tests" / "fixtures" / "parser"
    report = evaluate(corpus)
    assert report["cases"] >= 2
    assert report["expected_questions"] >= 6
    assert report["boundary_recall"] == 1.0
