import re
import os
import argparse
import requests
import whisper
from deep_translator import GoogleTranslator

def download_mp3(url, output_filename):
    print(f"Downloading audio from {url}...")
    try:
        # Added a 30-second timeout for the connection
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status() # Check for HTTP errors
        
        with open(output_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
        return True
    except Exception as e:
        print(f"Failed to download: {e}")
        return False

def transcribe_audio(audio_file, text_file):
    print("Loading Whisper model...")
    # 'turbo' is the latest fast/accurate model, or use 'base' for lower RAM usage
    model = whisper.load_model("base")
    
    print("Transcribing Swedish audio...")
    result = model.transcribe(audio_file, language='sv')
    
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(result['text'])
    
    print(f"Transcription saved to {text_file}")
    return result['text']

def translate_and_interleave(content):
    translator = GoogleTranslator(source='sv', target='en')
    
    # Split into sentences based on punctuation
    sentences = re.split(r'(?<=[.!?])\s+', content)
    print(f"\nFound {len(sentences)} sentences. Starting translation...\n")

    for sentence in sentences:
        clean_sv = sentence.strip()
        if not clean_sv:
            continue
        
        try:
            english_text = translator.translate(clean_sv)
            print(f"SV: {clean_sv}")
            print(f"EN: {english_text}")
            print("-" * 40)
        except Exception as e:
            print(f"[Error translating]: {e}")

def main():
    # Setup command line argument parsing
    parser = argparse.ArgumentParser(description="Download, Transcribe, and Translate Swedish Podcasts.")
    parser.add_argument("--url", required=True, help="The direct URL to the podcast .mp3 file")
    args = parser.parse_args()

    base_name = "podcast_episode"
    audio_file = f"{base_name}.mp3"
    transcript_file = f"{base_name}.sv.txt"

    # Execute Workflow
    if download_mp3(args.url, audio_file):
        try:
            sv_text = transcribe_audio(audio_file, transcript_file)
            translate_and_interleave(sv_text)
        finally:
            if os.path.exists(audio_file):
                os.remove(audio_file)
                print(f"\nCleaned up temporary file: {audio_file}")

if __name__ == "__main__":
    main()

    
