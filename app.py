import os
import re
import asyncio
from datetime import datetime
from difflib import SequenceMatcher

import streamlit as st
from bs4 import BeautifulSoup
from serpapi import GoogleSearch
from playwright.async_api import async_playwright
from transformers import pipeline

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

# ===================== CONFIG =====================
SERP_API_KEY = "3fb824092768ddbd78a7bdb8da513e6d63ce7dd19aa8337a616e5516d1f3331c"

INDUSTRY_SEARCH_QUERY = (
    "specialty chemicals OR non-ionic surfactants OR ethylene oxide "
    "OR green chemistry OR bio-based intermediates OR tariffs OR regulation OR supply chain"
)

# ===================== STREAMLIT SETUP =====================
st.set_page_config(page_title="Automated Weekly Insights", layout="centered")
st.title("📊 Automated Weekly Insights – Specialty Chemicals")

# ===================== LOAD MODEL (CACHED) =====================
@st.cache_resource
def load_model():
    return pipeline("summarization", model="facebook/bart-large-cnn")

summarizer = load_model()

# ===================== HELPERS =====================
def clean_text(text):
    text = text.replace("\n", " ").replace("?", "").replace("  ", " ")
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

# ===================== INDUSTRY NEWS =====================
async def fetch_industry_news():
    params = {
        "q": INDUSTRY_SEARCH_QUERY,
        "tbm": "nws",
        "tbs": "qdr:d7",
        "api_key": SERP_API_KEY,
        "num": 15,
    }

    search = GoogleSearch(params)
    results = search.get_dict().get("news_results", [])

    snippets, news_list, source_links = [], [], set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for r in results:
            page = await browser.new_page()
            try:
                await page.goto(r["link"], wait_until="domcontentloaded", timeout=20000)
                soup = BeautifulSoup(await page.content(), "html.parser")
                tag = soup.find("meta", property="og:description")
                snippet = clean_text(tag["content"]) if tag else ""
            except:
                snippet = ""

            await page.close()

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

        await browser.close()

    unique_snippets = remove_similar(list(dict.fromkeys(snippets)))
    summary = summarize_text(" ".join(unique_snippets))
    return summary, news_list, list(source_links)[:5]

# ===================== COMPANY NEWS =====================
async def fetch_company_news(companies):
    summaries, all_news, source_links = {}, [], set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for company in companies:
            params = {
                "q": company,
                "tbm": "nws",
                "tbs": "qdr:d7",
                "api_key": SERP_API_KEY,
                "num": 5,
            }

            search = GoogleSearch(params)
            results = search.get_dict().get("news_results", [])
            snippets = []

            for r in results:
                page = await browser.new_page()
                try:
                    await page.goto(r["link"], wait_until="domcontentloaded", timeout=20000)
                    soup = BeautifulSoup(await page.content(), "html.parser")
                    tag = soup.find("meta", property="og:description")
                    snippet = clean_text(tag["content"]) if tag else ""
                except:
                    snippet = ""

                await page.close()

                if snippet:
                    snippets.append(snippet)
                    source_links.add(r["link"])

            unique_snippets = remove_similar(list(dict.fromkeys(snippets)))
            combined = " ".join(unique_snippets)

            if combined:
                summaries[company] = summarize_text(combined)

        await browser.close()

    return summaries, all_news, list(source_links)[:5]

# ===================== PDF =====================
def generate_pdf(industry_summary, industry_news, company_summaries, industry_sources, company_sources):
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
    story.append(Paragraph(industry_summary, styles["BodyText"]))

    story.append(Spacer(1, 15))
    story.append(Paragraph("Company Highlights", section))

    for company, summary in company_summaries.items():
        story.append(Spacer(1, 8))
        story.append(Paragraph(company, styles["Heading3"]))
        story.append(Paragraph(summary, styles["BodyText"]))

    doc.build(story)
    return filename

# ===================== PIPELINE =====================
async def run_pipeline(companies):
    industry_summary, industry_news, industry_sources = await fetch_industry_news()
    company_summaries, _, company_sources = await fetch_company_news(companies)

    return generate_pdf(
        industry_summary,
        industry_news,
        company_summaries,
        industry_sources,
        company_sources,
    )

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

    st.success("✅ Report generated")

    with open(pdf, "rb") as f:
        st.download_button(
            "📄 Download PDF",
            f,
            file_name=pdf,
            mime="application/pdf",
        )
