import feedparser
import xml.etree.ElementTree as ET
from datetime import datetime

# RSS feed URLs
rss_feeds = [
    "https://politepol.com/fd/vn35US5klYN5.xml",
    "https://politepol.com/fd/g7gQ1jJspFpv.xml"
]

ARCHIVE_PREFIX = "https://archive.is/o/94ovq/"

def fetch_items(feed_urls):
    all_items = []
    seen_links = set()  # to track duplicates by link

    for feed_url in feed_urls:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            # skip if no link at all
            if not hasattr(entry, "link") or not entry.link.strip():
                continue

            original_link = entry.link.strip()

            # only skip if we already added one with this link
            if original_link in seen_links:
                continue

            seen_links.add(original_link)

            archive_link = ARCHIVE_PREFIX + original_link

            all_items.append({
                "title": entry.get("title", "No title"),
                "link": archive_link,
                "description": entry.get("description", ""),
                "pubDate": entry.get("published", datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000"))
            })

    # Ensure at least one inclusion per unique article
    return all_items

def create_rss(items):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Combined Le Monde RSS Feed"
    ET.SubElement(channel, "link").text = "https://yourusername.github.io/combined.xml"
    ET.SubElement(channel, "description").text = "Combined feed of multiple sources with archive.is/o/94ovq links"

    for item in items:
        i = ET.SubElement(channel, "item")
        ET.SubElement(i, "title").text = item["title"]
        ET.SubElement(i, "link").text = item["link"]
        ET.SubElement(i, "description").text = item["description"]
        ET.SubElement(i, "pubDate").text = item["pubDate"]

    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    items = fetch_items(rss_feeds)
    print(f"Fetched {len(items)} unique articles.")
    rss_xml = create_rss(items)
    with open("combined.xml", "wb") as f:
        f.write(rss_xml)
    print("Combined RSS feed created successfully.")
