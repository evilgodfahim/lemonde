#!/usr/bin/env python3
# combine_rss.py
# Combines multiple Economist RSS feeds, uses archive.is/o/nuunc/<original-url> as link,
# fetches full text from that archive URL, keeps newest 20 items, writes combined.xml.

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
MAX_WORKERS = 6       # parallel fetchers for archive pages
RETRY_COUNT = 2       # retry archive fetch attempts
REQUEST_TIMEOUT = 30  # seconds per request (keeps Actions from blocking forever)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CombinedRSS/1.0; +https://github.com/)"
}

# === helpers ===
def parse_entry_datetime(entry):
    """Return a timezone-aware datetime for sorting."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        ts = time.mktime(entry.published_parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        ts = time.mktime(entry.updated_parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.now(tz=timezone.utc)

def format_rfc2822(dt):
    """Return RFC-2822 formatted date string for pubDate."""
    try:
        return email.utils.format_datetime(dt)
    except Exception:
        return email.utils.formatdate(dt.timestamp(), usegmt=True)

def fetch_archive_full_html(archive_url):
    """
    Fetch the archive URL and attempt to extract the main content.
    Retries on transient errors.
    """
    last_exc = None
    for attempt in range(RETRY_COUNT):
        try:
            r = requests.get(archive_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            # Try to find a main <article> first
            article = soup.find("article")
            if article and article.get_text(strip=True):
                return str(article)

            # Some archive pages embed the snapshot inside an iframe or a div.
            # Try some fallbacks:
            # 1) iframe
            iframe = soup.find("iframe")
            if iframe and iframe.has_attr("src"):
                # attempt to fetch iframe src (may be relative)
                iframe_src = iframe["src"]
                if iframe_src.startswith("//"):
                    iframe_src = "https:" + iframe_src
                elif iframe_src.startswith("/"):
                    # build full url from archive_url
                    from urllib.parse import urljoin
                    iframe_src = urljoin(archive_url, iframe_src)
                try:
                    r2 = requests.get(iframe_src, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                    r2.raise_for_status()
                    soup2 = BeautifulSoup(r2.text, "html.parser")
                    a2 = soup2.find("article") or soup2.find("div", {"id": "content"}) or soup2.find("body")
                    if a2:
                        return str(a2)
                except Exception:
                    pass

            # 2) div that looks like a snapshot container
            possible = soup.find(lambda tag: tag.name == "div" and tag.get("id") and "snapshot" in tag.get("id").lower())
            if possible and possible.get_text(strip=True):
                return str(possible)

            # 3) fallback to body
            body = soup.find("body")
            if body:
                return str(body)

            # final fallback: raw HTML
            return r.text
        except Exception as e:
            last_exc = e
            time.sleep(2)  # short wait before retry
    # if all retries failed:
    return f"<!-- Failed to fetch archive content ({archive_url}): {last_exc} -->Full text not available."

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

# sort by published date descending and keep newest MAX_ITEMS
all_entries.sort(key=lambda x: x["published_dt"], reverse=True)
selected = all_entries[:MAX_ITEMS]

# === fetch archive pages in parallel ===
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    future_map = {}
    for item in selected:
        future = ex.submit(fetch_archive_full_html, item["archive_link"])
        future_map[future] = item

    for future in as_completed(future_map):
        item = future_map[future]
        try:
            full_html = future.result()
        except Exception as e:
            full_html = f"<!-- fetch error: {e} -->Full text not available."
        item["full_html"] = full_html

# === build RSS using minidom so we can include CDATA for full HTML ===
doc = Document()
rss = doc.createElement("rss")
rss.setAttribute("version", "2.0")
rss.setAttribute("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
doc.appendChild(rss)

channel = doc.createElement("channel")
rss.appendChild(channel)

def text_node(name, text):
    el = doc.createElement(name)
    el.appendChild(doc.createTextNode(text))
    return el

channel.appendChild(text_node("title", "Combined Economist RSS (archive.is links, newest 20)"))
channel.appendChild(text_node("link", "https://github.com/"))
channel.appendChild(text_node("description", "Combined feed — links point to archive.is/o/nuunc/..., full text fetched from archive pages"))

for it in selected:
    item_el = doc.createElement("item")
    channel.appendChild(item_el)

    item_el.appendChild(text_node("title", it.get("title", "Untitled")))
    # link must be archive prefix + original link (as you requested)
    item_el.appendChild(text_node("link", it["archive_link"]))
    item_el.appendChild(text_node("guid", it["orig_link"]))
    item_el.appendChild(text_node("description", it.get("summary", "")))
    pubdate = format_rfc2822(it["published_dt"])
    item_el.appendChild(text_node("pubDate", pubdate))

    content_el = doc.createElement("content:encoded")
    cdata = doc.createCDATASection(it.get("full_html", "Full text not available."))
    content_el.appendChild(cdata)
    item_el.appendChild(content_el)

# write to file
xml_bytes = doc.toxml(encoding="utf-8")
with open(OUTPUT_FILE, "wb") as f:
    f.write(xml_bytes)

print(f"Done — {len(selected)} items written to {OUTPUT_FILE}")
