import feedparser
import requests
from bs4 import BeautifulSoup
from xml.dom.minidom import Document
from email.utils import formatdate

# All feeds
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

# REQUIRED archive prefix you provided
ARCHIVE_PREFIX = "https://archive.is/o/nuunc/"

# Optional headers (helps avoid being rate-limited)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_full_html(url: str) -> str:
    """
    Fetch article HTML from the live Economist page (fast),
    and return the <article> HTML as a string. No timeout per your request.
    """
    try:
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        article = soup.find("article")
        if article:
            return str(article)
    except Exception as e:
        print(f"Could not fetch full text for {url}: {e}")
    return "Full text not available."

def text_node(doc: Document, name: str, value: str):
    el = doc.createElement(name)
    el.appendChild(doc.createTextNode(value))
    return el

def build_combined_feed(items):
    """
    Build an RSS 2.0 feed with content:encoded holding full HTML.
    Links point to archive.is/o/nuunc/<original>.
    """
    doc = Document()

    rss = doc.createElement("rss")
    rss.setAttribute("version", "2.0")
    rss.setAttribute("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    doc.appendChild(rss)

    channel = doc.createElement("channel")
    rss.appendChild(channel)

    channel.appendChild(text_node(doc, "title", "Combined Economist RSS (Archive links, Full Text)"))
    channel.appendChild(text_node(doc, "link", "https://github.com/evilgodfahim/eco"))
    channel.appendChild(text_node(doc, "description", "Merged feed with archive.is links and full article text"))

    for it in items:
        item = doc.createElement("item")
        channel.appendChild(item)

        item.appendChild(text_node(doc, "title", it.get("title", "Untitled")))
        # IMPORTANT: use your archive prefix for the public link
        item.appendChild(text_node(doc, "link", ARCHIVE_PREFIX + it["orig_link"]))
        item.appendChild(text_node(doc, "guid", it["orig_link"]))
        item.appendChild(text_node(doc, "pubDate", it.get("pubDate", formatdate(usegmt=True))))

        # description (optional short)
        short = it.get("summary", "")
        item.appendChild(text_node(doc, "description", short))

        # full HTML in content:encoded (CDATA)
        content_el = doc.createElement("content:encoded")
        cdata = doc.createCDATASection(it.get("full_html", "Full text not available."))
        content_el.appendChild(cdata)
        item.appendChild(content_el)

    return doc

def main():
    combined = []

    for feed_url in RSS_URLS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            orig_link = getattr(entry, "link", None)
            if not orig_link:
                continue

            full_html = fetch_full_html(orig_link)

            pubdate = getattr(entry, "published", None) or getattr(entry, "updated", None)
            pubdate = pubdate if pubdate else formatdate(usegmt=True)

            summary = getattr(entry, "summary", "")

            combined.append({
                "title": getattr(entry, "title", "Untitled"),
                "orig_link": orig_link,
                "pubDate": pubdate,
                "summary": summary,
                "full_html": full_html,
            })

    doc = build_combined_feed(combined)
    # Write as UTF-8 without extra escaping (CDATA keeps HTML intact)
    xml_bytes = doc.toxml(encoding="utf-8")
    with open("combined.xml", "wb") as f:
        f.write(xml_bytes)
    print("✅ combined.xml generated (archive links + full text).")

if __name__ == "__main__":
    main()
