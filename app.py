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
SERP_API_KEY = "14386fbcac3862b9e4a01e7b81d452c828740f448f09ca2f4c42995ed4e5bb6c"

INDUSTRY_SEARCH_QUERY = (
    "specialty chemicals OR non-ionic surfactants OR ethylene oxide "
    "OR green chemistry OR bio-based intermediates OR tariffs OR regulation OR supply chain"
)

# ===================== STREAMLIT =====================
st.set_page_config(page_title="Automated Weekly Insights", layout="centered")
st.title("📊 Automated Weekly Insights – Specialty Chemicals")

# ===================== MODEL (CACHED) =====================
@st.cache_resource
def load_model():
    return pipeline("summarization", model="facebook/bart-large-cnn")

summarizer = load_model()

# ===================== HELPERS =====================
def clean_text(text):
    text = text.replace("\n", " ").replace("?", "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+\S*$", "", text)
    return text.strip()

def summarize_text(text, max_len=130, min_len=50):
    if not text or len(text) < 50:
        return ""
    max_length = min(max_len, max(len(text) // 2, min_len))
    result = summarizer(
        text[:1024],
        max_length=max_length,
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

# ===================== SERPAPI (REST) =====================
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
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("news_results", [])

# ===================== INDUSTRY NEWS =====================
async def fetch_industry_news():
    results = serpapi_news_search(INDUSTRY_SEARCH_QUERY, num=15)

    snippets = []
    news_list = []
    source_links = set()

    for r in results:
        snippet = clean_text(r.get("snippet", ""))
        if snippet:
            snippets.append(snippet)
            news_list.append(
                {
                    "Headline": r.get("title", ""),
                    "Date": r.get("date", ""),
                    "URL": r.get("link", ""),
                    "Content": snippet,
                }
            )
            source_links.add(r.get("link", ""))

    unique_snippets = remove_similar(list(dict.fromkeys(snippets)))
    summary = summarize_text(" ".join(unique_snippets))
    return summary, news_list, list(source_links)[:5]

# ===================== COMPANY NEWS =====================
async def fetch_company_news(companies):
    summaries = {}
    source_links = set()

    for company in companies:
        results = serpapi_news_search(company, num=5)
        snippets = []

        for r in results:
            snippet = clean_text(r.get("snippet", ""))
            if snippet:
                snippets.append(snippet)
                source_links.add(r.get("link", ""))

        unique_snippets = remove_similar(list(dict.fromkeys(snippets)))
        combined = " ".join(unique_snippets)

        if combined:
            summaries[company] = summarize_text(combined)

    return summaries, list(source_links)[:5]

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
    story.append(Spacer(1, 15))

    story.append(Paragraph("Industry Intelligence – Specialty Chemicals", section))
    story.append(Spacer(1, 10))
    story.append(Paragraph(industry_summary or "No significant updates this week.", styles["BodyText"]))

    story.append(Spacer(1, 15))
    story.append(Paragraph("Company-Specific Highlights", section))

    for company, summary in company_summaries.items():
        story.append(Spacer(1, 8))
        story.append(Paragraph(company, styles["Heading3"]))
        story.append(Paragraph(summary, styles["BodyText"]))

    doc.build(story)
    return filename

# ===================== PIPELINE =====================
async def run_pipeline(companies):
    industry_summary, _, _ = await fetch_industry_news()
    company_summaries, _ = await fetch_company_news(companies)
    return generate_pdf(industry_summary, company_summaries)

# ===================== UI =====================
companies_input = st.text_area(
    "Enter company names (one per line)",
    "BASF\nDow\nClariant\nEvonik\nSolvay",
)

if st.button("🚀 Generate Weekly Report"):
    with st.spinner("Fetching news, summarizing & generating PDF..."):
        companies = [c.strip() for c in companies_input.split("\n") if c.strip()]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        pdf = loop.run_until_complete(run_pipeline(companies))

    st.success("✅ Report generated successfully")

    with open(pdf, "rb") as f:
        st.download_button(
            "📄 Download PDF",
            f,
            file_name=pdf,
            mime="application/pdf",
        )
