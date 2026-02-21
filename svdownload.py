import argparse
import requests
import whisper
import json
import warnings
from deep_translator import GoogleTranslator

# Suppress the urllib3/LibreSSL warning
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL 1.1.1+.*")

def process_podcast(url):
    audio_file = "podcast.mp3"
    json_output = "transcript.json"
    
    # 1. Download
    print(f"Downloading audio from: {url}")
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(audio_file, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
    else:
        print(f"Failed to download audio. Status code: {r.status_code}")
        return

    # 2. Transcribe with Whisper
    print("Transcribing with Whisper (preserving timestamps)...")
    # 'base' is good; if your Mac has the RAM, 'small' or 'medium' improves Swedish grammar
    model = whisper.load_model("base")
    result = model.transcribe(audio_file, language='sv')
    
    # 3. Process segments for Highlighting
    print("Translating segments and attaching timestamps...")
    translator = GoogleTranslator(source='sv', target='en')
    
    # Whisper's 'segments' list contains the timing data we need
    segments = result.get('segments', [])
    
    web_data = []
    for seg in segments:
        sv_text = seg['text'].strip()
        
        if sv_text:
            # We preserve start and end (in seconds) so the HTML player knows when to highlight
            web_data.append({
                "start": round(seg['start'], 2),
                "end": round(seg['end'], 2),
                "sv": sv_text,
                "en": translator.translate(sv_text)
            })

    # 4. Save for Web Player
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(web_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nSuccess! Created {json_output}")
    print(f"Processed {len(web_data)} timed segments.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download, transcribe, and translate with timing.")
    parser.add_argument("--url", required=True, help="The direct URL to the .mp3 file")
    args = parser.parse_args()
    
    process_podcast(args.url)

