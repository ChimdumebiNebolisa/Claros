"""
Generate test_assignment.pdf with the Claros test assignment content using reportlab.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

PDF_FILENAME = "test_assignment.pdf"


def build_assignment():
    doc = SimpleDocTemplate(
        PDF_FILENAME,
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
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        name="Subtitle",
        parent=styles["Normal"],
        fontSize=14,
        spaceAfter=24,
    )
    question_style = ParagraphStyle(
        name="Question",
        parent=styles["Normal"],
        fontSize=12,
        spaceBefore=20,
        spaceAfter=8,
    )

    story = []

    story.append(Paragraph("Claros Test Assignment", title_style))
    story.append(Paragraph("Algebra — Grade 9/10", subtitle_style))

    story.append(Paragraph(
        "<b>Question 1:</b> Solve for x: 3x + 7 = 22",
        question_style,
    ))

    story.append(Paragraph(
        "<b>Question 2:</b> Solve for x: 2(x - 4) = 10",
        question_style,
    ))

    story.append(Paragraph(
        "<b>Question 3:</b> Solve for x and verify your answer: 4x - 3 = 2x + 9",
        question_style,
    ))

    story.append(Paragraph(
        "<b>Question 4:</b> A school store sells notebooks for $3 each and pens for $1.50 each. "
        "Maria spent $18 buying a combination of notebooks and pens. If she bought 4 notebooks, "
        "how many pens did she buy? Show your work.",
        question_style,
    ))

    story.append(Paragraph(
        "<b>Question 5:</b> A train leaves Station A traveling at 60 mph. Two hours later, "
        "a second train leaves the same station traveling in the same direction at 90 mph. "
        "How many hours after the second train departs will it catch up to the first train? "
        "Set up and solve an equation to find your answer.",
        question_style,
    ))

    doc.build(story)
    print(f"Created {PDF_FILENAME}")


if __name__ == "__main__":
    build_assignment()
