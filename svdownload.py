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
import time

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
        time.sleep(0.5) # Wait half a second between segments
        orig_text = seg['text'].strip()
        en_text = translated_en[i].strip() if i < len(translated_en) else ""
        seg_b_start = current_b_time
        
        try:
            # Source TTS
            tts_orig = gTTS(text=orig_text, lang=lang)
            fp_orig = BytesIO()
            tts_orig.write_to_fp(fp_orig)
            fp_orig.seek(0)
            orig_audio_seg = AudioSegment.from_file(fp_orig, format="mp3")
            combined_audio += orig_audio_seg
            current_b_time += (len(orig_audio_seg) / 1000.0)
            
            combined_audio += AudioSegment.silent(duration=500)
            current_b_time += 0.5
            
            # English TTS
            if en_text:
                tts_en = gTTS(text=en_text, lang='en')
                fp_en = BytesIO()
                tts_en.write_to_fp(fp_en)
                fp_en.seek(0)
                en_audio_seg = AudioSegment.from_file(fp_en, format="mp3")
                combined_audio += en_audio_seg
                current_b_time += (len(en_audio_seg) / 1000.0)
            
            # Final silence for the segment
            combined_audio += AudioSegment.silent(duration=1000)
            current_b_time += 1.0
            
            # The end of this row is the current time after silence
            seg_b_end = current_b_time
            b_timestamps.append({"b_start": round(seg_b_start, 2), "b_end": round(seg_b_end, 2)})
        except Exception as e:
            print(f"Error synthesizing segment {i}: {e}")
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
    
    # 5. Mobile-Friendly HTML Player
    html_template = f"""
    <!DOCTYPE html>
    <html lang="{lang}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>{title}</title>
        <style>
            :root {{ --primary: #004a99; --accent: #ffc107; --bg: #f0f2f5; }}
            body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0; background: var(--bg); }}
            .header-box {{ position: sticky; top: 0; background: rgba(255,255,255,0.98); padding: 15px; border-bottom: 3px solid var(--primary); z-index: 100; backdrop-filter: blur(10px); }}
            .controls {{ display: flex; flex-direction: column; gap: 10px; margin-top: 10px; background: #eee; padding: 12px; border-radius: 15px; }}
            .audio-row {{ display: flex; gap: 10px; align-items: center; }}
            audio {{ flex-grow: 1; height: 40px; }}
            .speed-row {{ display: flex; gap: 5px; align-items: center; justify-content: center; border-top: 1px solid #ccc; padding-top: 8px; }}
            .btn {{ background: var(--primary); color: white; border: none; padding: 8px 12px; border-radius: 20px; font-weight: bold; cursor: pointer; font-size: 0.75rem; }}
            .btn.active {{ background: var(--accent); color: black; }}
            .speed-btn {{ background: #fff; color: #333; border: 1px solid #ccc; padding: 4px 10px; border-radius: 12px; font-size: 0.7rem; cursor: pointer; }}
            .speed-btn.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
            .transcript {{ padding: 20px; max-width: 900px; margin: 0 auto; }}
            .row {{ display: flex; gap: 20px; padding: 15px; margin-bottom: 12px; background: white; border-radius: 12px; border: 1px solid #ddd; cursor: pointer; }}
            .row.highlight {{ background: #fffde7; border-left: 8px solid var(--accent); transition: background 0.3s ease; }}
            .orig {{ flex: 1; color: var(--primary); font-weight: 700; font-size: 1.1rem; }}
            .en {{ flex: 1; color: #546e7a; font-style: italic; border-left: 1px solid #eee; padding-left: 15px; font-size: 1.1rem; }}
            .status-badge {{ font-size: 0.7rem; margin-left: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; }}
            @media (max-width: 768px) {{ .row {{ flex-direction: column; gap: 10px; }} .en {{ border-left: none; border-top: 1px solid #eee; padding-top: 10px; }} }}
        </style>
    </head>
    <body>
        <div class="header-box">
            <small style="font-weight:bold; color:#666;">{feedname.upper()} | {date}</small>
            <h1 style="margin: 5px 0; font-size: 1.2rem;">
                {title} <span id="audio-status" class="status-badge"></span>
            </h1>
            <div class="controls">
                <div class="audio-row">
                    <audio id="audio" controls src="{audio_file}"></audio>
                    <button id="modeBtn" class="btn" onclick="toggleMode()">🌍 Interleaved</button>
                </div>
                <div class="speed-row">
                    <span style="font-size: 0.7rem; font-weight: bold; color: #555;">SPEED:</span>
                    <button class="speed-btn" onclick="setSpeed(0.5)">0.5x</button>
                    <button class="speed-btn" onclick="setSpeed(0.75)">0.75x</button>
                    <button class="speed-btn active" id="speed-1" onclick="setSpeed(1.0)">1x</button>
                    <button class="speed-btn" onclick="setSpeed(1.25)">1.25x</button>
                    <button class="speed-btn" onclick="setSpeed(1.5)">1.5x</button>
                </div>
            </div>
        </div>
        <div id="transcript" class="transcript"></div>
        <script>
            const audio = document.getElementById('audio');
            const modeBtn = document.getElementById('modeBtn');
            const statusEl = document.getElementById('audio-status');
            const container = document.getElementById('transcript');
            const sources = {{ orig: "{audio_file}", bilingual: "{interleaved_audio_file}" }};
            let mode = 'orig';
            let data = [];
            let lastIdx = -1;

            // Check if audio files are live on server
            async function checkAudioStatus() {{
                try {{
                    const response = await fetch(sources[mode], {{ method: 'HEAD' }});
                    if (response.ok) {{
                        statusEl.innerText = "● Live";
                        statusEl.style.color = "green";
                    }} else {{
                        statusEl.innerText = "○ Missing";
                        statusEl.style.color = "orange";
                    }}
                }} catch (e) {{
                    statusEl.innerText = "○ Offline";
                    statusEl.style.color = "red";
                }}
            }}

            function setSpeed(rate) {{
                audio.playbackRate = rate;
                document.querySelectorAll('.speed-btn').forEach(btn => {{
                    btn.classList.remove('active');
                    if (parseFloat(btn.innerText) === rate) btn.classList.add('active');
                }});
            }}

            function toggleMode() {{
                const isPlaying = !audio.paused;
                const rate = audio.playbackRate;
                mode = (mode === 'orig') ? 'bilingual' : 'orig';
                audio.src = sources[mode];
                audio.playbackRate = rate;
                lastIdx = -1; 
                checkAudioStatus();
                if (isPlaying) audio.play();
                modeBtn.innerText = mode === 'orig' ? '🌍 Interleaved' : '🎙️ Podcast';
                modeBtn.classList.toggle('active');
            }}

            checkAudioStatus();

            fetch('{json_output}').then(r => r.json()).then(json => {{
                data = json;
                data.forEach((item, i) => {{
                    const row = document.createElement('div');
                    row.className = 'row'; row.id = 'row-' + i;
                    row.innerHTML = `<div class=\"orig\">${{item.orig}}</div><div class=\"en\">${{item.en}}</div>`;
                    row.onclick = () => {{ 
                        audio.currentTime = (mode === 'orig') ? item.start : item.b_start; 
                        audio.play(); 
                    }};
                    container.appendChild(row);
                }});
            }});

            audio.addEventListener('timeupdate', () => {{
                const now = audio.currentTime;
                const currentIdx = data.findIndex(item => {{
                    const s = (mode === 'orig') ? item.start : item.b_start;
                    const e = (mode === 'orig') ? item.end : item.b_end;
                    return now >= s && now <= e;
                }});

                if (currentIdx !== lastIdx) {{
                    if (lastIdx !== -1) {{
                        const oldEl = document.getElementById('row-' + lastIdx);
                        if (oldEl) oldEl.classList.remove('highlight');
                    }}
                    if (currentIdx !== -1) {{
                        const newEl = document.getElementById('row-' + currentIdx);
                        if (newEl) {{
                            newEl.classList.add('highlight');
                            newEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }}
                    lastIdx = currentIdx;
                }}
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

