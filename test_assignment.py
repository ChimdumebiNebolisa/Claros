"""
Canonical Claros sample worksheet producer.

Writes test_assignment.pdf with one intentional answer blank per question.
Other scripts must not overwrite this PDF with a blank-free layout.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

PDF_FILENAME = "test_assignment.pdf"


def build_assignment(output_path: str = PDF_FILENAME) -> str:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="Title",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=12,
    )
    question_style = ParagraphStyle(
        name="Question",
        parent=styles["Normal"],
        fontSize=12,
        spaceBefore=14,
        spaceAfter=6,
    )
    answer_style = ParagraphStyle(
        name="AnswerLine",
        parent=styles["Normal"],
        fontSize=12,
        spaceAfter=10,
    )

    story = []

    story.append(Paragraph("Math Assignment - Grades 9-10", title_style))
    story.append(Paragraph("Claros sample algebra worksheet", styles["Normal"]))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph(
        "<b>Question 1:</b> Solve for <i>x</i>: &nbsp; 3<i>x</i> + 7 = 22",
        question_style,
    ))
    story.append(Paragraph("Show your work. Answer: <i>x</i> = ________", answer_style))

    story.append(Paragraph(
        "<b>Question 2:</b> Solve for <i>x</i>: &nbsp; -2<i>x</i> - 5 = 11",
        question_style,
    ))
    story.append(Paragraph("Show your work. Answer: <i>x</i> = ________", answer_style))

    story.append(Paragraph(
        "<b>Question 3:</b> Solve for <i>x</i>: &nbsp; 4(<i>x</i> - 3) + 2<i>x</i> = 5<i>x</i> + 6",
        question_style,
    ))
    story.append(Paragraph(
        "Simplify both sides, then solve. Show your work. Answer: <i>x</i> = ________",
        answer_style,
    ))

    story.append(Paragraph(
        "<b>Question 4:</b> A rectangle has a length that is 3 more than twice its width. "
        "The perimeter of the rectangle is 42 cm. Find the width and the length. "
        "Write an equation, solve it, and state your answer with units.",
        question_style,
    ))
    story.append(Paragraph("Final answer: ________________________________", answer_style))

    story.append(Paragraph(
        "<b>Question 5:</b> Tickets for a school play cost $5 for students and $8 for adults. "
        "There were 120 tickets sold for a total of $720. How many student tickets "
        "and how many adult tickets were sold? Define variables, write a system of "
        "equations (or one equation), solve, and answer in a full sentence.",
        question_style,
    ))
    story.append(Paragraph("Final answer: ________________________________", answer_style))

    doc.build(story)
    return output_path


if __name__ == "__main__":
    path = build_assignment()
    print(f"Created {path}")
