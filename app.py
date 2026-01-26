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
    filename = f"Market_Intelligence_Report_{datetime.now()._
