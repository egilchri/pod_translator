import argparse
import feedparser
import re
import sys
import os
import time
import requests
from datetime import datetime

def clean_text(text):
    """Cleans text for safe command-line usage and HTML safety."""
    if not text: return ""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    # Using single quotes to prevent f-string syntax errors in Python
    return " ".join(text.split()).replace('"', "'")

def slugify(text):
    """Converts a string into a short, filename-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:15]

def create_general_feed(url, lang_override=None, feedname_override=None):
    # 1. CACHE-BUSTING FETCH
    # Add a unique 'salt' to the URL and use strict headers to bypass CDN caching
    cache_buster_url = f"{url}?t={int(time.time())}"
    print(f"Fetching fresh feed: {cache_buster_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }
    
    try:
        response = requests.get(cache_buster_url, headers=headers, timeout=20)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"Cache-bust failed: {e}. Falling back to standard URL.")
        feed = feedparser.parse(url)
    
    if not feed.entries:
        print("Error: Could not parse feed or no entries found.")
        return None, None

    # Determine Feedname
    if feedname_override:
        feed_name_attr = feedname_override
        print(f"Using manual feedname override: {feed_name_attr}")
    else:
        podcast_title = feed.feed.get('title', 'Unknown Podcast')
        feed_name_attr = slugify(podcast_title)
        print(f"Discovered feedname: {feed_name_attr}")

    podcast_title_display = feed.feed.get('title', 'Unknown Podcast')
    
    # Sync Logic: Latest entry timestamp
    latest_entry = feed.entries[0]
    latest_ts = time.mktime(latest_entry.published_parsed) if hasattr(latest_entry, 'published_parsed') else time.time()

    # Determine language logic
    is_override = "true" if lang_override else "false"
    if lang_override:
        lang_code = lang_override
    else:
        full_lang = feed.feed.get('language', 'en-us').lower()
        if "en" in full_lang:
            print(f"Error: Target language is English ({full_lang}). Skipping.")
            return None, None
        lang_code = full_lang.split('-')[0]

    base_gh_url = "https://egilchri.github.io/pod_tran"
    js_lang_param = f"'{lang_override}'" if lang_override else "null"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="{lang_code}" data-is-override="{is_override}" data-rss-url="{url}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{podcast_title_display} - Feed Dashboard</title>
        
        <link rel="manifest" href="manifest.json">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        
        <style>
            body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f0f2f5; }}
            /* ... (rest of your styles) */
        </style>
        
        <script>
            // Register Service Worker for PWA
            if ('serviceWorker' in navigator) {{
                window.addEventListener('load', () => {{
                    navigator.serviceWorker.register('sw.js').then(reg => {{
                        console.log('SW registered:', reg);
                    }}).catch(err => {{
                        console.log('SW registration failed:', err);
                    }});
                }});
            }}

            function triggerUpdate() {{
                const rssUrl = document.documentElement.getAttribute('data-rss-url');
                const langCode = {js_lang_param};
                const langFlag = langCode ? ` --lang ${{langCode}}` : "";
                const cmd = `python3 run_workflow_feed.py --url "${{rssUrl}}"${{langFlag}}`;
                navigator.clipboard.writeText(cmd).then(() => {{
                    alert("Feed Update command copied! Run it in your terminal.");
                }});
            }}
            /* ... (rest of your existing scripts) */
        </script>
    </head>
    <body data-latest="{latest_ts}" data-generated="{time.time()}">
    """


    for i, entry in enumerate(feed.entries[:15]):
        dt = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else datetime.now()
        date_param = dt.strftime("%y%m%d")
        
        # 2. PROTOCOL REPAIR
        # Fix //sverigesradio.se URLs common in SR feeds
        mp3_link = next((en.href for en in entry.get('enclosures', []) if en.type == 'audio/mpeg'), "")
        if mp3_link.startswith("//"):
            mp3_link = "https:" + mp3_link

        expected_mp3_url = f"{base_gh_url}/{feed_name_attr}.{date_param}.mp3"
        live_url = f"{base_gh_url}/{feed_name_attr}.{date_param}.html"
        c_title = clean_text(entry.get('title', 'Untitled'))
        c_summary = clean_text(entry.get('summary', ''))[:300]

        html_content += f"""
        <div class="episode-card" id="card-{i}">
            <span id="status-{i}" class="status-tag tag-checking">Checking...</span>
            <small style="color:#666; font-weight:bold;">{dt.strftime("%B %d, %Y")}</small>
            <h2>{c_title}</h2>
            <div class="summary">{c_summary}...</div>
            <div class="btn-group">
                <button class="btn btn-run" onclick="copyMasterCommand('{mp3_link}', '{feed_name_attr}', '{date_param}', '{c_title}', '{lang_code}')">⚡ Copy Process Command</button>
                <a href="{live_url}" id="view-{i}" class="btn btn-view">🌐 View Live</a>
                <a href="{mp3_link}" target="_blank" class="btn" style="background:#e9ecef; color:#004a99; border:1px solid #004a99;">🎧 Preview MP3</a>
            </div>
            <script>checkLiveStatus({i}, "{expected_mp3_url}");</script>
        </div>"""

    output_filename = f"{feed_name_attr}.feed.html"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html_content + """
        <script>
            window.addEventListener('DOMContentLoaded', () => {
                const latest = parseFloat(document.body.dataset.latest);
                const generated = parseFloat(document.body.dataset.generated);
                if (latest > generated) {
                    document.getElementById('syncBtn').style.display = 'block';
                }
            });
        </script>
        </body></html>""")
    return feed_name_attr, lang_code

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--lang", help="Override the RSS language code")
    parser.add_argument("--feedname", help="Override the discovered feed name")
    args = parser.parse_args()
    
    fname, lcode = create_general_feed(args.url, args.lang, args.feedname)
    if fname and lcode:
        print(f"FEEDNAME_OUTPUT:{fname}")
        print(f"LANG_OUTPUT:{lcode}")

