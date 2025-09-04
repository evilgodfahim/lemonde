#!/usr/bin/env python3
# combine_rss.py
# Combine multiple Economist RSS feeds with archive.is links and full text from archive snapshots

import feedparser
import requests
from bs4 import BeautifulSoup
from xml.dom.minidom import Document
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import time
import email.utils

# === Configuration ===
RSS_URLS = [
    "https://www.economist.com/briefing/rss.xml",
    "https://www.economist.com/the-economist-explains/rss.xml",
    "https://www.economist.com/leaders/rss.xml",
    "https://www.economist.com/asia/rss.xml",
    "https://www.economist.com/china/rss.xml",
    "https://www.economist.com/international/rss.xml",
    "https://www.economist.com/united-states/rss.xml",
    "https://www.economist.com/finance-and-economics/rss.xml",
    "https://www.economist.com/the-world-this-week/rss.xml",
]

ARCHIVE_PREFIX = "https://archive.is/o/nuunc/"   # your required prefix
OUTPUT_FILE = "combined.xml"
MAX_ITEMS = 20
MAX_WORKERS = 6
RETRY_COUNT = 2
REQUEST_TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CombinedRSS/1.0; +https://github.com/)"
}

# === helpers ===
def parse_entry_datetime(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        ts = time.mktime(entry.published_parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        ts = time.mktime(entry.updated_parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.now(tz=timezone.utc)

def format_rfc2822(dt):
    try:
        return email.utils.format_datetime(dt)
    except Exception:
        return email.utils.formatdate(dt.timestamp(), usegmt=True)

def fetch_archive_full_html(archive_url):
    """
    Follow the archive.is redirect (o/nuunc) to the actual snapshot,
    then fetch and extract the main content.
    """
    last_exc = None
    for attempt in range(RETRY_COUNT):
        try:
            # follow redirects to reach snapshot
            r = requests.get(archive_url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, "html.parser")

            # main <article> first
            article = soup.find("article")
            if article and article.get_text(strip=True):
                return str(article)

            # fallback divs or body
            possible = soup.find("div", id=lambda x: x and "content" in x.lower()) or soup.find("body")
            if possible:
                return str(possible)

            return r.text
        except Exception as e:
            last_exc = e
            time.sleep(2)
    return f"<!-- Failed to fetch archive content ({archive_url}): {last_exc} -->Full text not available."

def text_node(doc, name, text):
    el = doc.createElement(name)
    el.appendChild(doc.createTextNode(text))
    return el

# === collect entries from feeds ===
all_entries = []
for feed_url in RSS_URLS:
    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        print(f"Failed to parse feed {feed_url}: {e}")
        continue
    for entry in feed.entries:
        link = getattr(entry, "link", None)
        if not link:
            continue
        dt = parse_entry_datetime(entry)
        all_entries.append({
            "title": getattr(entry, "title", "Untitled"),
            "orig_link": link,
            "archive_link": ARCHIVE_PREFIX + link,
            "summary": getattr(entry, "summary", "") or getattr(entry, "description", ""),
            "published_dt": dt,
        })

# newest 20 items
all_entries.sort(key=lambda x: x["published_dt"], reverse=True)
selected = all_entries[:MAX_ITEMS]

# fetch full HTML in parallel
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    future_map = {ex.submit(fetch_archive_full_html, it["archive_link"]): it for it in selected}
    for future in as_completed(future_map):
        it = future_map[future]
        try:
            full_html = future.result()
        except Exception as e:
            full_html = f"<!-- fetch error: {e} -->Full text not available."
        it["full_html"] = full_html

# === build RSS feed ===
doc = Document()
rss = doc.createElement("rss")
rss.setAttribute("version", "2.0")
rss.setAttribute("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
doc.appendChild(rss)

channel = doc.createElement("channel")
rss.appendChild(channel)
channel.appendChild(text_node(doc, "title", "Combined Economist RSS (archive.is links, newest 20)"))
channel.appendChild(text_node(doc, "link", "https://github.com/"))
channel.appendChild(text_node(doc, "description", "Combined feed — links point to archive.is/o/nuunc/, full text from archive snapshots"))

for it in selected:
    item_el = doc.createElement("item")
    channel.appendChild(item_el)

    item_el.appendChild(text_node(doc, "title", it.get("title", "Untitled")))
    item_el.appendChild(text_node(doc, "link", it["archive_link"]))
    item_el.appendChild(text_node(doc, "guid", it["orig_link"]))
    item_el.appendChild(text_node(doc, "description", it.get("summary", "")))
    item_el.appendChild(text_node(doc, "pubDate", format_rfc2822(it["published_dt"])))

    content_el = doc.createElement("content:encoded")
    cdata = doc.createCDATASection(it.get("full_html", "Full text not available."))
    content_el.appendChild(cdata)
    item_el.appendChild(content_el)

# write to file
with open(OUTPUT_FILE, "wb") as f:
    f.write(doc.toxml(encoding="utf-8"))

print(f"✅ combined.xml generated with {len(selected)} newest items (archive.is links + full text).")
