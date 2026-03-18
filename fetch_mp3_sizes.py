#!/usr/bin/env python3
"""
fetch_mp3_sizes.py  —  patch MP3 file sizes into a feed HTML file.

Usage:
    python3 fetch_mp3_sizes.py usapodden
    python3 fetch_mp3_sizes.py usapodden --html Podcasts/usapodden.feed.html
"""

import argparse
import re
import sys
import urllib.request

def get_content_length(url):
    try:
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            length = resp.headers.get('Content-Length')
            return int(length) if length else 0
    except Exception as e:
        print(f"  [!] HEAD failed for {url}: {e}", file=sys.stderr)
        return 0

def format_size(bytes):
    if bytes <= 0:
        return None
    return f"{bytes / 1_000_000:.0f} MB"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("feedname", help="Feed slug, e.g. usapodden")
    parser.add_argument("--html", help="Path to feed HTML (default: Podcasts/{feedname}.feed.html)")
    args = parser.parse_args()

    html_path = args.html or f"Podcasts/{args.feedname}.feed.html"

    with open(html_path, encoding='utf-8') as f:
        html = f.read()

    # Find all episode cards and their MP3 URLs
    card_pattern = re.compile(
        r'(<div class="episode-card" id="card-\d+">'
        r'.*?<small style="color:#666; font-weight:bold;">)(.*?)(</small>)'
        r'(.*?copyMasterCommand\(\'(https?://[^\']+\.mp3)\')',
        re.DOTALL
    )

    def replace_card(m):
        prefix = m.group(1)
        date_text = m.group(2)
        close_small = m.group(3)
        rest = m.group(4)
        mp3_url = m.group(5)

        # Strip any previously added size
        date_clean = re.sub(r'\s*&nbsp;·&nbsp;\s*\d+ MB', '', date_text)

        print(f"  {date_clean}: {mp3_url}")
        size_bytes = get_content_length(mp3_url)
        size_str = format_size(size_bytes)

        if size_str:
            print(f"    → {size_str}")
            new_date = f"{date_clean} &nbsp;·&nbsp; {size_str}"
        else:
            print(f"    → size unknown, leaving unchanged")
            new_date = date_clean

        return f"{prefix}{new_date}{close_small}{rest}"

    print(f"Fetching MP3 sizes for {args.feedname}...")
    new_html, count = card_pattern.subn(replace_card, html)
    print(f"\nPatched {count} episode cards.")

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(f"Wrote {html_path}")

if __name__ == '__main__':
    main()
