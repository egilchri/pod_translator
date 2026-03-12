#!/usr/bin/env python3
"""
Check whether a podcast feed has a new episode that hasn't been processed yet.
If so, send a local mail with the exact run_workflow.py command to process it.

Usage:
    python3 check_staleness.py --feedname usapodden
    python3 check_staleness.py --feedname ok-america --dry-run
"""

import argparse
import re
import time
import subprocess
import feedparser
import requests
from datetime import datetime

PODCASTS_DIR = "/Users/edgargilchrist/tools/PodTranslator/Podcasts"
MAIL_TO = "edgargilchrist"


def get_feed_metadata(feedname):
    feed_html_path = f"{PODCASTS_DIR}/{feedname}.feed.html"
    with open(feed_html_path, encoding="utf-8") as f:
        content = f.read()

    rss_url_m = re.search(r'data-rss-url="([^"]+)"', content)
    if not rss_url_m:
        raise ValueError(f"Could not find data-rss-url in {feed_html_path}")
    rss_url = rss_url_m.group(1)

    lang_m = re.search(r'<html\s[^>]*lang="([^"]+)"', content)
    if not lang_m:
        raise ValueError(f"Could not find lang in <html> tag in {feed_html_path}")
    lang = lang_m.group(1)

    latest_m = re.search(r'data-latest="([0-9.]+)"', content)
    if not latest_m:
        raise ValueError(f"Could not find data-latest in {feed_html_path}")
    known_latest_ts = float(latest_m.group(1))

    return rss_url, lang, known_latest_ts


def fetch_latest_rss_entry(rss_url):
    cache_buster_url = f"{rss_url}?t={int(time.time())}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    try:
        response = requests.get(cache_buster_url, headers=headers, timeout=20)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"Cache-bust failed: {e}. Falling back.")
        feed = feedparser.parse(rss_url)

    if not feed.entries:
        raise ValueError("No entries found in RSS feed")

    return feed.entries[0]


def clean_text(text):
    if not text:
        return ""
    text = re.sub(re.compile("<.*?>"), "", text)
    return " ".join(text.split()).replace('"', "'")


def build_command(entry, feedname, lang):
    dt = datetime(*entry.published_parsed[:6])
    date_param = dt.strftime("%y%m%d")
    mp3_url = next(
        (en.href for en in entry.get("enclosures", []) if en.type == "audio/mpeg"), ""
    )
    if mp3_url.startswith("//"):
        mp3_url = "https:" + mp3_url
    title = clean_text(entry.get("title", "Untitled"))
    return (
        f'python3 ./run_workflow.py --url "{mp3_url}" '
        f'--feedname "{feedname}" --date "{date_param}" '
        f'--title "{title}" --lang "{lang}"'
    )


def send_mail(subject, body):
    result = subprocess.run(
        ["mail", "-s", subject, MAIL_TO],
        input=body,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"mail failed: {result.stderr}")
    else:
        print("Mail sent.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feedname", required=True, help="Feed name (e.g. usapodden, ok-america)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the command that would be mailed without checking staleness or sending mail")
    args = parser.parse_args()

    rss_url, lang, known_latest_ts = get_feed_metadata(args.feedname)
    entry = fetch_latest_rss_entry(rss_url)
    title = clean_text(entry.get("title", "Untitled"))
    cmd = build_command(entry, args.feedname, lang)

    if args.dry_run:
        print(f"Latest episode: {title}")
        print(f"\nCommand that would be mailed:\n\n{cmd}")
        return

    rss_ts = time.mktime(entry.published_parsed) if hasattr(entry, "published_parsed") else 0

    if rss_ts <= known_latest_ts:
        print(f"No new episode. RSS latest: {rss_ts}, known latest: {known_latest_ts}")
        return

    subject = f"{args.feedname}: new episode ready to process"
    body = f"New episode detected: {title}\n\nRun this command to process it:\n\n{cmd}\n"
    print(body)
    send_mail(subject, body)


if __name__ == "__main__":
    main()
