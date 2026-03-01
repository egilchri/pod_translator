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

    podcast_title = feed.feed.get('title', 'Unknown Podcast')
    feed_name_attr = slugify(podcast_title)
    
    # Determine language logic
    is_override = "true" if lang_override else "false"
    if lang_override:
        lang_code = lang_override
        print(f"[*] Using language override: {lang_code}")
    else:
        full_lang = feed.feed.get('language', 'en-us').lower()
        # Only block English if no override is provided
        if "en" in full_lang:
            print(f"Error: Target language is English ({full_lang}). Skipping.")
            return None, None
        lang_code = full_lang.split('-')[0]

    base_gh_url = "https://egilchri.github.io/pod_tran"

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
            .btn-back {{ background: #6c757d; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; }}
            header {{ background: #004a99; color: white; padding: 25px; border-radius: 12px; margin-bottom: 30px; }}
            .episode-card {{ background: white; padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-left: 6px solid #ffc107; }}
            .btn-run {{ background: #ffc107; color: black; padding: 10px 15px; border-radius: 6px; font-weight: bold; cursor: pointer; border: none; }}
            .toast {{ position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); background: #333; color: white; padding: 15px 30px; border-radius: 50px; display: none; }}
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
            <p>Language: <strong>{lang_code}</strong> {"(Manual Override)" if lang_override else ""}</p>
        </header>
        <div id="toast" class="toast">✅ Command Copied!</div>
    """

    for entry in feed.entries[:15]:
        dt = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else datetime.now()
        date_param = dt.strftime("%y%m%d")
        mp3_link = next((en.href for en in entry.get('enclosures', []) if en.type == 'audio/mpeg'), "")
        c_title = clean_text(entry.get('title', 'Untitled'))
        
        html_content += f"""
        <div class=\"episode-card\">
            <small>{dt.strftime(\"%B %d, %Y\")}</small>
            <h2>{entry.title}</h2>
            <div class=\"btn-group\">
                <button class=\"btn-run\" onclick=\"copyMasterCommand('{mp3_link}', '{feed_name_attr}', '{date_param}', '{c_title}', '{lang_code}')\">⚡ Copy Process Command</button>
            </div>
        </div>"""

    output_filename = f"{feed_name_attr}.feed.html"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html_content + "</body></html>")
    
    return feed_name_attr, lang_code

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--lang", help="Override language code")
    args = parser.parse_args()
    
    # Critical: Return output for the master workflow
    fname, lcode = create_general_feed(args.url, args.lang)
    if fname and lcode:
        print(f"FEEDNAME_OUTPUT:{fname}")
        print(f"LANG_OUTPUT:{lcode}")

