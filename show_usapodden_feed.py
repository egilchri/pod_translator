import feedparser
from datetime import datetime
import re

def clean_text(text):
    """Cleans text for safe command-line usage."""
    if not text: return ""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    return " ".join(text.split()).replace('"', '\\"').replace("'", "\\'")

def create_html_feed(url):
    print(f"Fetching feed: {url}")
    feed = feedparser.parse(url)
    if feed.bozo: return

    # Updated: Points to the top level of the pod_tran repo
    base_gh_url = "https://egilchri.github.io/pod_tran"
    feed_name_attr = "usapodden"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="sv">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{feed.feed.title} - Master Workflow</title>
        <style>
            body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f0f2f5; }}
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
            function copyMasterCommand(mp3Url, feedname, date, title) {{
                const cmd = `python3 ./run_workflow.py --url "${{mp3Url}}" --feedname "${{feedname}}" --date "${{date}}" --title "${{title}}"`;
                navigator.clipboard.writeText(cmd).then(() => {{
                    const t = document.getElementById('toast');
                    t.style.display = 'block';
                    setTimeout(() => {{ t.style.display = 'none'; }}, 3000);
                }});
            }}
        </script>
    </head>
    <body>
        <header>
            <h1>{feed.feed.title}</h1>
            <p>Master Workflow Dashboard</p>
        </header>
        <div id="toast" class="toast">✅ Master Command Copied!</div>
    """

    for entry in feed.entries[:15]:
        dt = datetime(*entry.published_parsed[:6])
        date_param = dt.strftime("%y%m%d")
        mp3_link = next((en.href for en in entry.enclosures if en.type == 'audio/mpeg'), "")
        c_title = clean_text(entry.title)
        
        # Construct the live URL pointing to the top level
        live_url = f"{base_gh_url}/{feed_name_attr}.{date_param}.html"

        html_content += f"""
        <div class="episode-card">
            <small style="color:#666; font-weight:bold;">{dt.strftime("%B %d, %Y")}</small>
            <h2>{entry.title}</h2>
            <div class="summary">{entry.summary}</div>
            <div class="btn-group">
                <button class="btn btn-run" onclick="copyMasterCommand('{mp3_link}', '{feed_name_attr}', '{date_param}', '{c_title}')">
                    ⚡ TransViewer (Cmd)
                </button>
                <a href="{live_url}" target="_blank" class="btn btn-view">🌐 View Live</a>
                <a href="{mp3_link}" target="_blank" class="btn btn-listen">🎧 Preview MP3</a>
            </div>
        </div>
        """

    with open("ipodden.feed.html", "w", encoding="utf-8") as f:
        f.write(html_content + "</body></html>")
    print("Success! Dashboard updated with top-level 'View Live' buttons.")

if __name__ == "__main__":
    create_html_feed("https://api.sr.se/api/rss/pod/itunes/22712")

