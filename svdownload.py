import re
import os
import argparse
import requests
import whisper
import json
import warnings
import nltk
from deep_translator import GoogleTranslator

# Suppress the urllib3/LibreSSL warning for a cleaner output
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL 1.1.1+.*")

# Ensure the NLTK sentence tokenizer is available
try:
    # We now check for 'punkt_tab' which is required for newer NLTK versions
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    print("Downloading updated NLTK punctuation data (punkt_tab)...")
    nltk.download('punkt_tab')
    # Some older environments still look for the original 'punkt'
    nltk.download('punkt')

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
    print("Transcribing with Whisper (this may take a minute)...")
    # 'base' is a good balance of speed and accuracy. Use 'medium' for better Swedish.
    model = whisper.load_model("base")
    result = model.transcribe(audio_file, language='sv')
    
    # 3. Re-group into Utterances (Sentences)
    print("Processing utterances and translating...")
    translator = GoogleTranslator(source='sv', target='en')
    full_text = result['text']
    
    # Split the massive block of text into actual sentences
    utterances = nltk.sent_tokenize(full_text, language='swedish')
    
    web_data = []
    for sentence in utterances:
        clean_sentence = sentence.strip()
        if clean_sentence:
            web_data.append({
                "sv": clean_sentence,
                "en": translator.translate(clean_sentence)
            })

    # 4. Save for Web Player
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(web_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nSuccess! Created {json_output}")
    print(f"Processed {len(web_data)} utterances.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download, transcribe, and translate Swedish podcasts.")
    parser.add_argument("--url", required=True, help="The direct URL to the .mp3 file")
    args = parser.parse_args()
    
    process_podcast(args.url)

