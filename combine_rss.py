import feedparser
import xml.etree.ElementTree as ET
from datetime import datetime

# RSS feed URLs
rss_feeds = [
    "https://www.economist.com/briefing/rss.xml",
    "https://www.economist.com/the-economist-explains/rss.xml",
    "https://www.economist.com/leaders/rss.xml",
    "https://www.economist.com/asia/rss.xml",
    "https://www.economist.com/china/rss.xml",
    "https://www.economist.com/international/rss.xml",
    "https://www.economist.com/united-states/rss.xml",
    "https://www.economist.com/finance-and-economics/rss.xml",
    "https://www.economist.com/the-world-this-week/rss.xml"
]

ARCHIVE_PREFIX = "https://archive.is/o/nuunc/"

def fetch_items(feed_urls):
    all_items = []
    for feed_url in feed_urls:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if not hasattr(entry, "link"):
                continue
            original_link = entry.link
            archive_link = ARCHIVE_PREFIX + original_link
            all_items.append({
                "title": entry.title,
                "link": archive_link,
                "description": entry.get("description", ""),
                "pubDate": entry.get("published", datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000"))
            })
    return all_items

def create_rss(items):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Combined Economist RSS Feed"
    ET.SubElement(channel, "link").text = "https://yourusername.github.io/combined.xml"
    ET.SubElement(channel, "description").text = "Combined feed of multiple Economist RSS sources with archive.is/o/nuunc links"
    
    for item in items:
        i = ET.SubElement(channel, "item")
        ET.SubElement(i, "title").text = item["title"]
        ET.SubElement(i, "link").text = item["link"]
        ET.SubElement(i, "description").text = item["description"]
        ET.SubElement(i, "pubDate").text = item["pubDate"]
    
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    items = fetch_items(rss_feeds)
    rss_xml = create_rss(items)
    with open("combined.xml", "wb") as f:
        f.write(rss_xml)
    print("Combined RSS feed created successfully.")
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
