import argparse
import requests
import whisper
import json
import warnings
import os
import re
import spacy
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydub import AudioSegment
from deep_translator import GoogleTranslator
from gtts import gTTS
from io import BytesIO
import time

SPACY_MODELS = {
    "sv": "sv_core_news_lg",
    "no": "nb_core_news_sm",
    "da": "da_core_news_sm",
    "de": "de_core_news_sm",
    "fr": "fr_core_news_sm",
    "es": "es_core_news_sm",
    "pt": "pt_core_news_sm",
    "it": "it_core_news_sm",
}


COGNET_PATH = os.path.join(os.path.dirname(__file__), "sv_en_cognates.json")
FOLKETS_PATH = os.path.join(os.path.dirname(__file__), "folkets_words.json")
_cognet_cache = None
_folkets_cache = None

def _load_cognet():
    global _cognet_cache
    if _cognet_cache is None:
        if os.path.exists(COGNET_PATH):
            with open(COGNET_PATH, encoding="utf-8") as f:
                _cognet_cache = json.load(f)
        else:
            _cognet_cache = {}
    return _cognet_cache

def _load_folkets():
    global _folkets_cache
    if _folkets_cache is None:
        if os.path.exists(FOLKETS_PATH):
            with open(FOLKETS_PATH, encoding="utf-8") as f:
                _folkets_cache = set(json.load(f))
        else:
            _folkets_cache = set()
    return _folkets_cache


WIKTIONARY_LANG_HEADERS = {
    "sv": "Swedish", "no": "Norwegian", "da": "Danish",
    "de": "German",  "fr": "French",   "es": "Spanish",
    "pt": "Portuguese", "it": "Italian",
}

ETYMOLOGY_POS = {"NOUN", "VERB", "ADJ", "ADV", "PROPN"}


def _render_template(m):
    """Render a wiki template to readable text or empty string."""
    content = m.group(1)
    parts = [p.strip() for p in content.split("|")]
    name = parts[0].lower()

    # Etymology link templates: {{inh|lang|source-lang|word|...}} → the word
    # e.g. {{inh|sv|non|land}} → "land"
    if name in ("inh", "der", "bor", "inh+", "der+", "bor+"):
        # Structure: {{inh|target-lang|source-lang|word|...}} — skip 2 lang codes
        positional = [p for p in parts[1:] if "=" not in p and p]
        return positional[2] if len(positional) > 2 else ""
    if name in ("cog", "m", "l", "m+", "l+"):
        # Structure: {{cog|source-lang|word|...}} — skip 1 lang code
        positional = [p for p in parts[1:] if "=" not in p and p]
        # Skip placeholder "-" which means "no word"
        word = positional[1] if len(positional) > 1 else ""
        return word if word != "-" else ""

    # Ignore purely structural/cross-reference templates
    if name in ("ux", "uxi", "q", "qualifier", "sense", "lb", "label", "root", "wp", "wikipedia", "dercat", "etymon"):
        return ""

    # For anything else, take last positional non-empty arg
    positional = [p for p in parts[1:] if "=" not in p and p]
    return positional[-1] if positional else ""


def _clean_wikitext(text):
    """Strip wiki templates and markup, return plain text."""
    text = re.sub(r"\{\{([^}]+)\}\}", _render_template, text)
    # Drop [[link|label]] -> label, [[link]] -> link
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    # Drop HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Drop isolated tokens before "From" at the start (e.g. "*lendʰ- From", "gem-pro From")
    text = re.sub(r"^([^\s]+ )+(?=From )", "", text)
    # Drop empty "from" references (e.g. "From, from" → "From")
    text = re.sub(r"\bfrom,\s*", "from ", text, flags=re.IGNORECASE)
    # Fix punctuation spacing artifacts (e.g. " ," → ",")
    text = re.sub(r"\s+([,.])", r"\1", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_etymology(word, lang):
    """Fetch etymology for a word from English Wiktionary. Returns '' on failure."""
    lang_header = WIKTIONARY_LANG_HEADERS.get(lang, "")
    if not lang_header:
        return ""
    try:
        url = "https://en.wiktionary.org/w/api.php"
        params = {
            "action": "query", "titles": word, "prop": "revisions",
            "rvprop": "content", "rvslots": "main", "format": "json",
        }
        resp = requests.get(url, params=params, timeout=10,
                            headers={"User-Agent": "PodTranslator/1.0"})
        pages = resp.json().get("query", {}).get("pages", {})
        wikitext = next(iter(pages.values()), {}).get("revisions", [{}])[0].get(
            "slots", {}).get("main", {}).get("*", "")

        # Find the language section
        if not wikitext:
            return {"etymology": "", "cognate": "", "wiktionary": False}
        lang_match = re.search(rf"==\s*{re.escape(lang_header)}\s*==(.+?)(?:^==\w|\Z)",
                               wikitext, re.S | re.M)
        if not lang_match:
            return {"etymology": "", "cognate": "", "wiktionary": False}

        lang_section = lang_match.group(1)

        # Find Etymology subsection
        etym_match = re.search(r"===\s*Etymology[^=]*===\s*\n(.+?)(?:===|\Z)",
                               lang_section, re.S)
        if not etym_match:
            return ""

        # Extract English cognates: {{cog|en|word}} and ||gloss in inh/der/bor templates
        cog_matches = re.findall(r'\{\{cog\|en\|([^|}\n]+)', lang_section)
        gloss_matches = re.findall(r'\{\{(?:inh|der|bor)[+]?\|sv\|[^|]+\|[^|]*\|\|([^|}\n,]+)', lang_section)
        candidates = [c.strip() for c in cog_matches + gloss_matches
                      if c.strip() and c.strip() != '-'
                      and ' ' not in c.strip()
                      and not c.strip().startswith('*')]
        cognate = candidates[0] if candidates else ""

        etymology = ""
        if etym_match:
            raw = etym_match.group(1).strip()
            cleaned = _clean_wikitext(raw)
            etymology = cleaned[:220] if len(cleaned) > 220 else cleaned

        return {"etymology": etymology, "cognate": cognate, "wiktionary": True}
    except Exception:
        return {"etymology": "", "cognate": "", "wiktionary": False}


ETYMOLOGY_CACHE_PATH = os.path.join(os.path.dirname(__file__), "etymology_cache.json")


def _load_etymology_cache():
    if os.path.exists(ETYMOLOGY_CACHE_PATH):
        with open(ETYMOLOGY_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_etymology_cache(cache):
    with open(ETYMOLOGY_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def fetch_etymologies(lemmas, lang):
    """Fetch etymologies for a list of lemmas, using local cache where available."""
    cache = _load_etymology_cache()
    etymologies = {}
    to_fetch = []

    for lemma in lemmas:
        key = f"{lang}:{lemma}"
        if key in cache:
            val = cache[key]
            # Handle old cache entries that stored plain strings
            etymologies[lemma] = val if isinstance(val, dict) else {"etymology": val, "cognate": ""}
        else:
            to_fetch.append(lemma)

    if to_fetch:
        print(f"[*] Cache: {len(lemmas) - len(to_fetch)} hits, fetching {len(to_fetch)} from Wiktionary...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_etymology, lemma, lang): lemma for lemma in to_fetch}
            for future in as_completed(futures):
                lemma = futures[future]
                try:
                    result = future.result()
                    if not isinstance(result, dict):
                        result = {"etymology": "", "cognate": ""}
                except Exception:
                    result = {"etymology": "", "cognate": ""}
                etymologies[lemma] = result
                # Only cache successful lookups; retry empty results next run
                if result.get("cognate") or result.get("etymology"):
                    cache[f"{lang}:{lemma}"] = result
        _save_etymology_cache(cache)
    else:
        print(f"[*] Cache: all {len(lemmas)} etymologies served from cache")

    return etymologies


def build_vocabulary(segments, lang):
    model_name = SPACY_MODELS.get(lang)
    if not model_name:
        print(f"[!] No spacy model configured for lang '{lang}', skipping vocab.")
        return {}
    try:
        nlp = spacy.load(model_name)
    except OSError:
        print(f"[!] spacy model '{model_name}' not installed, skipping vocab. Run: python3 -m spacy download {model_name}")
        return {}

    full_text = " ".join(seg['text'].strip() for seg in segments)
    doc = nlp(full_text)

    # Collect lemma counts and surface forms per POS
    # pos -> lemma -> {count, forms}
    pos_lemmas = {}
    for token in doc:
        if token.is_punct or token.is_space or token.is_digit or token.pos_ == "NUM":
            continue
        pos = token.pos_
        lemma = token.lemma_.lower()
        form = token.text.lower()
        if pos not in pos_lemmas:
            pos_lemmas[pos] = {}
        if lemma not in pos_lemmas[pos]:
            pos_lemmas[pos][lemma] = {"count": 0, "forms": set()}
        pos_lemmas[pos][lemma]["count"] += 1
        pos_lemmas[pos][lemma]["forms"].add(form)

    # Translate all unique lemmas in batches
    all_lemmas = sorted({lemma for entries in pos_lemmas.values() for lemma in entries})
    print(f"[*] Translating {len(all_lemmas)} unique vocabulary lemmas...")
    translator = GoogleTranslator(source=lang, target='en')
    translations = {}
    batch_size = 25
    for i in range(0, len(all_lemmas), batch_size):
        batch = all_lemmas[i:i + batch_size]
        try:
            result = translator.translate("\n".join(batch))
            for lemma, trans in zip(batch, result.split("\n")):
                translations[lemma] = trans.strip()
        except Exception as e:
            print(f"[!] Vocab translation error: {e}")
            for lemma in batch:
                translations[lemma] = ""

    # Look up cognates: CogNet first, Wiktionary for misses
    cognet = _load_cognet() if lang == "sv" else {}
    folkets = _load_folkets() if lang == "sv" else set()
    etym_lemmas = [l for pos, entries in pos_lemmas.items()
                   if pos in ETYMOLOGY_POS for l in entries]
    cognet_hits = {l: cognet[l] for l in etym_lemmas if l in cognet}
    wikt_lemmas = [l for l in etym_lemmas if l not in cognet]
    print(f"[*] CogNet: {len(cognet_hits)} cognates found; fetching {len(wikt_lemmas)} from Wiktionary...")
    etymologies = fetch_etymologies(wikt_lemmas, lang)
    # Merge: CogNet cognates override Wiktionary; assume Wiktionary entry exists for CogNet words
    for lemma, cognate in cognet_hits.items():
        etymologies[lemma] = {
            "cognate": cognate,
            "etymology": etymologies.get(lemma, {}).get("etymology", ""),
            "wiktionary": True,
        }

    # Assemble final structure: grouped by POS, sorted by frequency descending
    vocab = {}
    for pos, lemmas in sorted(pos_lemmas.items()):
        vocab[pos] = [
            {
                "word": lemma,
                "translation": translations.get(lemma, ""),
                "count": data["count"],
                "forms": sorted(data["forms"]),
                "cognate": etymologies.get(lemma, {}).get("cognate", ""),
                "etymology": etymologies.get(lemma, {}).get("etymology", ""),
                "folkets": lemma in folkets,
            }
            for lemma, data in sorted(lemmas.items(), key=lambda x: (-x[1]["count"], x[0]))
        ]

    return vocab

# Suppress warnings
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

def process_podcast(url, feedname, date, title, lang, num_utterances=None, wordlist_only=False, html_only=False, start_pattern=None, staging=False):
    audio_file = f"{feedname}.{date}.mp3"
    interleaved_audio_file = f"{feedname}.{date}.bilingual.mp3"
    json_output = f"transcript.{feedname}.{date}.json"
    vocab_output = f"vocab.{feedname}.{date}.json"
    html_output = f"{feedname}.{date}.html"
    
    # Shortcut: if --html-only, just regenerate the HTML and exit
    asset_prefix = "../" if staging else ""
    if html_only:
        print(f"[*] --html-only: regenerating {html_output} from existing JSON files...")
        with open(html_output, 'w', encoding='utf-8') as f:
            f.write(build_html(feedname, date, title, lang, asset_prefix + audio_file, asset_prefix + interleaved_audio_file, asset_prefix + json_output, asset_prefix + vocab_output, start_pattern))
        print(f"[*] Done. Created {html_output}")
        return

    # Shortcut: if --wordlist-only and transcript already exists, load it directly
    podcasts_transcript = os.path.join("Podcasts", json_output)
    if wordlist_only and os.path.exists(podcasts_transcript):
        print(f"[*] --wordlist-only: loading existing transcript from {podcasts_transcript}")
        with open(podcasts_transcript, encoding="utf-8") as f:
            existing = json.load(f)
        if start_pattern:
            pattern_lower = start_pattern.lower()
            match_idx = next((i for i, e in enumerate(existing) if pattern_lower in e['orig'].lower()), None)
            if match_idx is None:
                print(f"[!] Warning: start pattern '{start_pattern}' not found. Using all segments.")
            else:
                print(f"[*] Start pattern found at segment {match_idx + 1}. Skipping {match_idx} preceding segments.")
                existing = existing[match_idx:]
            with open(json_output, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            print(f"[*] Saved filtered transcript -> {json_output}")
        segments = [{"text": entry["orig"]} for entry in existing]
        vocab = build_vocabulary(segments, lang)
        with open(vocab_output, 'w', encoding='utf-8') as f:
            json.dump(vocab, f, ensure_ascii=False, indent=2)
        total_words = sum(len(v) for v in vocab.values())
        print(f"[*] Vocabulary: {total_words} unique words across {len(vocab)} parts of speech -> {vocab_output}")
        return

    # 1. Download
    print(f"Downloading: {audio_file}")
    r = requests.get(url, stream=True, timeout=30,
                     headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
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
    print(f"[*] Loading Whisper model ('small')...")
    model = whisper.load_model("small")
    segments = []

    if num_utterances:
        print(f"[*] Transcribing first {num_utterances} utterances in: {lang}...")
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
        print(f"[*] Transcribing full audio in: {lang} (this may take a while)...")
        full_audio.export("temp_full.wav", format="wav")
        result = model.transcribe("temp_full.wav", language=lang)
        segments = [s for s in result.get('segments', []) if s['text'].strip()]
        if os.path.exists("temp_full.wav"): os.remove("temp_full.wav")

    # 2.5 Apply start pattern filter
    if start_pattern:
        pattern_lower = start_pattern.lower()
        match_idx = next((i for i, s in enumerate(segments) if pattern_lower in s['text'].lower()), None)
        if match_idx is None:
            print(f"[!] Warning: start pattern '{start_pattern}' not found. Processing all segments.")
        else:
            print(f"[*] Start pattern found at segment {match_idx + 1}. Skipping {match_idx} preceding segments.")
            segments = segments[match_idx:]

    # 2.6 Build Vocabulary
    print(f"[*] Building vocabulary from {len(segments)} segments...")
    vocab = build_vocabulary(segments, lang)
    with open(vocab_output, 'w', encoding='utf-8') as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)
    total_words = sum(len(v) for v in vocab.values())
    print(f"[*] Vocabulary: {total_words} unique words across {len(vocab)} parts of speech -> {vocab_output}")

    if wordlist_only:
        print(f"[*] --wordlist-only: done. Skipping audio synthesis and HTML generation.")
        return

    # 3. Translation
    total_to_translate = len(segments)
    print(f"[*] Translating {total_to_translate} segments...")
    translator = GoogleTranslator(source=lang, target='en')
    all_source_text = [seg['text'].strip() for seg in segments]
    translated_en = []
    if all_source_text:
        batch_size = 25 
        for i in range(0, len(all_source_text), batch_size):
            current_batch_num = (i // batch_size) + 1
            total_batches = (len(all_source_text) + batch_size - 1) // batch_size
            print(f"    > Translating batch {current_batch_num} of {total_batches}...")
            
            batch = all_source_text[i:i + batch_size]
            try:
                batch_string = "\n".join(batch)
                translated_batch = translator.translate(batch_string)
                translated_en.extend(translated_batch.split('\n'))
            except Exception as e:
                print(f"      [!] Translation error in batch {current_batch_num}: {e}")
                translated_en.extend(batch)

    # 3.5 Generate Interleaved Audio with Timestamps
    total_segments = len(segments)
    print(f"[*] Synthesizing interleaved track for {total_segments} segments...")
    combined_audio = AudioSegment.empty()
    current_b_time = 0.0
    b_timestamps = []

    for i, seg in enumerate(segments):
        if (i + 1) % 5 == 0 or i == 0 or (i + 1) == total_segments:
            print(f"    > Synthesizing audio segment {i+1} of {total_segments}...")

        time.sleep(0.5) 
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
            
            combined_audio += AudioSegment.silent(duration=1000)
            current_b_time += 1.0
            
            seg_b_end = current_b_time
            b_timestamps.append({"b_start": round(seg_b_start, 2), "b_end": round(seg_b_end, 2)})
        except Exception as e:
            print(f"      [!] Error synthesizing segment {i+1}: {e}")
            b_timestamps.append({"b_start": 0, "b_end": 0})

    print(f"[*] Exporting final interleaved MP3...")
    combined_audio.export(interleaved_audio_file, format="mp3")

    # 4. Save JSON
    print(f"[*] Saving transcription data to {json_output}...")
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
    with open(html_output, 'w', encoding='utf-8') as f:
        f.write(build_html(feedname, date, title, lang, asset_prefix + audio_file, asset_prefix + interleaved_audio_file, asset_prefix + json_output, asset_prefix + vocab_output, start_pattern))
    print(f"[*] Success! Created {html_output}")


_GTAG_IDS = {
    "usapodden": "G-1B0C3D6XSQ",
}

def _gtag_snippet(feedname):
    gtag_id = _GTAG_IDS.get(feedname)
    if not gtag_id:
        return ""
    return f"""<!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={gtag_id}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{gtag_id}');
    </script>"""

def build_html(feedname, date, title, lang, audio_file, interleaved_audio_file, json_output, vocab_output, start_pattern=None, title_translation=None):
    from interleaver.player import render_player
    from datetime import datetime as _dt
    try:
        pretty_date = _dt.strptime(date, "%y%m%d").strftime("%B %-d, %Y")
    except Exception:
        pretty_date = date
    _feed_display = {"usapodden": "USApodden", "aftenpodden-usa": "Aftenpodden USA"}
    feed_label = "Based on " + _feed_display.get(feedname, feedname.replace("-", " ").title())
    if title_translation is None and lang != "en":
        try:
            from deep_translator import GoogleTranslator
            title_translation = GoogleTranslator(source=lang, target="en").translate(title)
        except Exception:
            title_translation = ""
    changelog_html = """
        <div class="cl-entry">
            <div class="cl-date">March 29, 2026</div>
            <ul class="cl-items">
                <li>New <strong>Reading mode</strong> &#x2014; scroll through the transcript and translations reveal as each line scrolls into view</li>
                <li>Sticky position &#x2014; the app remembers where you left off in Podcast and Interleaved modes</li>
                <li>Reading mode also remembers your scroll position between visits</li>
                <li>New <strong>&#x21A9; Resume</strong> button in the header jumps back to the last played position</li>
            </ul>
        </div>
        <div class="cl-entry">
            <div class="cl-date">March 23, 2026</div>
            <ul class="cl-items">
                <li>English translation now appears directly below the Swedish as it plays &#x2014; easier to follow both at once</li>
                <li>Tap the left side of any row to jump to that line and start playing</li>
                <li>Tap &#x1F4CC; on any row to loop that line &#x2014; useful for practicing a phrase</li>
                <li>Tapping a word pauses playback; dismissing the definition resumes automatically</li>
                <li>Speed controls back in the header for quick access</li>
                <li>Scrolling the transcript no longer fights with auto-scroll during playback</li>
                <li>Definitions now link to Folkets lexikon, a Swedish-English learner dictionary</li>
            </ul>
        </div>
        <div class="cl-entry">
            <div class="cl-date">March 21, 2026</div>
            <ul class="cl-items">
                <li>Tap any blue word in the transcript to see its English definition, and related English words</li>
                <li>Words with known English relatives are highlighted in the transcript</li>
                <li>Definitions link directly to the word&#x27;s Wiktionary page when available</li>
            </ul>
        </div>
        <div class="cl-entry">
            <div class="cl-date">March 14, 2026</div>
            <ul class="cl-items">
                <li>Added vocabulary panel with words grouped by part of speech</li>
                <li>English cognates shown for Swedish words (e.g. <em>hus</em> &#x2192; <em>house</em>)</li>
                <li>Etymology notes from Wiktionary</li>
            </ul>
        </div>
        <div class="cl-entry">
            <div class="cl-date">February 2026</div>
            <ul class="cl-items">
                <li>Bilingual interleaved audio mode &#x2014; hear each segment in Swedish, then English</li>
                <li>Transcript scrolls and highlights in sync with playback</li>
                <li>Tap any transcript segment to jump to that point in the audio</li>
                <li>Works offline once loaded; installable as a home screen app</li>
            </ul>
        </div>"""
    return render_player(
        title=title,
        source_lang=lang,
        audio_path=audio_file,
        interleaved_audio_path=interleaved_audio_file,
        transcript_json_path=json_output,
        vocab_json_path=vocab_output,
        start_pattern=start_pattern,
        extra_head_html=_gtag_snippet(feedname),
        subtitle=f"{feed_label} &nbsp;&middot;&nbsp; {pretty_date}",
        title_translation=title_translation or "",
        changelog_html=changelog_html,
        ep_key=f"{feedname}.{date}",
    )


def _build_html_old_UNUSED(feedname, date, title, lang, audio_file, interleaved_audio_file, json_output, vocab_output, start_pattern=None):
    """Retained for reference only — build_html now delegates to interleaver.player.render_player."""
    js_start_pattern = f'"{start_pattern}"' if start_pattern else "null"
    return f"""
    <!DOCTYPE html>
    <html lang="{lang}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>{title}</title>
        {_gtag_snippet(feedname)}
        <style>
            :root {{ --primary: #004a99; --accent: #ffc107; --bg: #f0f2f5; }}
            body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0; background: var(--bg); }}
            .header-box {{ position: sticky; top: 0; background: rgba(255,255,255,0.98); padding: 10px 15px; border-bottom: 3px solid var(--primary); z-index: 100; backdrop-filter: blur(10px); }}
            .header-top {{ display: flex; align-items: center; gap: 12px; }}
            .header-left {{ flex: 1; min-width: 0; }}
            .header-title {{ margin: 2px 0; font-size: 1.1rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
            .header-meta {{ font-size: 0.65rem; font-weight: bold; color: #666; }}
            .header-meta a {{ color: #1565c0; text-decoration: none; font-weight: bold; }}
            .changelog-overlay {{
                display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4);
                z-index: 1000; align-items: center; justify-content: center;
            }}
            .changelog-overlay.open {{ display: flex; }}
            .changelog-box {{
                background: white; border-radius: 12px; padding: 20px 24px;
                max-width: 420px; width: 90%; max-height: 80vh; overflow-y: auto;
                box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            }}
            .changelog-box h2 {{ margin: 0 0 14px; font-size: 1rem; color: var(--primary); }}
            .changelog-box .cl-close {{ float: right; cursor: pointer; color: #999; font-size: 1.1rem; }}
            .cl-entry {{ margin-bottom: 14px; }}
            .cl-date {{ font-size: 0.7rem; font-weight: bold; color: #888; text-transform: uppercase; margin-bottom: 3px; }}
            .cl-items {{ margin: 0; padding-left: 16px; font-size: 0.85rem; color: #333; line-height: 1.6; }}
            .header-right {{ flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 3px; }}
            audio {{ width: 220px; height: 36px; }}
            .header-controls {{ display: flex; align-items: center; gap: 5px; flex-wrap: wrap; margin-top: 6px; padding-top: 6px; border-top: 1px solid #e0e0e0; }}
            .header-controls .divider {{ color: #ccc; }}
            .mode-toggle {{ display: flex; border: 1px solid var(--primary); border-radius: 20px; overflow: hidden; }}
            .mode-opt {{ background: white; color: var(--primary); border: none; padding: 5px 12px; font-size: 0.75rem; font-weight: bold; cursor: pointer; }}
            .mode-opt.active {{ background: var(--primary); color: white; }}
            .speed-label {{ font-size: 0.65rem; font-weight: bold; color: #555; }}
            .speed-btn {{ background: #fff; color: #333; border: 1px solid #ccc; padding: 4px 10px; border-radius: 12px; font-size: 0.7rem; cursor: pointer; }}
            .speed-btn.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
            .vocab-row {{ display: flex; align-items: center; gap: 8px; }}
            .btn {{ background: var(--primary); color: white; border: none; padding: 8px 12px; border-radius: 20px; font-weight: bold; cursor: pointer; font-size: 0.75rem; }}
            .btn.active {{ background: var(--accent); color: black; }}
            .transcript {{ padding: 20px; max-width: 900px; margin: 0 auto; }}
            #word-tip {{
                display: flex; align-items: center; justify-content: space-between;
                background: #e8f0fe; border: 1px solid #c5d8fb; border-radius: 8px;
                padding: 8px 12px; margin: 12px 20px 0; font-size: 0.8rem; color: #1a3a6e;
            }}
            #word-tip-close {{ cursor: pointer; font-size: 1rem; color: #999; padding-left: 10px; }}
            .row {{ display: flex; flex-direction: row; margin-bottom: 8px; background: white; border-radius: 12px; border: 1px solid #ddd; overflow: hidden; }}
            .row.highlight {{ background: #fffde7; border-left: none; outline: 3px solid var(--accent); transition: outline 0.3s ease; }}
            .row-nav {{
                width: 32px; flex-shrink: 0; background: #e8f0fe;
                display: flex; flex-direction: column; align-items: center;
                justify-content: flex-start; padding-top: 8px; gap: 6px;
                cursor: pointer; user-select: none; transition: background 0.15s;
            }}
            .row.highlight .row-nav {{ background: #c5d8fb; }}
            .row-nav:active {{ background: var(--accent); }}
            @keyframes navFlash {{ 0%,100% {{ background: #e8f0fe; }} 50% {{ background: var(--accent); }} }}
            .row-nav.flash {{ animation: navFlash 0.35s ease-out; }}
            .row-nav.pinned {{ background: #fff3cd; }}
            .row.highlight .row-nav.pinned {{ background: #ffe082; }}
            .pin-btn {{ font-size: 0.75rem; opacity: 0.4; cursor: pointer; line-height: 1; }}
            .row-nav.pinned .pin-btn {{ opacity: 1; }}
            .row-content {{ flex: 1; padding: 12px 15px; display: flex; flex-direction: column; min-width: 0; }}
            #play-btn {{
                display: none; position: fixed; left: 8px; z-index: 50;
                background: var(--accent); border: none; border-radius: 50%;
                width: 36px; height: 36px; font-size: 1rem; cursor: pointer;
                box-shadow: 0 2px 6px rgba(0,0,0,0.2); line-height: 36px; text-align: center;
            }}
            .orig {{ color: var(--primary); font-weight: 700; font-size: 1.1rem; }}
            .en {{ display: none; color: #546e7a; font-style: italic; font-size: 0.95rem; margin-top: 6px; padding-top: 6px; border-top: 1px solid #e8e8e8; }}
            .row.highlight .en {{ display: block; }}
            .en.revealed {{ display: block; }}
            body.reading-mode .row-nav {{ display: none; }}
            body.reading-mode #play-btn {{ display: none !important; }}
            body.reading-mode .speed-label,
            body.reading-mode .speed-btn {{ display: none; }}
            .jump-btn {{ background: #fff3cd; color: #7a5c00; border: 1px solid #ffc107; padding: 4px 10px; border-radius: 12px; font-size: 0.7rem; cursor: pointer; font-weight: bold; }}
            .reset-btn {{ background: #fce4e4; color: #7a0000; border: 1px solid #e57373; padding: 4px 10px; border-radius: 12px; font-size: 0.7rem; cursor: pointer; font-weight: bold; }}
            .status-badge {{ font-size: 0.7rem; margin-left: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; }}
            .sv-word {{ cursor: pointer; color: #1565c0; }}
            .sv-word .wikt-arrow {{ font-size: 0.55em; vertical-align: super; opacity: 0.6; }}
            #word-popup {{
                display: none; position: fixed; z-index: 999;
                background: white; border: 1px solid #ccc; border-radius: 10px;
                box-shadow: 0 4px 16px rgba(0,0,0,0.18); padding: 12px 15px;
                max-width: 280px; font-size: 0.85rem; line-height: 1.5;
            }}
            #word-popup .wp-lemma {{ font-size: 1rem; font-weight: bold; color: var(--primary); }}
            #word-popup .wp-trans {{ color: #546e7a; font-style: italic; margin-bottom: 4px; }}
            #word-popup .wp-cognate {{ color: #1565c0; font-weight: bold; }}
            #word-popup .wp-etym {{ color: #555; font-size: 0.78rem; margin-top: 4px; }}
            #word-popup .wp-link {{ display: inline-block; margin-top: 6px; font-size: 0.75rem; color: #2e7d32; text-decoration: underline; }}
            #word-popup .wp-close {{ float: right; cursor: pointer; color: #999; font-size: 1rem; line-height: 1; margin-left: 8px; }}
            @media (max-width: 768px) {{ .row {{ padding: 10px 12px; }} }}
        </style>
    </head>
    <body>
        <div class="header-box">
            <div class="header-top">
                <div class="header-left">
                    <div class="header-meta">{feed_label} &nbsp;·&nbsp; {pretty_date} &nbsp;·&nbsp; <a href="#" onclick="event.preventDefault();document.getElementById('changelog').classList.add('open')">What's new</a> &nbsp;·&nbsp; <em style="font-weight:normal;">Personal/educational use only.</em></div>
                    <h1 class="header-title">{title}</h1>
                </div>
                <div class="header-right">
                    <audio id="audio" preload="metadata" src="{audio_file}"></audio>
                    <span id="audio-status" class="status-badge"></span>
                </div>
            </div>
            <div class="header-controls">
                <span class="speed-label">SPEED:</span>
                <button class="speed-btn" onclick="setSpeed(0.5)">0.5x</button>
                <button class="speed-btn" onclick="setSpeed(0.75)">0.75x</button>
                <button class="speed-btn active" onclick="setSpeed(1.0)">1x</button>
                <button class="speed-btn" onclick="setSpeed(1.25)">1.25x</button>
                <button class="speed-btn" onclick="setSpeed(1.5)">1.5x</button>
                <span class="divider">|</span>
                <div class="mode-toggle">
                    <button id="modePodcast" class="mode-opt active" onclick="setMode('orig')" title="Listen and follow along with the translated text">Podcast</button>
                    <button id="modeInterleaved" class="mode-opt" onclick="setMode('bilingual')" title="Listen to alternating Swedish and English audio">Interleaved</button>
                    <button id="modeReading" class="mode-opt" onclick="setMode('reading')" title="Scroll through source and translation — no audio">Reading</button>
                </div>
                <button id="jump-btn" class="jump-btn" style="display:none" onclick="jumpToLast()">↩ Resume</button>
                <button id="reset-btn" class="reset-btn" style="display:none" onclick="resetProgress()">✕ Reset</button>
            </div>
        </div>
        <div id="changelog" class="changelog-overlay" onclick="if(event.target===this)this.classList.remove('open')">
            <div class="changelog-box">
                <span class="cl-close" onclick="document.getElementById('changelog').classList.remove('open')">✕</span>
                <h2>What's new</h2>
                <div class="cl-entry">
                    <div class="cl-date">March 29, 2026</div>
                    <ul class="cl-items">
                        <li>New <strong>Reading mode</strong> — scroll through the transcript and translations reveal as each line scrolls into view</li>
                        <li>Sticky position — the app remembers where you left off in Podcast and Interleaved modes</li>
                        <li>Reading mode also remembers your scroll position between visits</li>
                        <li>New <strong>↩ Resume</strong> button in the header jumps back to the last played position</li>
                    </ul>
                </div>
                <div class="cl-entry">
                    <div class="cl-date">March 23, 2026</div>
                    <ul class="cl-items">
                        <li>English translation now appears directly below the Swedish as it plays — easier to follow both at once</li>
                        <li>Tap the left side of any row to jump to that line and start playing</li>
                        <li>Tap 📌 on any row to loop that line — useful for practicing a phrase</li>
                        <li>Tapping a word pauses playback; dismissing the definition resumes automatically</li>
                        <li>Speed controls back in the header for quick access</li>
                        <li>Scrolling the transcript no longer fights with auto-scroll during playback</li>
                        <li>Definitions now link to Folkets lexikon, a Swedish-English learner dictionary</li>
                    </ul>
                </div>
                <div class="cl-entry">
                    <div class="cl-date">March 21, 2026</div>
                    <ul class="cl-items">
                        <li>Tap any blue word in the transcript to see its English definition, and related English words</li>
                        <li>Words with known English relatives are highlighted in the transcript</li>
                        <li>Definitions link directly to the word's Wiktionary page when available</li>
                    </ul>
                </div>
                <div class="cl-entry">
                    <div class="cl-date">March 14, 2026</div>
                    <ul class="cl-items">
                        <li>Added vocabulary panel with words grouped by part of speech</li>
                        <li>English cognates shown for Swedish words (e.g. <em>hus</em> → <em>house</em>)</li>
                        <li>Etymology notes from Wiktionary</li>
                    </ul>
                </div>
                <div class="cl-entry">
                    <div class="cl-date">February 2026</div>
                    <ul class="cl-items">
                        <li>Bilingual interleaved audio mode — hear each segment in Swedish, then English</li>
                        <li>Transcript scrolls and highlights in sync with playback</li>
                        <li>Tap any transcript segment to jump to that point in the audio</li>
                        <li>Works offline once loaded; installable as a home screen app</li>
                    </ul>
                </div>
            </div>
        </div>
        <button id="play-btn" onclick="togglePlayPause()">▶</button>
        <div id="word-tip">
            <span>Tap a <strong style="color:#1565c0;">blue word</strong> in the transcript to see its definition.</span>
            <span id="word-tip-close" onclick="dismissTip()">✕</span>
        </div>
        <div id="word-popup">
            <span class="wp-close" onclick="closePopup()">✕</span>
            <div class="wp-lemma" id="wp-lemma"></div>
            <div class="wp-trans" id="wp-trans"></div>
            <div class="wp-cognate" id="wp-cognate"></div>
            <div class="wp-etym" id="wp-etym"></div>
            <a class="wp-link" id="wp-link" target="_blank" rel="noopener">Open in Folkets lexikon ↗</a>
        </div>
        <div id="transcript" class="transcript"></div>
        <script>
            const audio = document.getElementById('audio');
            const modePodcast = document.getElementById('modePodcast');
            const modeInterleaved = document.getElementById('modeInterleaved');
            const modeReading = document.getElementById('modeReading');
            const statusEl = document.getElementById('audio-status');
            const container = document.getElementById('transcript');
            const sources = {{ orig: "{audio_file}", bilingual: "{interleaved_audio_file}" }};
            const startPattern = {js_start_pattern};
            const epKey = '{feedname}.{date}';
            let mode = 'orig';
            let data = [];
            let lastIdx = -1;
            let seekTargetTime = null;
            let initialSeekDone = false;

            function applySeek() {{
                if (initialSeekDone || seekTargetTime === null) return;
                if (audio.readyState >= 1) {{
                    audio.currentTime = seekTargetTime;
                    initialSeekDone = true;
                }}
            }}

            audio.addEventListener('loadedmetadata', applySeek);
            audio.addEventListener('canplay', applySeek);

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
                    btn.classList.toggle('active', parseFloat(btn.textContent) === rate);
                }});
            }}

            // --- Reading mode ---
            let readingObserver = null;

            function enterReadingMode() {{
                audio.pause();
                document.body.classList.add('reading-mode');
                document.querySelectorAll('.row').forEach(row => {{
                    if (readingObserver) readingObserver.observe(row);
                }});
                const saved = parseInt(localStorage.getItem('readScroll_' + epKey) || '0');
                if (saved > 0) requestAnimationFrame(() => window.scrollTo({{ top: saved, behavior: 'instant' }}));
            }}

            function exitReadingMode() {{
                document.body.classList.remove('reading-mode');
                if (readingObserver) {{ readingObserver.disconnect(); }}
                document.querySelectorAll('.en.revealed').forEach(el => el.classList.remove('revealed'));
            }}

            readingObserver = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        const enEl = entry.target.querySelector('.en');
                        if (enEl) enEl.classList.add('revealed');
                    }}
                }});
            }}, {{ threshold: 0.3 }});

            // --- Sticky position ---
            function updateJumpBtn() {{
                const saved = parseFloat(localStorage.getItem('audioPos_' + epKey) || '0');
                const hasProgress = saved > 5 || parseFloat(localStorage.getItem('readPct_' + epKey) || '0') > 0;
                document.getElementById('jump-btn').style.display = (mode !== 'reading' && saved > 5) ? '' : 'none';
                document.getElementById('reset-btn').style.display = hasProgress ? '' : 'none';
            }}

            function resetProgress() {{
                ['audioPos_', 'audioPct_', 'readScroll_', 'readPct_', 'epMode_'].forEach(function(k) {{
                    localStorage.removeItem(k + epKey);
                }});
                audio.currentTime = 0;
                audio.pause();
                document.getElementById('prog-orig').textContent = '';
                document.getElementById('prog-bilingual').textContent = '';
                document.getElementById('prog-reading').textContent = '';
                updateJumpBtn();
            }}

            function jumpToLast() {{
                if (mode === 'reading') return;
                const saved = parseFloat(localStorage.getItem('audioPos_' + epKey) || '0');
                if (!saved || !data.length) return;
                audio.currentTime = saved;
                const idx = data.findIndex(item => saved >= item.start && saved <= item.end);
                if (idx !== -1) {{
                    const row = document.getElementById('row-' + idx);
                    if (row) {{ userScrolling = false; row.scrollIntoView({{ behavior: 'smooth', block: 'center' }}); }}
                }}
                audio.play();
            }}

            let audioSaveTimer = null;
            function saveAudioPos() {{
                if (mode !== 'reading' && audio.currentTime > 5) {{
                    localStorage.setItem('audioPos_' + epKey, audio.currentTime.toString());
                }}
            }}
            audio.addEventListener('pause', saveAudioPos);

            function setMode(newMode) {{
                if (newMode === mode) return;
                const wasReading = (mode === 'reading');
                const willRead = (newMode === 'reading');
                if (wasReading) exitReadingMode();
                const isPlaying = !audio.paused;
                const rate = audio.playbackRate;
                mode = newMode;
                localStorage.setItem('epMode_' + epKey, mode);
                modePodcast.classList.toggle('active', mode === 'orig');
                modeInterleaved.classList.toggle('active', mode === 'bilingual');
                modeReading.classList.toggle('active', mode === 'reading');
                if (willRead) {{
                    enterReadingMode();
                    return;
                }}
                audio.src = sources[mode];
                audio.playbackRate = rate;
                lastIdx = -1;
                if (startPattern !== null && data.length > 0) {{
                    const normPat = startPattern.toLowerCase().replace(/\s+/g, '');
                    const matchIdx = data.findIndex(item => item.orig.toLowerCase().replace(/\s+/g, '').includes(normPat));
                    const target = data[matchIdx !== -1 ? matchIdx : 0];
                    seekTargetTime = (mode === 'orig') ? target.start : target.b_start;
                    initialSeekDone = false;
                }}
                checkAudioStatus();
                if (isPlaying) audio.play();
                updateJumpBtn();
            }}

            checkAudioStatus();
            updateJumpBtn();

            const playBtn = document.getElementById('play-btn');
            function togglePlayPause() {{
                if (audio.paused) {{ audio.play(); }} else {{ audio.pause(); }}
            }}
            audio.addEventListener('play', () => {{ playBtn.textContent = '⏸'; }});
            audio.addEventListener('pause', () => {{ playBtn.textContent = '▶'; }});

            function movePlayBtn(rowEl) {{
                if (!rowEl) {{ playBtn.style.display = 'none'; return; }}
                const rect = rowEl.getBoundingClientRect();
                const btnTop = rect.top + rect.height / 2 - 18;
                playBtn.style.top = btnTop + 'px';
                playBtn.style.display = 'block';
            }}

            let formToEntry = {{}};
            let userScrolling = false;
            let pinnedIdx = -1;
            let userScrollTimer = null;
            let readScrollTimer = null;
            window.addEventListener('scroll', () => {{
                userScrolling = true;
                clearTimeout(userScrollTimer);
                userScrollTimer = setTimeout(() => {{ userScrolling = false; }}, 2000);
                if (mode === 'reading') {{
                    clearTimeout(readScrollTimer);
                    readScrollTimer = setTimeout(() => {{
                        localStorage.setItem('readScroll_' + epKey, window.scrollY.toString());
                    }}, 500);
                }}
            }}, {{ passive: true }});

            (function() {{
                const tip = document.getElementById('word-tip');
                if (localStorage.getItem('wordTipDismissed')) tip.style.display = 'none';
            }})();

            function dismissTip() {{
                document.getElementById('word-tip').style.display = 'none';
                localStorage.setItem('wordTipDismissed', '1');
            }}

            function tokenizeOrig(text) {{
                // Split into word/non-word tokens, wrap lookupable words in spans
                const tokens = text.split(/(\s+|[.,!?;:""''()\[\]\u2013\u2014-]+)/);
                return tokens.map(tok => {{
                    const key = tok.toLowerCase().replace(/^[""''()\[\]\u2013\u2014-]+|[.,!?;:""''()\[\]\u2013\u2014-]+$/g, '');
                    const entry = key ? formToEntry[key] : null;
                    if (!entry) return tok.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                    const safe = tok.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                    const arrow = entry.folkets ? '<span class="wikt-arrow">↗</span>' : '';
                    return `<span class="sv-word" data-key="${{key}}">${{safe}}${{arrow}}</span>`;
                }}).join('');
            }}

            let pausedForPopup = false;

            function showWordPopup(key, anchorEl) {{
                const entry = formToEntry[key];
                if (!entry) return;
                if (!audio.paused) {{ audio.pause(); pausedForPopup = true; }}
                const popup = document.getElementById('word-popup');
                document.getElementById('wp-lemma').textContent = entry.word;
                document.getElementById('wp-trans').textContent = entry.translation || '';
                const cogEl = document.getElementById('wp-cognate');
                cogEl.textContent = entry.cognate ? `cognate: ${{entry.cognate}}` : '';
                cogEl.style.display = entry.cognate ? '' : 'none';
                const etymEl = document.getElementById('wp-etym');
                etymEl.textContent = entry.etymology || '';
                etymEl.style.display = entry.etymology ? '' : 'none';
                const linkEl = document.getElementById('wp-link');
                if (entry.folkets) {{
                    linkEl.href = `https://folkets-lexikon.csc.kth.se/folkets/folkets.en.html#lookup&${{encodeURIComponent(entry.word)}}`;
                    linkEl.style.display = '';
                }} else {{
                    linkEl.style.display = 'none';
                }}
                popup.style.display = 'block';
                const rect = anchorEl.getBoundingClientRect();
                let top = rect.bottom + 6;
                let left = rect.left;
                const pw = 280;
                if (left + pw > window.innerWidth - 10) left = window.innerWidth - pw - 10;
                if (left < 10) left = 10;
                popup.style.top = top + 'px';
                popup.style.left = left + 'px';
            }}

            function closePopup() {{
                document.getElementById('word-popup').style.display = 'none';
                if (pausedForPopup) {{ pausedForPopup = false; audio.play(); }}
            }}

            document.addEventListener('click', e => {{
                const popup = document.getElementById('word-popup');
                if (!popup.contains(e.target) && !e.target.classList.contains('sv-word')) {{
                    closePopup();
                }}
            }});

            function makeRowHTML(item) {{
                const origHTML = Object.keys(formToEntry).length > 0 ? tokenizeOrig(item.orig) : item.orig.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                return `<div class="row-nav"><span class="pin-btn">📌</span></div><div class="row-content"><div class="orig">${{origHTML}}</div><div class="en">${{item.en}}</div></div>`;
            }}

            function rerenderTranscript() {{
                data.forEach((item, i) => {{
                    const row = document.getElementById('row-' + i);
                    if (row) row.innerHTML = makeRowHTML(item);
                }});
            }}

            fetch('{vocab_output}').then(r => r.json()).then(vocab => {{
                Object.entries(vocab).forEach(([pos, words]) => {{
                    words.forEach(e => {{
                        const entry = {{ word: e.word, translation: e.translation, pos, cognate: e.cognate || '', etymology: e.etymology || '', folkets: e.folkets || false }};
                        formToEntry[e.word.toLowerCase()] = entry;
                        (e.forms || []).forEach(f => {{ formToEntry[f.toLowerCase()] = entry; }});
                    }});
                }});
                rerenderTranscript();
            }}).catch(() => {{}});

            fetch('{json_output}').then(r => r.json()).then(json => {{
                data = json;
                // Restore sticky mode
                const savedMode = localStorage.getItem('epMode_' + epKey);
                if (savedMode && savedMode !== mode) {{
                    mode = savedMode;
                    modePodcast.classList.toggle('active', mode === 'orig');
                    modeInterleaved.classList.toggle('active', mode === 'bilingual');
                    modeReading.classList.toggle('active', mode === 'reading');
                    if (mode !== 'reading') {{
                        audio.src = sources[mode] || sources['orig'];
                        checkAudioStatus();
                    }}
                }}
                data.forEach((item, i) => {{
                    const row = document.createElement('div');
                    row.className = 'row'; row.id = 'row-' + i;
                    row.innerHTML = makeRowHTML(item);
                    row.onclick = e => {{
                        // Arrow on a word — treat as click on the word itself
                        const wordEl = e.target.classList.contains('wikt-arrow') ? e.target.closest('.sv-word') : null;
                        if (e.target.classList.contains('sv-word') || wordEl) {{
                            showWordPopup((wordEl || e.target).dataset.key, wordEl || e.target);
                        }} else if (e.target.classList.contains('pin-btn') || e.target.classList.contains('row-nav')) {{
                            // Nav cell: pin toggle on pin icon, jump-and-play on cell body
                            const nav = row.querySelector('.row-nav');
                            if (e.target.classList.contains('pin-btn')) {{
                                if (pinnedIdx === i) {{
                                    pinnedIdx = -1;
                                    nav.classList.remove('pinned');
                                }} else {{
                                    if (pinnedIdx !== -1) {{
                                        const old = document.querySelector('.row-nav.pinned');
                                        if (old) old.classList.remove('pinned');
                                    }}
                                    pinnedIdx = i;
                                    nav.classList.add('pinned');
                                }}
                            }}
                            nav.classList.remove('flash');
                            void nav.offsetWidth;
                            nav.classList.add('flash');
                            setTimeout(() => nav.classList.remove('flash'), 400);
                            closePopup();
                            userScrolling = false;
                            audio.currentTime = (mode === 'orig') ? item.start : item.b_start;
                            audio.play();
                            movePlayBtn(row);
                        }}
                        // clicks on row-content area do nothing
                    }};
                    container.appendChild(row);
                }});
                if (mode === 'reading') {{
                    enterReadingMode();
                }} else {{
                    // Restore saved audio position, or fall back to startPattern
                    const savedPos = parseFloat(localStorage.getItem('audioPos_' + epKey) || '0');
                    if (savedPos > 5) {{
                        seekTargetTime = savedPos;
                        initialSeekDone = false;
                        applySeek();
                    }} else if (startPattern !== null && data.length > 0) {{
                        const normPat = startPattern.toLowerCase().replace(/\s+/g, '');
                        const matchIdx = data.findIndex(item => item.orig.toLowerCase().replace(/\s+/g, '').includes(normPat));
                        const targetIdx = matchIdx !== -1 ? matchIdx : 0;
                        const target = data[targetIdx];
                        seekTargetTime = (mode === 'orig') ? target.start : target.b_start;
                        const targetRow = document.getElementById('row-' + targetIdx);
                        if (targetRow) {{
                            requestAnimationFrame(() => {{
                                targetRow.scrollIntoView({{ block: 'center' }});
                                movePlayBtn(targetRow);
                            }});
                        }}
                        applySeek();
                    }}
                    updateJumpBtn();
                }}
            }});

            audio.addEventListener('timeupdate', () => {{
                const now = audio.currentTime;
                clearTimeout(audioSaveTimer);
                audioSaveTimer = setTimeout(saveAudioPos, 5000);
                const currentIdx = data.findIndex(item => {{
                    const s = (mode === 'orig') ? item.start : item.b_start;
                    const e = (mode === 'orig') ? item.end : item.b_end;
                    return now >= s && now <= e;
                }});

                // Pin loop logic — cut off cleanly at the row's end time
                if (pinnedIdx !== -1) {{
                    const pinEnd = (mode === 'orig') ? data[pinnedIdx].end : data[pinnedIdx].b_end;
                    const pinStart = (mode === 'orig') ? data[pinnedIdx].start : data[pinnedIdx].b_start;
                    if (now >= pinEnd) {{
                        audio.pause();
                        setTimeout(() => {{
                            audio.currentTime = pinStart;
                            audio.play();
                        }}, 600);
                    }}
                }}

                if (currentIdx !== lastIdx) {{
                    if (lastIdx !== -1) {{
                        const oldEl = document.getElementById('row-' + lastIdx);
                        if (oldEl) oldEl.classList.remove('highlight');
                    }}
                    if (currentIdx !== -1) {{
                        const newEl = document.getElementById('row-' + currentIdx);
                        if (newEl) {{
                            newEl.classList.add('highlight');
                            if (!userScrolling) newEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                            movePlayBtn(newEl);
                        }}
                    }} else {{
                        movePlayBtn(null);
                    }}
                    lastIdx = currentIdx;
                }} else if (currentIdx !== -1) {{
                    movePlayBtn(document.getElementById('row-' + currentIdx));
                }}
            }});
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--feedname", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--lang", default="no")
    parser.add_argument("--num_utterances", type=int)
    parser.add_argument("--wordlist-only", action="store_true")
    parser.add_argument("--html-only", action="store_true")
    parser.add_argument("--staging", action="store_true")
    parser.add_argument("--start-pattern", default=None)
    args = parser.parse_args()
    process_podcast(args.url, args.feedname, args.date, args.title, args.lang, args.num_utterances, args.wordlist_only, args.html_only, args.start_pattern, args.staging)
    
