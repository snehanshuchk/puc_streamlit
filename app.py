import streamlit as st
import pandas as pd
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
import tempfile

# -----------------------------
# Summariser (CPU-safe)
# -----------------------------
def summarize_50_60_words(text):
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    sentences = summarizer(parser.document, 4)
    summary = " ".join(str(s) for s in sentences)
    return clean_summary(summary)

def clean_summary(text):
    text = text.strip()
    text = re.sub(r"\s*([.!?]+)\s*$", "", text)
    text = text[0].upper() + text[1:]
    return text + "."

# -----------------------------
# PDF Generator
# -----------------------------
def generate_pdf(df):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(tmp.name, pagesize=A4)

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Chemical Weekly – News Digest", styles["Title"]))

    for _, row in df.iterrows():
        story.append(Paragraph(row["HEADING"], styles["Heading2"]))
        story.append(Paragraph(str(row["DATE"]), styles["Normal"]))
        story.append(Paragraph(row["SUMMARY"], styles["Normal"]))

    doc.build(story)
    return tmp.name

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Chemical Weekly Newsletter", layout="wide")

st.title("📰 Chemical Weekly – AI Newsletter")

uploaded_file = st.file_uploader(
    "Upload Chemical Weekly Excel file",
    type=["xlsx"]
)

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    with st.spinner("Summarising news..."):
        df["SUMMARY"] = df["CONTENT"].apply(summarize_50_60_words)

    st.subheader("Newsletter Preview")

    for _, row in df.iterrows():
        st.markdown(f"### {row['HEADING']}")
        st.caption(row["DATE"])
        st.write(row["SUMMARY"])

    pdf_path = generate_pdf(df)

    with open(pdf_path, "rb") as f:
        st.download_button(
            "📄 Download Newsletter PDF",
            f,
            file_name="ChemicalWeekly_Newsletter.pdf"
        )
