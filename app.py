import re
from datetime import datetime, timedelta

import streamlit as st
from serpapi import GoogleSearch
import google.generativeai as genai

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable


# ===================== CONFIG =====================

SERP_API_KEY = st.secrets["SERP_API_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)

COMPETITORS = [
    "BASF",
    "Dow Chemical",
    "Croda International",
    "Clariant",
    "Evonik Industries",
    "Stepan Company"
]

INDUSTRY_SEARCH_QUERY = (
    "ethylene oxide OR non-ionic surfactants OR specialty chemicals "
    "OR green chemistry OR feedstock OR regulation OR sustainability"
)

CATEGORIES = [
    "Upstream & Feedstock Intelligence (Ethylene & Derivatives)",
    "Market Dynamics & Demand Forecasting",
    "Sustainability & Regulatory Intelligence",
    "Operational & Competitive Intelligence",
    "Innovation & Formulation Platforms",
    "Merger and Acquisition",
    "Latest Published Quarterly Results (Customers & Competitors)"
]


# ===================== UTIL =====================

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


# ===================== GEMINI =====================

def gemini_summarize(raw_text, mode="industry"):
    if len(raw_text) < 200:
        return ""

    allowed = (
        CATEGORIES[:5]
        if mode == "industry"
        else [
            "Operational & Competitive Intelligence",
            "Latest Published Quarterly Results (Customers & Competitors)"
        ]
    )

    prompt = f"""
Role: Senior Market Intelligence Analyst for the Specialty Chemicals industry.

Objective:
Identify the top 5–7 most impactful news stories from the past 7 days relevant to Indovinya.
EXCLUDE any Indorama or Indovinya related news.

High-Level Intelligence Categories:
{", ".join(allowed)}

STRICT OUTPUT FORMAT:
NEWS_1
CATEGORY:
TITLE:
SOURCE:
SUMMARY:
IMPACT:

RAW NEWS:
{raw_text}
"""

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)

    return response.text.strip()


# ===================== PARSER =====================

def parse_news_blocks(text):
    blocks = re.split(r"NEWS_\d+", text)
    items = []

    for block in blocks:
        data = dict(category="", title="", source="", summary="", impact="")
        for line in block.split("\n"):
            for key in data:
                if line.startswith(key.upper() + ":"):
                    data[key] = line.split(":", 1)[1].strip()
        if data["title"]:
            items.append(data)

    return items


# ===================== SERPAPI =====================

@st.cache_data(ttl=3600)
def fetch_serp_news(query, num=10):
    params = {
        "q": query,
        "tbm": "nws",
        "tbs": "qdr:d7",
        "api_key": SERP_API_KEY,
        "num": num
    }

    search = GoogleSearch(params)
    results = search.get_dict().get("news_results", [])

    snippets, sources = [], set()
    for r in results:
        if r.get("snippet"):
            snippets.append(r["snippet"])
        if r.get("link"):
            sources.add(r["link"])

    return clean_text(" ".join(snippets)), list(sources)


def fetch_industry_news():
    raw, sources = fetch_serp_news(INDUSTRY_SEARCH_QUERY, 15)
    return gemini_summarize(raw, "industry"), sources


def fetch_company_news():
    all_snippets, all_sources = [], set()
    for company in COMPETITORS:
        raw, sources = fetch_serp_news(company, 5)
        all_snippets.append(f"{company}: {raw}")
        all_sources.update(sources)

    combined = clean_text(" ".join(all_snippets))
    return gemini_summarize(combined, "company"), list(all_sources)


# ===================== PDF =====================

def generate_pdf(industry_summary, company_summary, industry_sources, company_sources):
    filename = f"Weekly_Strategic_Intelligence_{datetime.now():%Y%m%d}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=LETTER)

    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", fontSize=20, spaceAfter=16)
    section = ParagraphStyle("section", fontSize=15, spaceBefore=18)
    category = ParagraphStyle("category", fontSize=13, textColor=colors.darkblue)
    body = ParagraphStyle("body", fontSize=11, leading=15)

    story = []

    end = datetime.now()
    start = end - timedelta(days=7)

    story.extend([
        Paragraph("WEEKLY STRATEGIC INTELLIGENCE REPORT", title),
        Paragraph(f"Reporting Period: {start:%d %B %Y} – {end:%d %B %Y}", body),
        HRFlowable(width="100%"),
        Spacer(1, 20)
    ])

    story.append(Paragraph("1. INDUSTRY INTELLIGENCE", section))
    for item in parse_news_blocks(industry_summary):
        story.append(Paragraph(item["category"], category))
        story.append(Paragraph(item["title"], body))
        story.append(Paragraph(item["summary"], body))
        story.append(Paragraph(item["impact"], body))
        story.append(Spacer(1, 12))

    story.append(Paragraph("2. COMPETITIVE LANDSCAPE", section))
    for item in parse_news_blocks(company_summary):
        story.append(Paragraph(item["category"], category))
        story.append(Paragraph(item["title"], body))
        story.append(Paragraph(item["summary"], body))
        story.append(Paragraph(item["impact"], body))
        story.append(Spacer(1, 12))

    story.append(Paragraph("Source Links", section))
    for link in sorted(set(industry_sources + company_sources)):
        story.append(Paragraph(link, styles["Italic"]))

    doc.build(story)
    return filename


# ===================== STREAMLIT UI =====================

st.set_page_config(page_title="Strategic Intelligence", layout="wide")

st.title("📊 Weekly Strategic Intelligence Report")
st.caption("Specialty Chemicals | EO | Surfactants")

if st.button("🚀 Generate Report"):
    with st.spinner("Collecting news, analyzing with Gemini, generating PDF..."):
        industry, i_src = fetch_industry_news()
        company, c_src = fetch_company_news()
        pdf = generate_pdf(industry, company, i_src, c_src)

    with open(pdf, "rb") as f:
        st.download_button(
            "⬇️ Download PDF",
            f,
            file_name=pdf,
            mime="application/pdf"
        )

    st.success("Report generated successfully!")
