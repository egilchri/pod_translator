import argparse
import feedparser
import re
import sys
import time
from datetime import datetime

def clean_text(text):
    if not text: return ""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    return " ".join(text.split()).replace('"', "'")

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:15]

def create_general_feed(url, lang_override=None):
    feed = feedparser.parse(url)
    if not feed.entries: return None, None
    
    podcast_title = feed.feed.get('title', 'Unknown Podcast')
    feed_name_attr = slugify(podcast_title)
    
    # Sync Logic: Get latest entry timestamp
    latest_entry = feed.entries[0]
    latest_ts = time.mktime(latest_entry.published_parsed) if hasattr(latest_entry, 'published_parsed') else time.time()

    is_override = "true" if lang_override else "false"
    if lang_override:
        lang_code = lang_override
    else:
        full_lang = feed.feed.get('language', 'en-us').lower()
        if "en" in full_lang: return None, None
        lang_code = full_lang.split('-')[0]

    base_gh_url = "https://egilchri.github.io/pod_tran"

    # NEW: Added data-rss-url to keep track of the source
    html_content = f"""
    <!DOCTYPE html>
    <html lang="{lang_code}" data-is-override="{is_override}" data-rss-url="{url}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{podcast_title} - Feed Dashboard</title>
        <style>
            body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f0f2f5; }}
            .nav-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .btn-back {{ background: #6c757d; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; }}
            .btn-sync {{ background: #ffc107; color: black; padding: 8px 16px; border-radius: 6px; font-weight: bold; border: none; cursor: pointer; display: none; animation: pulse 2s infinite; }}
            @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} 100% {{ opacity: 1; }} }}
            header {{ background: #004a99; color: white; padding: 25px; border-radius: 12px; margin-bottom: 30px; }}
            .episode-card {{ background: white; padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-left: 6px solid #ffc107; }}
            .btn-run {{ background: #ffc107; color: black; padding: 10px 15px; border-radius: 6px; font-weight: bold; cursor: pointer; border: none; }}
        </style>
        <script>
            function triggerUpdate() {{
                const cmd = `python3 run_workflow_feed.py --url "{url}"` + ("{lang_override}" ? ` --lang {lang_override}` : "");
                navigator.clipboard.writeText(cmd);
                alert("Update command copied! Run it in your terminal.");
            }}
            function copyMasterCommand(mp3Url, feedname, date, title, lang) {{
                const cmd = `python3 ./run_workflow.py --url "${{mp3Url}}" --feedname "${{feedname}}" --date "${{date}}" --title "${{title}}" --lang "${{lang}}"`;
                navigator.clipboard.writeText(cmd);
            }}
        </script>
    </head>
    <body data-latest="{latest_ts}" data-generated="{time.time()}">
        <div class="nav-header">
            <button class="btn-back" onclick="window.history.back()">← Back to Index</button>
            <button id="syncBtn" class="btn-sync" onclick="triggerUpdate()">⚠ Update Available</button>
        </div>
        <header>
            <h1>{podcast_title}</h1>
            <p>Language: <strong>{lang_code}</strong> {"(Manual Override)" if lang_override else ""}</p>
        </header>
        <script>
            window.addEventListener('DOMContentLoaded', () => {{
                if (parseFloat(document.body.dataset.latest) > parseFloat(document.body.dataset.generated)) {{
                    document.getElementById('syncBtn').style.display = 'block';
                }}
            }});
        </script>
    """

    for entry in feed.entries[:15]:
        dt = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else datetime.now()
        date_param = dt.strftime("%y%m%d")
        mp3_link = next((en.href for en in entry.get('enclosures', []) if en.type == 'audio/mpeg'), "")
        c_title = clean_text(entry.get('title', 'Untitled'))
        live_url = f"{base_gh_url}/{feed_name_attr}.{date_param}.html"

        html_content += f"""
        <div class="episode-card">
            <small>{dt.strftime("%B %d, %Y")}</small>
            <h2>{c_title}</h2>
            <div class="btn-group">
                <button class="btn-run" onclick="copyMasterCommand('{mp3_link}', '{feed_name_attr}', '{date_param}', '{c_title}', '{lang_code}')">⚡ Copy Process Command</button>
                <a href="{live_url}" class="btn-view" style="background:#28a745; color:white; padding:10px 15px; border-radius:6px; text-decoration:none; font-weight:bold;">🌐 View Live</a>
            </div>
        </div>"""

    with open(f"{feed_name_attr}.feed.html", "w", encoding="utf-8") as f:
        f.write(html_content + "</body></html>")
    return feed_name_attr, lang_code

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--lang", help="Override language code")
    args = parser.parse_args()
    fname, lcode = create_general_feed(args.url, args.lang)
    if fname and lcode:
        print(f"FEEDNAME_OUTPUT:{fname}")
        print(f"LANG_OUTPUT:{lcode}")


