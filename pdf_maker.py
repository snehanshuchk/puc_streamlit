import re
import pandas as pd
from transformers import pipeline
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor

# --------------------------------------------------
# Load FREE open-source LLM (CPU, no API, no cost)
# --------------------------------------------------
summarizer = pipeline(
    "summarization",
    model="t5-small",
    tokenizer="t5-small"
)

# --------------------------------------------------
# Clean + enforce editorial formatting
# --------------------------------------------------
def clean_summary(text: str) -> str:
    text = text.strip()

    # Remove trailing punctuation and spaces
    text = re.sub(r"\s*([.!?]+)\s*$", "", text)

    # Capitalise first letter
    if text:
        text = text[0].upper() + text[1:]

    # Add exactly one full stop
    return text + "."

# --------------------------------------------------
# LLM-based 50–60 word summariser
# --------------------------------------------------
def summarize_50_60_words(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()

    result = summarizer(
        text,
        min_length=90,   # ≈ 50 words
        max_length=120,  # ≈ 60 words
        do_sample=False
    )[0]["summary_text"]

    return clean_summary(result)

# --------------------------------------------------
# Load Excel data
# --------------------------------------------------
df = pd.read_excel("chemicalweekly_last_7_days_with_content.xlsx")

# --------------------------------------------------
# Create PDF
# --------------------------------------------------
output_pdf = "ChemicalWeekly_Newsletter_LLM_Summary.pdf"

doc = SimpleDocTemplate(
    output_pdf,
    pagesize=A4,
    leftMargin=36,
    rightMargin=36,
    topMargin=20,
    bottomMargin=36
)

styles = getSampleStyleSheet()

header_style = ParagraphStyle(
    "Header",
    parent=styles["Title"],
    textColor=HexColor("#1f3c88"),
    spaceAfter=6
)

sub_style = ParagraphStyle(
    "Sub",
    parent=styles["Normal"],
    fontSize=10,
    textColor=HexColor("#444444"),
    spaceAfter=12
)

title_style = ParagraphStyle(
    "Title",
    parent=styles["Heading2"],
    textColor=HexColor("#1f3c88"),
    spaceAfter=2
)

date_style = ParagraphStyle(
    "Date",
    parent=styles["Normal"],
    fontSize=9,
    textColor=HexColor("#777777"),
    spaceAfter=4
)

summary_style = ParagraphStyle(
    "Summary",
    parent=styles["Normal"],
    fontSize=11,
    leading=15,
    spaceAfter=14
)

story = []

# Header
story.append(Paragraph("Indorama Ventures - News Digest", header_style))
story.append(
    Paragraph(
        "Weekly Lastest News",
        sub_style
    )
)

# Articles
for _, row in df.iterrows():
    story.append(Paragraph(row["HEADING"], title_style))
    story.append(Paragraph(str(row["DATE"]), date_style))
    story.append(
        Paragraph(
            summarize_50_60_words(row["CONTENT"]),
            summary_style
        )
    )

doc.build(story)

print("Newsletter PDF generated successfully:", output_pdf)
