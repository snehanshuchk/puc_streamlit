import os
import re
import asyncio
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

# ================= CONFIG =================
NEWS_URL = "https://www.chemicalweekly.com/news"
RAW_HTML_FILE = "chemicalweekly_raw.html"
EXCEL_FILE = "chemicalweekly_last_7_days.xlsx"
FINAL_EXCEL_FILE = "chemicalweekly_last_7_days_with_content.xlsx"
HTML_DIR = "html_dump"
LINK_COLUMN = "LINK"
CONTENT_COLUMN = "CONTENT"
BASE_URL = "https://chemicalweekly.com"
# =========================================

os.makedirs(HTML_DIR, exist_ok=True)


# ---------- COMMON HELPERS ----------
def link_to_filename(link: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', link) + ".html"


def parse_date(date_str):
    return datetime.strptime(
        date_str.replace(" IST", ""),
        "%d %B, %Y %H:%M:%S"
    )


# ---------- STEP 1: Dump raw news HTML ----------
async def dump_raw_html():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = await browser.new_page()
        await page.goto(NEWS_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        await page.evaluate("""
            async () => {
                window.scrollTo(0, document.body.scrollHeight);
                await new Promise(r => setTimeout(r, 2000));
            }
        """)

        raw_html = await page.content()
        await browser.close()

    with open(RAW_HTML_FILE, "w", encoding="utf-8") as f:
        f.write(raw_html)

    print("✅ Step 1: Raw HTML dumped")


# ---------- STEP 2: Create Excel for last 7 days ----------
def create_excel_last_7_days():
    with open(RAW_HTML_FILE, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    cards = soup.select("#latest-news div.card > a")
    records = []

    for a in cards:
        h5 = a.find("h5")
        footer = a.find("p", class_="card-footer")
        link = a.get("href")

        if not (h5 and footer and link):
            continue

        if h5.find("svg", class_="bi-lock"):
            continue

        try:
            date_obj = parse_date(footer.get_text(strip=True))
        except Exception:
            continue

        if link.startswith("/"):
            link = BASE_URL + link

        records.append({
            "DATE_OBJ": date_obj,
            "DATE": date_obj.strftime("%d %B %Y"),
            "HEADING": h5.get_text(strip=True),
            "LINK": link,
            "CONTENT": ""
        })

    records.sort(key=lambda x: x["DATE_OBJ"], reverse=True)
    cutoff = records[0]["DATE_OBJ"] - timedelta(days=7)

    final = [r for r in records if r["DATE_OBJ"] >= cutoff]

    df = pd.DataFrame(final).drop(columns=["DATE_OBJ"])
    df.to_excel(EXCEL_FILE, index=False)

    print(f"✅ Step 2: Excel created ({len(df)} rows)")


# ---------- STEP 3: Save article HTMLs ----------
async def save_article_htmls():
    df = pd.read_excel(EXCEL_FILE)
    links = df[LINK_COLUMN].dropna().unique().tolist()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        for link in links:
            try:
                page = await context.new_page()
                print(f"Fetching article: {link}")
                await page.goto(link, wait_until="networkidle", timeout=60000)

                html = await page.content()
                path = os.path.join(HTML_DIR, link_to_filename(link))

                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)

                await page.close()
            except Exception as e:
                print(f"❌ Failed: {link} → {e}")

        await browser.close()

    print("✅ Step 3: Article HTML files saved")


# ---------- STEP 4: Extract og:description ----------
def extract_og_description(html_path):
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "lxml")

        tag = soup.find("meta", property="og:description")
        return tag["content"].strip() if tag else ""
    except Exception:
        return ""


def fill_excel_with_content():
    df = pd.read_excel(EXCEL_FILE)
    contents = []

    for link in df[LINK_COLUMN]:
        path = os.path.join(HTML_DIR, link_to_filename(link))
        contents.append(extract_og_description(path) if os.path.exists(path) else "")

    df[CONTENT_COLUMN] = contents
    df.to_excel(FINAL_EXCEL_FILE, index=False)

    print(f"✅ Step 4: Final Excel created → {FINAL_EXCEL_FILE}")


# ---------- MAIN PIPELINE ----------
async def main():
    await dump_raw_html()
    create_excel_last_7_days()
    await save_article_htmls()
    fill_excel_with_content()
    print("\n🎯 ALL STEPS COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    asyncio.run(main())
