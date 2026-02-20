import re, os, argparse, requests, whisper, json
from deep_translator import GoogleTranslator

def process_podcast(url):
    audio_file = "podcast.mp3"
    json_output = "transcript.json"
    
    # 1. Download
    print("Downloading...")
    r = requests.get(url, stream=True)
    with open(audio_file, 'wb') as f:
        for chunk in r.iter_content(8192): f.write(chunk)

    # 2. Transcribe with Timestamps
    print("Transcribing (this creates the timing data)...")
    model = whisper.load_model("base")
    result = model.transcribe(audio_file, language='sv')
    
    # 3. Translate Segments & Build Web Data
    translator = GoogleTranslator(source='sv', target='en')
    web_data = []

    print("Translating segments...")
    for seg in result['segments']:
        web_data.append({
            "start": seg['start'],
            "end": seg['end'],
            "sv": seg['text'].strip(),
            "en": translator.translate(seg['text'])
        })

    # 4. Save for Web
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(web_data, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Created {json_output} and kept {audio_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    process_podcast(args.url)

    
