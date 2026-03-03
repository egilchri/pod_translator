import argparse
import feedparser
import re
import sys
import os
import time
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
    print(f"Fetching feed: {url}")
    feed = feedparser.parse(url)
    
    if not feed.entries:
        print("Error: Could not parse feed or no entries found.")
        return None, None

    # FEATURE: Use feedname_override if provided, otherwise slugify the title
    if feedname_override:
        feed_name_attr = feedname_override
        print(f"Using manual feedname override: {feed_name_attr}")
    else:
        podcast_title = feed.feed.get('title', 'Unknown Podcast')
        feed_name_attr = slugify(podcast_title)
        print(f"Discovered feedname: {feed_name_attr}")

    podcast_title_display = feed.feed.get('title', 'Unknown Podcast')
    
    # Sync Logic: Capture the timestamp of the latest episode in the RSS
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

    # Metadata persistence: Save the RSS source and override status in the HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="{lang_code}" data-is-override="{is_override}" data-rss-url="{url}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{podcast_title_display} - Feed Dashboard</title>
        <style>
            body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f0f2f5; }}
            .nav-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .btn-back {{ background: #6c757d; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; }}
            .btn-sync {{ background: #ffc107; color: black; padding: 8px 16px; border-radius: 6px; font-weight: bold; border: none; cursor: pointer; display: none; animation: pulse 2s infinite; }}
            @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} 100% {{ opacity: 1; }} }}
            header {{ background: #004a99; color: white; padding: 25px; border-radius: 12px; margin-bottom: 30px; }}
            
            .episode-card {{ background: white; padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-left: 6px solid #ccc; position: relative; }}
            .episode-card.is-live {{ border-left-color: #28a745; }}
            
            .status-tag {{ position: absolute; top: 15px; right: 20px; font-size: 0.75rem; font-weight: bold; padding: 4px 8px; border-radius: 4px; text-transform: uppercase; }}
            .tag-live {{ background: #d4edda; color: #155724; }}
            .tag-pending {{ background: #fff3cd; color: #856404; }}
            .tag-checking {{ background: #e9ecef; color: #666; }}
            
            .btn-group {{ display: flex; gap: 8px; margin-top: 15px; flex-wrap: wrap; }}
            .btn {{ padding: 10px 15px; border-radius: 6px; font-weight: bold; text-decoration: none; cursor: pointer; border: none; font-size: 0.85em; }}
            .btn-run {{ background: #ffc107; color: black; }}
            .btn-view {{ background: #28a745; color: white; display: none; }}
            .toast {{ position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); background: #333; color: white; padding: 15px 30px; border-radius: 50px; display: none; z-index: 1000; }}
        </style>
        <script>
            function triggerUpdate() {{
                const rssUrl = document.documentElement.getAttribute('data-rss-url');
                const langCode = {js_lang_param};
                const langFlag = langCode ? ` --lang ${{langCode}}` : "";
                const cmd = `python3 run_workflow_feed.py --url "${{rssUrl}}"${{langFlag}}`;
                navigator.clipboard.writeText(cmd).then(() => {{
                    alert("Feed Update command copied! Run it in your terminal.");
                }});
            }}
            function copyMasterCommand(mp3Url, feedname, date, title, lang) {{
                const cmd = `python3 ./run_workflow.py --url "${{mp3Url}}" --feedname "${{feedname}}" --date "${{date}}" --title "${{title}}" --lang "${{lang}}"`;
                navigator.clipboard.writeText(cmd).then(() => {{
                    const t = document.getElementById('toast');
                    t.style.display = 'block';
                    setTimeout(() => {{ t.style.display = 'none'; }}, 3000);
                }});
            }}

            async function checkLiveStatus(i, url) {{
                const status = document.getElementById(`status-${{i}}`);
                const card = document.getElementById(`card-${{i}}`);
                const viewBtn = document.getElementById(`view-${{i}}`);
                
                try {{
                    const response = await fetch(url, {{ method: 'HEAD' }});
                    if (response.ok) {{
                        status.innerText = "● Live";
                        status.className = "status-tag tag-live";
                        card.classList.add('is-live');
                        viewBtn.style.display = 'inline-block';
                    }} else {{
                        status.innerText = "○ Pending";
                        status.className = "status-tag tag-pending";
                    }}
                }} catch (e) {{
                    status.innerText = "○ Offline";
                    status.className = "status-tag tag-pending";
                }}
            }}
        </script>
    </head>
    <body data-latest="{latest_ts}" data-generated="{time.time()}">
        <div class="nav-header">
            <button class="btn-back" onclick="window.history.back()">← Back to Index</button>
            <button id="syncBtn" class="btn-sync" onclick="triggerUpdate()">⚠ Update Available</button>
        </div>
        <header>
            <h1>{podcast_title_display}</h1>
            <p>Language: <strong>{lang_code}</strong> {"(Manual Override)" if lang_override else ""}</p>
        </header>
        <div id="toast" class="toast">✅ Command Courtesied to Clipboard!</div>
    """

    for i, entry in enumerate(feed.entries[:15]):
        dt = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else datetime.now()
        date_param = dt.strftime("%y%m%d")
        
        # Construct the URLs based on the determined feed_name_attr
        expected_mp3_url = f"{base_gh_url}/{feed_name_attr}.{date_param}.mp3"
        live_url = f"{base_gh_url}/{feed_name_attr}.{date_param}.html"

        mp3_link = next((en.href for en in entry.get('enclosures', []) if en.type == 'audio/mpeg'), "")
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
    # Added optional --feedname parameter
    parser.add_argument("--feedname", help="Override the discovered feed name")
    args = parser.parse_args()
    
    # Passing args.feedname to the creation function
    fname, lcode = create_general_feed(args.url, args.lang, args.feedname)
    if fname and lcode:
        print(f"FEEDNAME_OUTPUT:{fname}")
        print(f"LANG_OUTPUT:{lcode}")
