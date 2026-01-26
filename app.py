import re
import asyncio
import base64
from datetime import datetime

import streamlit as st
from bs4 import BeautifulSoup
from serpapi.google_search import GoogleSearch
from playwright.async_api import async_playwright
from google import genai

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

# ===================== STREAMLIT CONFIG =====================
st.set_page_config(page_title="Market Intelligence", layout="wide")
st.title("📊 Market Intelligence Dashboard")

# ===================== API KEYS (REPLACE THESE) =====================
SERP_API_KEY = "3fb824092768ddbd78a7bdb8da513e6d63ce7dd19aa8337a616e5516d1f3331c"
GEMINI_API_KEY = "AIzaSyBb_0Opc3mUWkBkYpNVwKlk6UaF4nSLzYI"

client = genai.Client(api_key=GEMINI_API_KEY)

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
    text = re.sub(r"\.{2,}", ".", text)     # remove ...
    text = re.sub(r"\s+", " ", text).strip()

    sentences = re.split(r"(?<=[.!?])\s+", text)
    cleaned = []

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        s = s[0].upper() + s[1:]
        if not s.endswith("."):
            s += "."
        cleaned.append(s)

    return " ".join(cleaned)

# ===================== GEMINI =====================
def gemini_summarize(raw_text: str) -> str:
    if len(raw_text) < 200:
        return ""

    prompt = f"""
Role: Senior Market Intelligence Analyst.

Rules:
- Professional grammar.
- Sentences start with capital letters.
- Sentences end with a single period.
- No ellipses.

RAW NEWS:
{raw_text}
"""

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )

    return normalize_text(response.text)

# ===================== INDUSTRY NEWS =====================
async def fetch_industry_news():
    params = {
        "q": INDUSTRY_SEARCH_QUERY,
        "tbm": "nws",
        "tbs": "qdr:d7",
        "api_key": SERP_API_KEY,
        "num": 15
    }

    results = GoogleSearch(params).get_dict().get("news_results", [])
    snippets, sources = [], set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for r in results:
            page = await browser.new_page()
            try:
                await page.goto(r["link"], timeout=20000)
                soup = BeautifulSoup(await page.content(), "html.parser")
                meta = soup.find("meta", property="og:description")
                if meta:
                    snippets.append(meta["content"])
                    sources.add(r["link"])
            except:
                pass
            await page.close()
        await browser.close()

    return gemini_summarize(" ".join(snippets)), list(sources)[:5]

# ===================== COMPANY NEWS =====================
async def fetch_company_news():
    snippets, sources = [], set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for company in COMPETITORS:
            params = {
                "q": company,
                "tbm": "nws",
                "tbs": "qdr:d7",
                "api_key": SERP_API_KEY,
                "num": 5
            }

            results = GoogleSearch(params).get_dict().get("news_results", [])
            for r in results:
                page = await browser.new_page()
                try:
                    await page.goto(r["link"], timeout=20000)
                    soup = BeautifulSoup(await page.content(), "html.parser")
                    meta = soup.find("meta", property="og:description")
                    if meta:
                        snippets.append(f"{company}: {meta['content']}")
                        sources.add(r["link"])
                except:
                    pass
                await page.close()
        await browser.close()

    return gemini_summarize(" ".join(snippets)), list(sources)[:5]

# ===================== PDF =====================
def generate_pdf(industry, company, industry_sources, company_sources):
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

    for link in industry_sources + company_sources:
        story.append(Paragraph(f"<a href='{link}'>{link}</a>", styles["Italic"]))

    doc.build(story)
    return filename

# ===================== STREAMLIT UI =====================
if st.button("Generate Latest Report"):
    with st.spinner("Generating report..."):
        industry, ind_src = asyncio.run(fetch_industry_news())
        company, comp_src = asyncio.run(fetch_company_news())
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
