"""
Deprecated alias for the canonical sample producer.

Use `python test_assignment.py` instead. This file remains only so older docs
and scripts do not silently overwrite the sample with a blank-free PDF.
"""

from test_assignment import PDF_FILENAME, build_assignment


def main() -> None:
    path = build_assignment(PDF_FILENAME)
    print(f"Created {path} via canonical test_assignment.build_assignment()")


if __name__ == "__main__":
    main()
