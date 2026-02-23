import argparse
import requests
import whisper
import json
import warnings
import os
from pydub import AudioSegment
from deep_translator import GoogleTranslator

# Suppress the urllib3/LibreSSL warning
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

def process_podcast(url, feedname, date, title):
    audio_file = f"{feedname}.{date}.mp3"
    wav_file = f"{feedname}.{date}.wav"
    json_output = f"transcript.{feedname}.{date}.json"
    html_output = f"{feedname}.{date}.html"
    
    # 1. Download
    print(f"Downloading: {audio_file}")
    r = requests.get(url, stream=True, timeout=30)
    with open(audio_file, 'wb') as f:
        for chunk in r.iter_content(8192): f.write(chunk)

    # 1.5 Convert to WAV (Prevents Whisper hangs on Mac/CPU)
    print(f"[*] Converting to WAV for stability...")
    try:
        audio_seg = AudioSegment.from_mp3(audio_file)
        audio_seg.export(wav_file, format="wav")
    except Exception as e:
        print(f"[!] Conversion error: {e}. Falling back to MP3.")
        wav_file = audio_file

    # 2. Transcribe
    print("[*] Transcribing (Live Progress enabled)...")
    model = whisper.load_model("base")
    # verbose=True shows segments in terminal to confirm script is active
    result = model.transcribe(wav_file, language='sv', verbose=True)
    
    if wav_file.endswith(".wav") and os.path.exists(wav_file):
        os.remove(wav_file)

    # 3. Batch Translation (Drastically faster than line-by-line)
    print("[*] Translating segments (Batch Mode)...")
    translator = GoogleTranslator(source='sv', target='en')
    web_data = []
    
    # Filter for segments that actually contain text
    segments = [seg for seg in result.get('segments', []) if seg['text'].strip()]
    all_sv_text = [seg['text'].strip() for seg in segments]
    
    batch_size = 25 # Translates 25 lines per network request
    translated_en = []
    
    for i in range(0, len(all_sv_text), batch_size):
        batch = all_sv_text[i:i + batch_size]
        try:
            # Join with newline; Google handles blocks of text much faster than individual lines
            batch_string = "\n".join(batch)
            translated_batch = translator.translate(batch_string)
            # Split back into individual lines, preserving the sequence
            translated_en.extend(translated_batch.split('\n'))
            print(f"    - Processed {min(i + batch_size, len(all_sv_text))}/{len(all_sv_text)} lines...")
        except Exception as e:
            print(f"    [!] Translation error in batch {i}: {e}")
            # Fallback to Swedish if a specific batch fails
            translated_en.extend(batch)

    # 4. Save JSON (Aligning timestamps with translated text)
    for i, seg in enumerate(segments):
        en_text = translated_en[i].strip() if i < len(translated_en) else "[Translation Missing]"
        web_data.append({
            "start": round(seg['start'], 2),
            "end": round(seg['end'], 2),
            "sv": seg['text'].strip(),
            "en": en_text
        })

    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(web_data, f, ensure_ascii=False, indent=2)
    
    # 5. Mobile-Friendly Side-by-Side Player HTML
    html_template = f"""
    <!DOCTYPE html>
    <html lang="sv">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>{title}</title>
        <style>
            :root {{
                --primary-bg: #f0f2f5;
                --header-bg: rgba(255, 255, 255, 0.98);
                --highlight-bg: #fffde7;
                --highlight-border: #fbc02d;
                --sv-color: #004a99;
                --en-color: #546e7a;
            }}
            body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 0; background: var(--primary-bg); line-height: 1.6; }}
            .header-box {{ position: sticky; top: 0; background: var(--header-bg); backdrop-filter: blur(12px); padding: 20px; border-bottom: 3px solid #004a99; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
            h1 {{ font-size: 1.4rem; margin: 5px 0 15px 0; color: #1a1a1a; }}
            small {{ text-transform: uppercase; color: #666; font-weight: bold; font-size: 0.8rem; letter-spacing: 1px; }}
            .player-wrapper {{ background: #e9ecef; padding: 12px; border-radius: 50px; border: 2px solid #ced4da; display: flex; align-items: center; }}
            audio {{ width: 100%; height: 54px; }}
            .transcript {{ padding: 20px; max-width: 1100px; margin: 0 auto; }}
            .row {{ display: flex; gap: 25px; padding: 20px; margin-bottom: 12px; border-radius: 12px; background: #fff; border: 1px solid #dee2e6; transition: all 0.3s ease; cursor: pointer; -webkit-tap-highlight-color: transparent; }}
            .row.highlight {{ background: var(--highlight-bg); border-left: 8px solid var(--highlight-border); transform: scale(1.01); box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
            .sv, .en {{ flex: 1; font-size: 1.15rem; }}
            .sv {{ color: var(--sv-color); font-weight: 700; }}
            .en {{ color: var(--en-color); font-style: italic; border-left: 1px solid #eee; padding-left: 15px; }}
            @media (max-width: 768px) {{
                .row {{ flex-direction: column; gap: 10px; padding: 15px; }}
                .en {{ border-left: none; padding-left: 0; border-top: 1px solid #eee; padding-top: 10px; }}
                h1 {{ font-size: 1.2rem; }}
                .sv, .en {{ font-size: 1.1rem; }}
                .transcript {{ padding: 10px; }}
                .header-box {{ padding: 15px; }}
            }}
        </style>
    </head>
    <body>
        <div class="header-box">
            <small>{feedname} | {date}</small>
            <h1>{title}</h1>
            <div class="player-wrapper">
                <audio id="audio" controls src="{audio_file}"></audio>
            </div>
        </div>
        <div id="transcript" class="transcript"></div>
        <script>
            const audio = document.getElementById('audio');
            const container = document.getElementById('transcript');
            let data = [];
            fetch('{json_output}').then(r => r.json()).then(json => {{
                data = json;
                data.forEach((item, i) => {{
                    const row = document.createElement('div');
                    row.className = 'row'; 
                    row.id = 'row-' + i;
                    row.innerHTML = `<div class="sv">${{item.sv}}</div><div class="en">${{item.en}}</div>`;
                    row.onclick = () => {{ audio.currentTime = item.start; audio.play(); }};
                    container.appendChild(row);
                }});
            }});
            audio.addEventListener('timeupdate', () => {{
                const now = audio.currentTime;
                data.forEach((item, i) => {{
                    const el = document.getElementById('row-' + i);
                    if (now >= item.start && now <= item.end) {{
                        el.classList.add('highlight');
                        if (!el.dataset.seen) {{ el.scrollIntoView({{ behavior: 'smooth', block: 'center' }}); el.dataset.seen = '1'; }}
                    }} else {{ el.classList.remove('highlight'); delete el.dataset.seen; }}
                }});
            }});
        </script>
    </body>
    </html>
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

