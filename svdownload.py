import argparse
import requests
import whisper
import json
import warnings
from deep_translator import GoogleTranslator

# Suppress the urllib3/LibreSSL warning
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

def process_podcast(url, feedname, date, title):
    audio_file = f"{feedname}.{date}.mp3"
    json_output = f"transcript.{feedname}.{date}.json"
    html_output = f"{feedname}.{date}.html"
    
    # 1. Download
    print(f"Downloading: {audio_file}")
    r = requests.get(url, stream=True)
    with open(audio_file, 'wb') as f:
        for chunk in r.iter_content(8192): f.write(chunk)

    # 2. Transcribe
    print("Transcribing (preserving timestamps for highlighting)...")
    model = whisper.load_model("base")
    result = model.transcribe(audio_file, language='sv')
    
    # 3. Translate
    translator = GoogleTranslator(source='sv', target='en')
    web_data = []
    for seg in result.get('segments', []):
        if seg['text'].strip():
            web_data.append({
                "start": round(seg['start'], 2),
                "end": round(seg['end'], 2),
                "sv": seg['text'].strip(),
                "en": translator.translate(seg['text'])
            })

    # 4. Save JSON
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(web_data, f, ensure_ascii=False, indent=2)
    
    # 5. Side-by-Side Player HTML
    html_template = f"""
    <!DOCTYPE html>
    <html lang="sv">
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
        <style>
            body {{ font-family: system-ui, sans-serif; max-width: 1000px; margin: 0 auto; padding: 30px; background: #f8f9fa; }}
            .header-box {{ background: white; padding: 30px; border-radius: 12px; margin-bottom: 25px; position: sticky; top: 0; z-index: 100; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            .row {{ display: flex; gap: 20px; padding: 12px; border-bottom: 1px solid #eee; cursor: pointer; transition: 0.2s; }}
            .row:hover {{ background: #f0f0f0; }}
            .row.highlight {{ background: #fff9c4; border-left: 6px solid #fbc02d; font-weight: bold; }}
            .sv, .en {{ flex: 1; font-size: 1.1em; }}
        </style>
    </head>
    <body>
        <div class="header-box">
            <small style="text-transform:uppercase; color:#666;">{feedname} | {date}</small>
            <h1>{title}</h1>
            <audio id="audio" controls src="{audio_file}" style="width:100%; margin-top:15px;"></audio>
        </div>
        <div id="transcript"></div>
        <script>
            const audio = document.getElementById('audio');
            const container = document.getElementById('transcript');
            let data = [];

            fetch('{json_output}').then(r => r.json()).then(json => {{
                data = json;
                data.forEach((item, i) => {{
                    const row = document.createElement('div');
                    row.className = 'row'; row.id = 'row-' + i;
                    row.innerHTML = `<div class="sv">${{item.sv}}</div><div class="en">${{item.en}}</div>`;
                    row.onclick = () => audio.currentTime = item.start;
                    container.appendChild(row);
                }});
            }});

            audio.addEventListener('timeupdate', () => {{
                data.forEach((item, i) => {{
                    const el = document.getElementById('row-' + i);
                    if (audio.currentTime >= item.start && audio.currentTime <= item.end) {{
                        el.classList.add('highlight');
                        if (!el.dataset.seen) {{ el.scrollIntoView({{behavior:'smooth', block:'center'}}); el.dataset.seen='1'; }}
                    }} else {{ el.classList.remove('highlight'); delete el.dataset.seen; }}
                }});
            }});
        </script>
    </body></html>
    """
    with open(html_output, 'w', encoding='utf-8') as f: f.write(html_template)
    print(f"Success! Final player created at {html_output}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--feedname", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()
    process_podcast(args.url, args.feedname, args.date, args.title)
    
