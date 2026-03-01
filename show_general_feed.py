import argparse
import feedparser
import re
import sys
from datetime import datetime

def clean_text(text):
    if not text: return ""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    return " ".join(text.split()).replace('"', '\\"').replace("'", "\\'")

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:15]

def create_general_feed(url, lang_override=None):
    feed = feedparser.parse(url)
    if not feed.entries: return None, None
    podcast_title = feed.feed.get('title', 'Unknown Podcast')
    feed_name_attr = slugify(podcast_title)
    
    # Logic for override tracking
    is_override = "true" if lang_override else "false"
    if lang_override:
        lang_code = lang_override
    else:
        full_lang = feed.feed.get('language', 'en-us').lower()
        lang_code = full_lang.split('-')[0]

    base_gh_url = "https://egilchri.github.io/pod_tran"

    # Embed data-is-override in the html tag
    html_content = f"""
    <!DOCTYPE html>
    <html lang="{lang_code}" data-is-override="{is_override}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{podcast_title} - Feed Dashboard</title>
        <style>
            body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f0f2f5; }}
            .nav-header {{ display: flex; align-items: center; margin-bottom: 20px; }}
            .btn-back {{ background: #6c757d; color: white; padding: 8px 16px; border-radius: 6px; font-weight: bold; border: none; cursor: pointer; }}
            header {{ background: #004a99; color: white; padding: 25px; border-radius: 12px; margin-bottom: 30px; }}
            .episode-card {{ background: white; padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-left: 6px solid #ffc107; }}
        </style>
    </head>
    <body>
        <div class="nav-header">
            <button class="btn-back" onclick="window.history.back()">← Back to Index</button>
        </div>
        <header>
            <h1>{podcast_title}</h1>
            <p>Language: <strong>{lang_code}</strong> {"(Manual Override)" if lang_override else ""}</p>
        </header>
    """
    # ... rest of entry loop logic ...
    output_filename = f"{feed_name_attr}.feed.html"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html_content + "</body></html>")
    return feed_name_attr, lang_code

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--lang", help="Override the RSS language code")
    args = parser.parse_args()
    
    # Capture the return values from the function
    fname, lcode = create_general_feed(args.url, args.lang)
    
    # The master script SEARCHES for these specific strings
    if fname and lcode:
        print(f"FEEDNAME_OUTPUT:{fname}")
        print(f"LANG_OUTPUT:{lcode}")
        

