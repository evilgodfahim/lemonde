import feedparser
import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import time

# RSS feed URLs (updated with the missing feed)
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

CACHE_FILE = "cache.json"
WAIT_TIME = 10  # Max seconds for archive fetching
RETRY_COUNT = 3  # Retry on failure

# Load or create cache
try:
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
except:
    cache = {}

# Function to get latest archived link robustly
def get_latest_archive(url):
    if url in cache:
        return cache[url]
    
    latest_url = f"https://archive.is/{url}"  # Fallback

    for attempt in range(RETRY_COUNT):
        try:
            # Wayback Machine API for archived versions
            api_url = f"https://archive.org/wayback/available?url={url}"
            response = requests.get(api_url, timeout=WAIT_TIME, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code == 200:
                data = response.json()
                snapshots = data.get("archived_snapshots", {})
                if "closest" in snapshots:
                    latest_url = snapshots["closest"]["url"]
            break
        except requests.RequestException as e:
            print(f"Attempt {attempt+1}: Error fetching archive for {url}: {e}")
            time.sleep(2)
    
    cache[url] = latest_url
    return latest_url

# Fetch items from all RSS feeds
def fetch_items(feed_urls):
    all_items = []
    for feed_url in feed_urls:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if not hasattr(entry, "link"):
                continue
            first_link = entry.link
            archive_link = get_latest_archive(first_link)
            all_items.append({
                "title": entry.title,
                "link": archive_link,
                "description": entry.get("description", ""),
                "pubDate": entry.get("published", datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000"))
            })
            time.sleep(0.5)  # polite delay
    return all_items

# Create combined RSS XML
def create_rss(items):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Combined Economist RSS Feed"
    ET.SubElement(channel, "link").text = "https://yourusername.github.io/combined.xml"
    ET.SubElement(channel, "description").text = "Combined feed of multiple Economist RSS sources with latest archived links"
    
    for item in items:
        i = ET.SubElement(channel, "item")
        ET.SubElement(i, "title").text = item["title"]
        ET.SubElement(i, "link").text = item["link"]
        ET.SubElement(i, "description").text = item["description"]
        ET.SubElement(i, "pubDate").text = item["pubDate"]
    
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)

# Main execution
if __name__ == "__main__":
    items = fetch_items(rss_feeds)
    rss_xml = create_rss(items)
    with open("combined.xml", "wb") as f:
        f.write(rss_xml)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
    print("Combined RSS feed created successfully.")
