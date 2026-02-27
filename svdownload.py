import argparse
import requests
import whisper
import json
import warnings
import os
from pydub import AudioSegment
from deep_translator import GoogleTranslator
from gtts import gTTS
from io import BytesIO

# Suppress warnings
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

def process_podcast(url, feedname, date, title, lang):
    audio_file = f"{feedname}.{date}.mp3"
    interleaved_audio_file = f"{feedname}.{date}.bilingual.mp3"
    wav_file = f"{feedname}.{date}.wav"
    json_output = f"transcript.{feedname}.{date}.json"
    html_output = f"{feedname}.{date}.html"
    
    # 1. Download
    print(f"Downloading: {audio_file}")
    r = requests.get(url, stream=True, timeout=30)
    with open(audio_file, 'wb') as f:
        for chunk in r.iter_content(8192): f.write(chunk)

    # 1.5 Convert to WAV
    print(f"[*] Converting to WAV...")
    try:
        audio_seg = AudioSegment.from_mp3(audio_file)
        audio_seg.export(wav_file, format="wav")
    except Exception as e:
        print(f"[!] Conversion error: {e}")
        wav_file = audio_file

    # 2. Transcribe
    print(f"[*] Transcribing in: {lang}...")
    model = whisper.load_model("base")
    result = model.transcribe(wav_file, language=lang, verbose=True)
    
    if wav_file.endswith(".wav") and os.path.exists(wav_file):
        os.remove(wav_file)

    # 3. Translation
    print("[*] Translating segments...")
    translator = GoogleTranslator(source=lang, target='en')
    segments = [seg for seg in result.get('segments', []) if seg['text'].strip()]
    all_source_text = [seg['text'].strip() for seg in segments]
    
    batch_size = 25 
    translated_en = []
    for i in range(0, len(all_source_text), batch_size):
        batch = all_source_text[i:i + batch_size]
        try:
            batch_string = "\n".join(batch)
            translated_batch = translator.translate(batch_string)
            translated_en.extend(translated_batch.split('\n'))
        except Exception as e:
            translated_en.extend(batch)

    # 3.5 Generate Interleaved Bilingual Audio
    print("[*] Synthesizing interleaved bilingual track...")
    combined_audio = AudioSegment.empty()
    
    for i, seg in enumerate(segments):
        orig_text = seg['text'].strip()
        en_text = translated_en[i].strip() if i < len(translated_en) else ""
        
        try:
            # Generate Source Language Audio
            tts_orig = gTTS(text=orig_text, lang=lang)
            fp_orig = BytesIO()
            tts_orig.write_to_fp(fp_orig)
            fp_orig.seek(0)
            combined_audio += AudioSegment.from_file(fp_orig, format="mp3")
            
            # Add a small pause (500ms)
            combined_audio += AudioSegment.silent(duration=500)
            
            # Generate English Translation Audio
            if en_text:
                tts_en = gTTS(text=en_text, lang='en')
                fp_en = BytesIO()
                tts_en.write_to_fp(fp_en)
                fp_en.seek(0)
                combined_audio += AudioSegment.from_file(fp_en, format="mp3")
            
            # Add longer pause between segments (1000ms)
            combined_audio += AudioSegment.silent(duration=1000)
            print(f"    - Synthesized segment {i+1}/{len(segments)}")
        except Exception as e:
            print(f"    [!] TTS error on segment {i}: {e}")

    combined_audio.export(interleaved_audio_file, format="mp3")

    # 4. Save JSON
    web_data = []
    for i, seg in enumerate(segments):
        web_data.append({
            "start": round(seg['start'], 2),
            "end": round(seg['end'], 2),
            "orig": seg['text'].strip(),
            "en": translated_en[i].strip() if i < len(translated_en) else ""
        })

    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(web_data, f, ensure_ascii=False, indent=2)
    
    # 5. HTML Template with Interleaved Toggle
# 5. HTML Template with Interleaved Toggle and Speed Slider
    html_template = f"""
    <!DOCTYPE html>
    <html lang="{lang}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            :root {{ --primary: #004a99; --accent: #ffc107; --bg: #f0f2f5; }}
            body {{ font-family: system-ui, sans-serif; margin: 0; background: var(--bg); }}
            .header-box {{ position: sticky; top: 0; background: white; padding: 15px; border-bottom: 3px solid var(--primary); z-index: 100; }}
            .controls {{ display: flex; gap: 15px; align-items: center; margin-top: 10px; flex-wrap: wrap; }}
            audio {{ flex-grow: 1; min-width: 300px; }}
            .speed-control {{ display: flex; align-items: center; gap: 8px; font-size: 0.9rem; font-weight: bold; color: var(--primary); }}
            .btn {{ background: var(--primary); color: white; border: none; padding: 10px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 0.8rem; }}
            .btn.active {{ background: var(--accent); color: black; }}
            .transcript {{ padding: 20px; max-width: 900px; margin: 0 auto; }}
            .row {{ display: flex; gap: 20px; padding: 15px; margin-bottom: 10px; background: white; border-radius: 8px; border: 1px solid #ddd; cursor: pointer; }}
            .row.highlight {{ background: #fffde7; border-left: 6px solid var(--accent); }}
            .orig {{ flex: 1; color: var(--primary); font-weight: bold; }}
            .en {{ flex: 1; color: #546e7a; font-style: italic; border-left: 1px solid #eee; padding-left: 15px; }}
        </style>
    </head>
    <body>
        <div class="header-box">
            <small>{feedname} | {date}</small>
            <h1>{title}</h1>
            <div class="controls">
                <audio id="audio" controls src="{audio_file}"></audio>
                
                <div class="speed-control">
                    <label for="speedSlider">Speed:</label>
                    <input type="range" id="speedSlider" min="0.5" max="2.0" step="0.1" value="1.0">
                    <span id="speedVal">1.0x</span>
                </div>

                <button id="modeBtn" class="btn" onclick="toggleMode()">🔊 Play Interleaved Track</button>
            </div>
        </div>
        <div id="transcript" class="transcript"></div>
        <script>
            const audio = document.getElementById('audio');
            const modeBtn = document.getElementById('modeBtn');
            const speedSlider = document.getElementById('speedSlider');
            const speedVal = document.getElementById('speedVal');
            const container = document.getElementById('transcript');
            const sources = {{ orig: "{audio_file}", bilingual: "{interleaved_audio_file}" }};
            let mode = 'orig';
            let data = [];

            // Speed Control Logic
            speedSlider.addEventListener('input', () => {{
                const val = speedSlider.value;
                audio.playbackRate = val;
                speedVal.innerText = val + 'x';
            }});

            function toggleMode() {{
                const isPlaying = !audio.paused;
                const currentSpeed = audio.playbackRate; // Preserve speed when switching tracks
                mode = (mode === 'orig') ? 'bilingual' : 'orig';
                audio.src = sources[mode];
                audio.playbackRate = currentSpeed; 
                if (isPlaying) audio.play();
                modeBtn.innerText = mode === 'orig' ? '🔊 Play Interleaved Track' : '🌍 Play Original Podcast';
                modeBtn.classList.toggle('active');
            }}

            fetch('{json_output}').then(r => r.json()).then(json => {{
                data = json;
                data.forEach((item, i) => {{
                    const row = document.createElement('div');
                    row.className = 'row'; row.id = 'row-' + i;
                    row.innerHTML = `<div class="orig">${{item.orig}}</div><div class="en">${{item.en}}</div>`;
                    row.onclick = () => {{ if(mode === 'orig') audio.currentTime = item.start; audio.play(); }};
                    container.appendChild(row);
                }});
            }});

            audio.addEventListener('timeupdate', () => {{
                if (mode !== 'orig') return;
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
    print(f"Success! Bilingual dashboard created at {html_output}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--feedname", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--lang", default="no")
    args = parser.parse_args()
    process_podcast(args.url, args.feedname, args.date, args.title, args.lang)

