import re
import base64
from datetime import datetime

import streamlit as st
import requests
import google.generativeai as genai

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

# ===================== STREAMLIT CONFIG =====================
st.set_page_config(page_title="Market Intelligence", layout="wide")
st.title("📊 Market Intelligence Dashboard")

# ===================== API KEYS (REPLACE WITH YOUR REAL KEYS) =====================
SERP_API_KEY = "YOUR_REAL_SERPAPI_KEY_HERE"
GEMINI_API_KEY = "YOUR_REAL_GEMINI_API_KEY_HERE"

# ===================== GEMINI CONFIG =====================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ===================== CONSTANTS =====================
COMPETITORS = [
    "BASF",
    "Dow",
    "Stepan Company",
    "Croda International",
    "Clariant"
]

INDUSTRY_SEARCH_QUERY = (
    "specialty chemicals OR non-ionic surfactants OR ethylene oxide "
    "OR green chemistry OR bio-based intermediates OR regulation OR supply chain"
)

# ===================== TEXT NORMALIZATION =====================
def normalize_text(text: str) -> str:
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+", " ", text).strip()

    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = []

    for s in sentences:
        if not s:
            continue
        s = s[0].upper() + s[1:]
        if not s.endswith("."):
            s += "."
        out.append(s)

    return " ".join(out)

# ===================== SERPAPI =====================
def fetch_news(query, num=10):
    params = {
        "engine": "google_news",
        "q": query,
        "api_key": SERP_API_KEY,
        "num": num
    }
    r = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("news_results", [])

# ===================== GEMINI =====================
def gemini_summarize(text: str) -> str:
    if len(text) < 200:
        return ""

    prompt = f"""
Role: Senior Market Intelligence Analyst.

Rules:
- Professional grammar.
- Capitalized sentence starts.
- Single period at sentence end.
- No ellipses.

RAW NEWS:
{text}
"""

    response = model.generate_content(prompt)
    return normalize_text(response.text)

# ===================== INDUSTRY =====================
def get_industry_news():
    results = fetch_news(INDUSTRY_SEARCH_QUERY, 15)
    snippets, links = [], []

    for r in results:
        if "snippet" in r:
            snippets.append(r["snippet"])
        if "link" in r:
            links.append(r["link"])

    return gemini_summarize(" ".join(snippets)), links[:5]

# ===================== COMPANIES =====================
def get_company_news():
    snippets, links = [], []

    for company in COMPETITORS:
        results = fetch_news(company, 5)
        for r in results:
            if "snippet" in r:
                snippets.append(f"{company}: {r['snippet']}")
            if "link" in r:
                links.append(r["link"])

    return gemini_summarize(" ".join(snippets)), links[:5]

# ===================== PDF =====================
def generate_pdf(industry, company, src1, src2):
    filename = f"Market_Intelligence_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=LETTER)

    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", fontSize=22, textColor=colors.darkblue)
    section = ParagraphStyle("section", fontSize=16, textColor=colors.navy)
    body = ParagraphStyle("body", fontSize=11, leading=16)

    story = [
        Paragraph("Market Intelligence Report", title),
        Spacer(1, 12),
        Paragraph(datetime.now().strftime("%B %d, %Y"), styles["Normal"]),
        HRFlowable(width="100%"),
        Spacer(1, 20),

        Paragraph("Industry Intelligence", section),
        Spacer(1, 10),
        Paragraph(industry, body),
        Spacer(1, 20),

        Paragraph("Competitive Landscape Impact", section),
        Spacer(1, 10),
        Paragraph(company, body),
        Spacer(1, 20),

        Paragraph("Source Links", section)
    ]

    for link in src1 + src2:
        story.append(Paragraph(f"<a href='{link}'>{link}</a>", styles["Italic"]))

    doc.build(story)
    return filename

# ===================== UI =====================
if st.button("Generate Latest Report"):
    with st.spinner("Generating report..."):
        industry, ind_src = get_industry_news()
        company, comp_src = get_company_news()
        pdf_path = generate_pdf(industry, company, ind_src, comp_src)

    st.header("Industry Intelligence")
    st.write(industry)

    st.header("Competitive Landscape Impact")
    st.write(company)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
        b64 = base64.b64encode(pdf_bytes).decode()

    st.markdown(
        f"<iframe src='data:application/pdf;base64,{b64}' width='100%' height='600'></iframe>",
        unsafe_allow_html=True
    )

    st.download_button(
        "⬇️ Download PDF",
        pdf_bytes,
        file_name=pdf_path,
        mime="application/pdf"
    )
