"""
update_latest.py -- download and process the latest episode for a feed, then refresh the feed page.

Usage:
    python3 update_latest.py usapodden
"""

import argparse
import os
import re
import subprocess
import sys
import time

import feedparser
import requests


def read_feed_meta(feedname):
    """Extract RSS URL, lang, and start-pattern from the existing feed HTML."""
    feed_html = os.path.join("Podcasts", f"{feedname}.feed.html")
    if not os.path.exists(feed_html):
        print(f"[!] No feed HTML found at {feed_html}. Run run_workflow_feed.py first.")
        sys.exit(1)
    with open(feed_html, encoding="utf-8") as f:
        content = f.read()
    url_m = re.search(r'data-rss-url="([^"]+)"', content)
    lang_m = re.search(r'<html lang="([^"]+)"', content)
    is_override = 'data-is-override="true"' in content
    pattern_m = re.search(r'data-start-pattern="([^"]+)"', content)
    if not url_m:
        print("[!] Could not extract data-rss-url from feed HTML.")
        sys.exit(1)
    return {
        "url": url_m.group(1),
        "lang": lang_m.group(1) if lang_m and is_override else None,
        "start_pattern": pattern_m.group(1) if pattern_m else None,
    }


def clean_title(text):
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r'<[^>]+>', '', text)
    return " ".join(text.split()).replace('"', "'")


def fetch_latest_entry(rss_url):
    """Fetch the RSS feed and return the first (newest) entry."""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cache-Control": "no-cache",
    }
    try:
        resp = requests.get(f"{rss_url}?t={int(time.time())}", headers=headers, timeout=20)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"[!] Failed to fetch RSS: {e}. Falling back to direct parse.")
        feed = feedparser.parse(rss_url)
    if not feed.entries:
        print("[!] No entries found in feed.")
        sys.exit(1)
    return feed.entries[0]


def run(cmd, cwd=None):
    subprocess.run(cmd, check=True, cwd=cwd)


def main():
    parser = argparse.ArgumentParser(description="Download latest episode for a feed and refresh the feed page.")
    parser.add_argument("feedname", help="Feed name (e.g. usapodden)")
    args = parser.parse_args()

    feedname = args.feedname
    meta = read_feed_meta(feedname)
    rss_url = meta["url"]
    lang = meta["lang"]
    start_pattern = meta["start_pattern"]

    print(f"--- Checking latest episode for '{feedname}' ---")
    entry = fetch_latest_entry(rss_url)

    from datetime import datetime
    dt = datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") else datetime.now()
    date_param = dt.strftime("%y%m%d")
    title = clean_title(entry.get("title", "Untitled"))
    mp3_url = next(
        (e.href for e in entry.get("enclosures", []) if e.type == "audio/mpeg"), ""
    )
    if mp3_url.startswith("//"):
        mp3_url = "https:" + mp3_url

    expected_html = os.path.join("Podcasts", f"{feedname}.{date_param}.html")
    if os.path.exists(expected_html):
        print(f"--- Episode {date_param} already processed. Skipping download. ---")
    else:
        if not mp3_url:
            print("[!] No MP3 enclosure found in latest RSS entry.")
            sys.exit(1)
        print(f"--- New episode found: {title} ({date_param}) ---")
        cmd = [
            "python3", "run_workflow.py",
            "--url", mp3_url,
            "--feedname", feedname,
            "--date", date_param,
            "--title", title,
        ]
        if lang:
            cmd.extend(["--lang", lang])
        if start_pattern:
            cmd.extend(["--start-pattern", start_pattern])
        run(cmd)

    print(f"--- Refreshing feed page for '{feedname}' ---")
    feed_cmd = ["python3", "run_workflow_feed.py", "--url", rss_url, "--feedname", feedname]
    if lang:
        feed_cmd.extend(["--lang", lang])
    if start_pattern:
        feed_cmd.extend(["--start-pattern", start_pattern])
    run(feed_cmd)

    print(f"--- Done. '{feedname}' is up to date. ---")


if __name__ == "__main__":
    main()
