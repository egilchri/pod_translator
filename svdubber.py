import os
import json
import whisper
from deep_translator import GoogleTranslator
from gtts import gTTS
from pydub import AudioSegment

def process_dubbing(input_mp3, output_mp3, output_json):
    # 1. Transcribe (Get text and timestamps)
    print("Transcribing Swedish audio...")
    model = whisper.load_model("base")
    result = model.transcribe(input_mp3, language='sv')
    
    # Load original audio
    original_audio = AudioSegment.from_mp3(input_mp3)
    combined_audio = AudioSegment.empty()
    transcript_data = []
    
    translator = GoogleTranslator(source='sv', target='en')
    
    print(f"Processing {len(result['segments'])} segments...")
    
    last_end_time = 0
    
    for i, seg in enumerate(result['segments']):
        start_ms = int(seg['start'] * 1000)
        end_ms = int(seg['end'] * 1000)
        sv_text = seg['text'].strip()
        
        # Translate
        en_text = translator.translate(sv_text)
        print(f"[{i}] SV: {sv_text}")
        
        # 2. Generate English Speech (TTS)
        tts = gTTS(text=en_text, lang='en')
        temp_tts = f"temp_{i}.mp3"
        tts.save(temp_tts)
        en_audio = AudioSegment.from_mp3(temp_tts)
        
        # 3. Interleave Audio
        # Add the original Swedish segment
        swedish_segment = original_audio[start_ms:end_ms]
        combined_audio += swedish_segment
        
        # Add a small 500ms pause, then the English translation
        combined_audio += AudioSegment.silent(duration=500)
        combined_audio += en_audio
        combined_audio += AudioSegment.silent(duration=1000) # Pause before next sentence
        
        # 4. Collect Data for Transcript
        transcript_data.append({
            "start": start_ms / 1000,
            "sv": sv_text,
            "en": en_text
        })
        
        os.remove(temp_tts)

    # Export final results
    combined_audio.export(output_mp3, format="mp3")
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)
        
    print(f"\nSuccess! Created {output_mp3} and {output_json}")

if __name__ == "__main__":
    # Usage: input_file, output_audio, output_json
    process_dubbing("podcast.mp3", "dubbed_podcast.mp3", "transcript.json")

