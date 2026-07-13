"""Deterministic PDF fixtures for worksheet layout tests."""
from __future__ import annotations

from pathlib import Path

import fitz


def write_simple_one_column(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Algebra Practice", fontsize=16)
    page.insert_text((72, 140), "Question 1: Solve for x: 3x + 7 = 22", fontsize=12)
    page.insert_text((72, 280), "Question 2: Solve for x: 2(x - 4) = 10", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def write_multiline_questions(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Long Prompts", fontsize=14)
    page.insert_text((72, 120), "Question 1: Start of problem", fontsize=12)
    page.insert_text((72, 140), "continuation line without question prefix", fontsize=12)
    page.insert_text((72, 250), "Question 2: Second problem", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def write_two_column(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Two Column Sheet", fontsize=14)
    page.insert_text((72, 140), "Question 1: Left column first", fontsize=11)
    page.insert_text((72, 280), "Question 2: Left column second", fontsize=11)
    page.insert_text((330, 140), "Question 3: Right column first", fontsize=11)
    page.insert_text((330, 280), "Question 4: Right column second", fontsize=11)
    doc.save(str(path))
    doc.close()
    return path


def write_table_like(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Table Style", fontsize=14)
    page.insert_text((72, 130), "1. Name the capital of France", fontsize=12)
    page.draw_line(fitz.Point(72, 160), fitz.Point(540, 160))
    page.insert_text((72, 210), "2. Name the capital of Spain", fontsize=12)
    page.draw_line(fitz.Point(72, 240), fitz.Point(540, 240))
    doc.save(str(path))
    doc.close()
    return path


def write_multipage(path: Path) -> Path:
    doc = fitz.open()
    page1 = doc.new_page(width=612, height=792)
    page1.insert_text((72, 72), "Page One", fontsize=14)
    page1.insert_text((72, 140), "Question 1: First page item", fontsize=12)
    page2 = doc.new_page(width=612, height=792)
    page2.insert_text((72, 72), "Page Two", fontsize=14)
    page2.insert_text((72, 140), "Question 2: Second page item", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def write_unicode_math(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Unicode Math", fontsize=14)
    page.insert_text((72, 140), "Question 1: Solve x \u2212 3 = 5", fontsize=12)
    page.insert_text((72, 240), "Question 2: Compare \u201cA\u201d and \u201cB\u201d", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def write_answer_lines(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Fill In", fontsize=14)
    page.insert_text((72, 130), "Question 1: What is 2 + 2?", fontsize=12)
    page.draw_line(fitz.Point(72, 180), fitz.Point(540, 180))
    page.draw_line(fitz.Point(72, 210), fitz.Point(540, 210))
    page.insert_text((72, 250), "Question 2: What is 3 + 3?", fontsize=12)
    page.draw_line(fitz.Point(72, 300), fitz.Point(540, 300))
    doc.save(str(path))
    doc.close()
    return path


def write_image_only(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # Draw a filled rectangle (no text layer) to simulate a scan.
    page.draw_rect(fitz.Rect(72, 72, 540, 720), color=(0.8, 0.8, 0.8), fill=(0.85, 0.85, 0.9))
    doc.save(str(path))
    doc.close()
    return path


def write_ambiguous_spacing(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Tight Layout", fontsize=14)
    page.insert_text((72, 120), "Question 1: Nearby next item", fontsize=12)
    page.insert_text((72, 136), "Question 2: Almost overlapping", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path
