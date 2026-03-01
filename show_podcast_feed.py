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

def process_podcast(url, feedname, lang, num_utterances=None):
    audio_file = f"{feedname}.mp3"
    interleaved_audio_file = f"{feedname}.bilingual.mp3"
    wav_file = f"{feedname}.wav"
    json_output = f"transcript.{feedname}.json"
    html_output = f"{feedname}.html"
    
    # 1. Download
    print(f"Downloading: {audio_file}")
    r = requests.get(url, stream=True, timeout=30)
    with open(audio_file, 'wb') as f:
        for chunk in r.iter_content(8192): f.write(chunk)

    # 1.5 Convert to WAV
    print(f"[*] Converting to WAV...")
    try:
        audio_seg = AudioSegment.from_mp3(audio_file)
        
        # OPTIMIZATION: If num_utterances is small, we could slice the audio here.
        # However, since we don't know the timestamps yet, we transcribe first.
        audio_seg.export(wav_file, format="wav")
    except Exception as e:
        print(f"[!] Conversion error: {e}")
        wav_file = audio_file

    # 2. Transcribe
    print(f"[*] Transcribing in: {lang}...")
    model = whisper.load_model("small")
    
    # We transcribe the file. Whisper is relatively fast, but we 
    # immediately slice the results to honor the num_utterances constraint.
    result = model.transcribe(wav_file, language=lang, verbose=False)
    
    if wav_file.endswith(".wav") and os.path.exists(wav_file):
        os.remove(wav_file)

    # Filter segments immediately
    segments = [seg for seg in result.get('segments', []) if seg['text'].strip()]
    if num_utterances:
        print(f"[*] Limiting processing to the first {num_utterances} utterances.")
        segments = segments[:num_utterances]

    # 3. Translation (Only processes the limited segments)
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
            except Exception as e:
                translated_en.extend(batch)

    # 3.5 Generate Interleaved Bilingual Audio (Only for the limited segments)
    print("[*] Synthesizing interleaved bilingual track...")
    combined_audio = AudioSegment.empty()
    
    for i, seg in enumerate(segments):
        orig_text = seg['text'].strip()
        en_text = translated_en[i].strip() if i < len(translated_en) else ""
        
        try:
            # Source Language
            tts_orig = gTTS(text=orig_text, lang=lang)
            fp_orig = BytesIO()
            tts_orig.write_to_fp(fp_orig)
            fp_orig.seek(0)
            combined_audio += AudioSegment.from_file(fp_orig, format="mp3")
            
            combined_audio += AudioSegment.silent(duration=500)
            
            # English Translation
            if en_text:
                tts_en = gTTS(text=en_text, lang='en')
                fp_en = BytesIO()
                tts_en.write_to_fp(fp_en)
                fp_en.seek(0)
                combined_audio += AudioSegment.from_file(fp_en, format="mp3")
            
            combined_audio += AudioSegment.silent(duration=1000)
            print(f"    - Synthesized {i+1}/{len(segments)}")
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
    
    # 5. HTML Generation (Omitted for brevity, but remains the same)
    # ... [Insert HTML template from previous response] ...

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--feedname", required=True)
    parser.add_argument("--lang", default="no")
    parser.add_argument("--num_utterances", type=int, help="Limit to first X utterances")
    args = parser.parse_args()
    process_podcast(args.url, args.feedname, args.lang, args.num_utterances)
    
