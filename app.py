import asyncio
import re
from datetime import datetime
from difflib import SequenceMatcher

import streamlit as st
import requests
from transformers import pipeline

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

# ===================== CONFIG =====================
SERP_API_KEY = "3fb824092768ddbd78a7bdb8da513e6d63ce7dd19aa8337a616e5516d1f3331c"

INDUSTRY_SEARCH_QUERY = (
    "specialty chemicals OR surfactants OR ethylene oxide OR green chemistry "
    "OR bio-based intermediates OR specialty materials OR chemical supply chain"
)

CHEM_KEYWORDS = [
    "chemical", "chemicals", "polymer", "resin", "surfactant",
    "battery", "additive", "coating", "specialty", "materials",
    "sustainability", "bio", "ethylene", "oxide", "pharma"
]

# ===================== STREAMLIT =====================
st.set_page_config(page_title="Automated Weekly Insights", layout="centered")
st.title("📊 Automated Weekly Insights – Specialty Chemicals")

# ===================== MODEL =====================
@st.cache_resource
def load_model():
    return pipeline("summarization", model="facebook/bart-large-cnn")

summarizer = load_model()

# ===================== TEXT HELPERS =====================
def clean_text(text):
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def normalize_sentences(text):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 40]
    return " ".join(sentences)

def summarize_text(text, max_len=140, min_len=60):
    if not text or len(text) < 100:
        return ""
    result = summarizer(
        text[:1024],
        max_length=max_len,
        min_length=min_len,
        do_sample=False,
    )
    return clean_text(result[0]["summary_text"])

def remove_similar(sentences, threshold=0.85):
    result = []
    for s in sentences:
        if all(SequenceMatcher(None, s, r).ratio() < threshold for r in result):
            result.append(s)
    return result

def is_relevant(text):
    t = text.lower()
    return any(k in t for k in CHEM_KEYWORDS)

# ===================== SERPAPI =====================
def serpapi_news_search(query, num=10):
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": query,
        "tbm": "nws",
        "tbs": "qdr:d7",
        "num": num,
        "api_key": SERP_API_KEY,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("news_results", [])

# ===================== INDUSTRY =====================
async def fetch_industry_news():
    results = serpapi_news_search(INDUSTRY_SEARCH_QUERY, 15)
    snippets = []

    for r in results:
        snippet = clean_text(r.get("snippet", ""))
        if snippet and is_relevant(snippet):
            snippets.append(snippet)

    snippets = remove_similar(snippets)
    combined = normalize_sentences(" ".join(snippets))
    summary = summarize_text(combined)

    if not summary:
        summary = (
            "No major industry-wide developments were reported in the specialty "
            "chemicals sector during the past week."
        )

    return summary

# ===================== COMPANY =====================
async def fetch_company_news(companies):
    summaries = {}

    for company in companies:
        results = serpapi_news_search(company, 5)
        snippets = []

        for r in results:
            snippet = clean_text(r.get("snippet", ""))
            if snippet and is_relevant(snippet):
                snippets.append(snippet)

        snippets = remove_similar(snippets)
        combined = normalize_sentences(" ".join(snippets))
        summary = summarize_text(combined)

        if not summary or len(summary.split()) < 40:
            summary = (
                "No material corporate developments were reported for this "
                "company during the past week."
            )

        summaries[company] = summary

    return summaries

# ===================== PDF =====================
def generate_pdf(industry_summary, company_summaries):
    filename = f"Weekly_Insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    doc = SimpleDocTemplate(filename, pagesize=LETTER)
    styles = getSampleStyleSheet()
    story = []

    title = ParagraphStyle("Title", fontSize=22, textColor=colors.navy)
    section = ParagraphStyle("Section", fontSize=16, textColor=colors.darkblue)

    story.append(Paragraph("Automated Weekly Insights", title))
    story.append(Spacer(1, 12))
    story.append(Paragraph(datetime.now().strftime("%B %d, %Y"), styles["BodyText"]))
    story.append(HRFlowable(width="100%"))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Industry Intelligence – Specialty Chemicals", section))
    story.append(Spacer(1, 10))
    story.append(Paragraph(industry_summary, styles["BodyText"]))

    story.append(Spacer(1, 18))
    story.append(Paragraph("Company-Specific Highlights", section))
    story.append(Spacer(1, 10))

    for company, summary in company_summaries.items():
        story.append(Paragraph(company, styles["Heading3"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(summary, styles["BodyText"]))
        story.append(Spacer(1, 12))

    doc.build(story)
    return filename

# ===================== PIPELINE =====================
async def run_pipeline(companies):
    industry_summary = await fetch_industry_news()
    company_summaries = await fetch_company_news(companies)
    pdf_file = generate_pdf(industry_summary, company_summaries)
    return industry_summary, company_summaries, pdf_file

# ===================== UI =====================
companies_input = st.text_area(
    "Enter company names (one per line)",
    "BASF\nDow\nClariant\nEvonik\nSolvay",
)

if st.button("🚀 Generate Weekly Report"):
    with st.spinner("Generating clean, formatted report..."):
        companies = [c.strip() for c in companies_input.split("\n") if c.strip()]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        industry_summary, company_summaries, pdf = loop.run_until_complete(
            run_pipeline(companies)
        )

    # ===== DISPLAY ON SITE =====
    st.success("✅ Report generated")

    st.header("Industry Intelligence – Specialty Chemicals")
    st.write(industry_summary)

    st.header("Company-Specific Highlights")
    for company, summary in company_summaries.items():
        st.subheader(company)
        st.write(summary)

    # ===== DOWNLOAD =====
    with open(pdf, "rb") as f:
        st.download_button(
            "📄 Download PDF",
            f,
            file_name=pdf,
            mime="application/pdf",
        )
