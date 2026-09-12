"""Strictly reopen a browser-downloaded PDF and report parser warnings."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pikepdf
from pypdf import PdfReader


def main() -> None:
    pdf_path = Path(sys.argv[1])
    with pikepdf.open(pdf_path) as document:
        result = {
            "pageCount": len(document.pages),
            "warnings": [*document.check_pdf_syntax(), *document.get_warnings()],
            "text": "\n".join(page.extract_text() or "" for page in PdfReader(pdf_path).pages),
        }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
