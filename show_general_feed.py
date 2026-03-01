import argparse
import feedparser
import re
import sys
from datetime import datetime

def clean_text(text):
    """Cleans text for safe command-line usage."""
    if not text: return ""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    return " ".join(text.split()).replace('"', '\\"').replace("'", "\\'")

def slugify(text):
    """Converts a string into a short, filename-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:15]

def create_general_feed(url, lang_override=None):
    print(f"Fetching feed: {url}")
    feed = feedparser.parse(url)
    
    if not feed.entries:
        print("Error: Could not parse feed or no entries found.")
        return None, None

    # Extract metadata from RSS
    podcast_title = feed.feed.get('title', 'Unknown Podcast')
    feed_name_attr = slugify(podcast_title)
    
    # Determine language: Use override if provided, otherwise detect from RSS
    if lang_override:
        lang_code = lang_override
        print(f"[*] Using language override: {lang_code}")
    else:
        full_lang = feed.feed.get('language', 'en-us').lower()
        lang_code = full_lang.split('-')[0]
        
    if lang_code == "en":
        print(f"Error: Target language is English. Skipping.")
        return None, None

    base_gh_url = "https://egilchri.github.io/pod_tran"

    # ADDED: Navigation header and Back button styles
    html_content = f"""
    <!DOCTYPE html>
    <html lang="{lang_code}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{podcast_title} - Feed Dashboard</title>
        <style>
            body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f0f2f5; }}
            .nav-header {{ display: flex; align-items: center; margin-bottom: 20px; }}
            .btn-back {{ background: #6c757d; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; }}
            .btn-back:hover {{ background: #5a6268; }}
            header {{ background: #004a99; color: white; padding: 25px; border-radius: 12px; margin-bottom: 30px; }}
            .episode-card {{ background: white; padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-left: 6px solid #ffc107; }}
            h2 {{ margin: 0 0 10px 0; font-size: 1.3em; }}
            .summary {{ color: #444; font-size: 0.95em; margin-bottom: 20px; line-height: 1.5; }}
            .btn-group {{ display: flex; gap: 8px; border-top: 1px solid #eee; padding-top: 15px; flex-wrap: wrap; }}
            .btn {{ padding: 10px 15px; border-radius: 6px; font-weight: bold; text-decoration: none; cursor: pointer; border: none; font-size: 0.85em; display: inline-block; }}
            .btn-run {{ background: #ffc107; color: black; }}
            .btn-view {{ background: #28a745; color: white; }}
            .btn-listen {{ background: #e9ecef; color: #004a99; border: 1px solid #004a99; }}
            .toast {{ position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); background: #333; color: white; padding: 15px 30px; border-radius: 50px; display: none; z-index: 1000; }}
        </style>
        <script>
            function copyMasterCommand(mp3Url, feedname, date, title, lang) {{
                const cmd = `python3 ./run_workflow.py --url "${{mp3Url}}" --feedname "${{feedname}}" --date "${{date}}" --title "${{title}}" --lang "${{lang}}"`;
                navigator.clipboard.writeText(cmd).then(() => {{
                    const t = document.getElementById('toast');
                    t.style.display = 'block';
                    setTimeout(() => {{ t.style.display = 'none'; }}, 3000);
                }});
            }}
        </script>
    </head>
    <body>
        <div class="nav-header">
            <button class="btn-back" onclick="window.history.back()">← Back to Index</button>
        </div>
        <header>
            <h1>{podcast_title}</h1>
            <p>Language Detected: <strong>{lang_code}</strong> | Feed ID: <strong>{feed_name_attr}</strong></p>
        </header>
        <div id="toast" class="toast">✅ Workflow Command Copied!</div>
    """

    for entry in feed.entries[:15]:
        dt = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else datetime.now()
        date_param = dt.strftime("%y%m%d")
        mp3_link = next((en.href for en in entry.get('enclosures', []) if en.type == 'audio/mpeg'), "")
        c_title = clean_text(entry.get('title', 'Untitled'))
        live_url = f"{base_gh_url}/{feed_name_attr}.{date_param}.html"

        html_content += f"""
        <div class="episode-card">
            <small style="color:#666; font-weight:bold;">{dt.strftime("%B %d, %Y")}</small>
            <h2>{entry.title}</h2>
            <div class="summary">{clean_text(entry.get('summary', ''))[:300]}...</div>
            <div class="btn-group">
                <button class="btn btn-run" onclick="copyMasterCommand('{mp3_link}', '{feed_name_attr}', '{date_param}', '{c_title}', '{lang_code}')">
                    ⚡ Copy Process Command
                </button>
                <a href="{live_url}" target="_blank" class="btn btn-view">🌐 View Live</a>
                <a href="{mp3_link}" target="_blank" class="btn btn-listen">🎧 Preview MP3</a>
            </div>
        </div>
        """

    output_filename = f"{feed_name_attr}.feed.html"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html_content + "</body></html>")
    
    return feed_name_attr, lang_code

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--lang", help="Override the RSS language code")
    args = parser.parse_args()
    
    fname, lcode = create_general_feed(args.url, args.lang)
    if fname and lcode:
        print(f"FEEDNAME_OUTPUT:{fname}")
        print(f"LANG_OUTPUT:{lcode}")

