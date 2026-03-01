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

def process_podcast(url, feedname, date, title, lang, num_utterances=None):
    audio_file = f"{feedname}.{date}.mp3"
    interleaved_audio_file = f"{feedname}.{date}.bilingual.mp3"
    json_output = f"transcript.{feedname}.{date}.json"
    html_output = f"{feedname}.{date}.html"
    
    # 1. Download
    print(f"Downloading: {audio_file}")
    r = requests.get(url, stream=True, timeout=30)
    with open(audio_file, 'wb') as f:
        for chunk in r.iter_content(8192): f.write(chunk)

    # 1.5 Load Audio
    print(f"[*] Loading audio for processing...")
    try:
        full_audio = AudioSegment.from_mp3(audio_file)
    except Exception as e:
        print(f"[!] Audio loading error: {e}")
        return

    # 2. Transcription
    print(f"[*] Transcribing in: {lang}...")
    model = whisper.load_model("small")
    segments = []
    
    if num_utterances:
        chunk_length_ms = 5 * 60 * 1000 
        current_pos = 0
        while len(segments) < num_utterances and current_pos < len(full_audio):
            chunk = full_audio[current_pos : current_pos + chunk_length_ms]
            chunk.export("temp_chunk.wav", format="wav")
            result = model.transcribe("temp_chunk.wav", language=lang)
            for s in result.get('segments', []):
                if s['text'].strip():
                    s['start'] += (current_pos / 1000)
                    s['end'] += (current_pos / 1000)
                    segments.append(s)
                    if len(segments) >= num_utterances: break
            current_pos += chunk_length_ms
            if os.path.exists("temp_chunk.wav"): os.remove("temp_chunk.wav")
        segments = segments[:num_utterances]
    else:
        full_audio.export("temp_full.wav", format="wav")
        result = model.transcribe("temp_full.wav", language=lang)
        segments = [s for s in result.get('segments', []) if s['text'].strip()]
        if os.path.exists("temp_full.wav"): os.remove("temp_full.wav")

    # 3. Translation
    print(f"[*] Translating {len(segments)} segments...")
    translator = GoogleTranslator(source=lang, target='en')
    all_source_text = [seg['text'].strip() for seg in segments]
    translated_en = []
    if all_source_text:
        batch_size = 25 
        for i in range(0, len(all_source_text), batch_size):
            batch = all_source_text[i:i + batch_size]
            try:
                batch_string = "\n".join(batch)
                translated_batch = translator.translate(batch_string)
                translated_en.extend(translated_batch.split('\n'))
            except:
                translated_en.extend(batch)

    # 3.5 Generate Interleaved Audio with Timestamps
    print("[*] Synthesizing interleaved track...")
    combined_audio = AudioSegment.empty()
    current_b_time = 0.0
    b_timestamps = []

    for i, seg in enumerate(segments):
        orig_text = seg['text'].strip()
        en_text = translated_en[i].strip() if i < len(translated_en) else ""
        seg_b_start = current_b_time
        
        try:
            # Source TTS
            tts_orig = gTTS(text=orig_text, lang=lang)
            fp_orig = BytesIO()
            tts_orig.write_to_fp(fp_orig)
            fp_orig.seek(0)
            orig_audio = AudioSegment.from_file(fp_orig, format="mp3")
            combined_audio += orig_audio
            current_b_time += (len(orig_audio) / 1000.0)
            
            combined_audio += AudioSegment.silent(duration=500)
            current_b_time += 0.5
            
            # English TTS
            if en_text:
                tts_en = gTTS(text=en_text, lang='en')
                fp_en = BytesIO()
                tts_en.write_to_fp(fp_en)
                fp_en.seek(0)
                en_audio = AudioSegment.from_file(fp_en, format="mp3")
                combined_audio += en_audio
                current_b_time += (len(en_audio) / 1000.0)
            
            combined_audio += AudioSegment.silent(duration=1000)
            seg_b_end = current_b_time
            current_b_time += 1.0
            
            b_timestamps.append({"b_start": round(seg_b_start, 2), "b_end": round(seg_b_end, 2)})
        except:
            b_timestamps.append({"b_start": 0, "b_end": 0})

    combined_audio.export(interleaved_audio_file, format="mp3")

    # 4. Save JSON
    web_data = []
    for i, seg in enumerate(segments):
        web_data.append({
            "start": round(seg['start'], 2),
            "end": round(seg['end'], 2),
            "b_start": b_timestamps[i]["b_start"],
            "b_end": b_timestamps[i]["b_end"],
            "orig": seg['text'].strip(),
            "en": translated_en[i].strip() if i < len(translated_en) else ""
        })
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(web_data, f, ensure_ascii=False, indent=2)
    
    # 5. HTML Template with dynamic timestamp logic
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
            .controls {{ background: #eee; padding: 12px; border-radius: 15px; margin-top: 10px; }}
            .row {{ display: flex; gap: 20px; padding: 15px; margin-bottom: 12px; background: white; border-radius: 12px; cursor: pointer; }}
            .row.highlight {{ background: #fffde7; border-left: 8px solid var(--accent); }}
            .orig {{ flex: 1; color: var(--primary); font-weight: 700; }}
            .en {{ flex: 1; color: #546e7a; font-style: italic; }}
        </style>
    </head>
    <body>
        <div class="header-box">
            <h1>{title}</h1>
            <div class="controls">
                <audio id="audio" controls src="{audio_file}"></audio>
                <button id="modeBtn" onclick="toggleMode()">🔊 Switch to Interleaved</button>
            </div>
        </div>
        <div id="transcript" style="padding: 20px;"></div>
        <script>
            const audio = document.getElementById('audio');
            const modeBtn = document.getElementById('modeBtn');
            const container = document.getElementById('transcript');
            const sources = {{ orig: "{audio_file}", bilingual: "{interleaved_audio_file}" }};
            let mode = 'orig';
            let data = [];

            function toggleMode() {{
                const isPlaying = !audio.paused;
                mode = (mode === 'orig') ? 'bilingual' : 'orig';
                audio.src = sources[mode];
                if (isPlaying) audio.play();
                modeBtn.innerText = mode === 'orig' ? '🔊 Switch to Interleaved' : '🌍 Switch to Podcast';
            }}

            fetch('{json_output}').then(r => r.json()).then(json => {{
                data = json;
                data.forEach((item, i) => {{
                    const row = document.createElement('div');
                    row.className = 'row'; row.id = 'row-' + i;
                    row.innerHTML = `<div class="orig">${{item.orig}}</div><div class="en">${{item.en}}</div>`;
                    row.onclick = () => {{ audio.currentTime = (mode === 'orig' ? item.start : item.b_start); audio.play(); }};
                    container.appendChild(row);
                }});
            }});

            audio.addEventListener('timeupdate', () => {{
                const now = audio.currentTime;
                data.forEach((item, i) => {{
                    const el = document.getElementById('row-' + i);
                    const s = (mode === 'orig') ? item.start : item.b_start;
                    const e = (mode === 'orig') ? item.end : item.b_end;
                    if (now >= s && now <= e) {{
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--feedname", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--lang", default="no")
    parser.add_argument("--num_utterances", type=int)
    args = parser.parse_args()
    process_podcast(args.url, args.feedname, args.date, args.title, args.lang, args.num_utterances)

