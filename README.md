# Podcast Translator & Feed Dashboard Pipeline

This repository contains a suite of Python scripts designed to automate the translation of foreign language politics podcasts. The pipeline handles everything from RSS feed discovery to deployment on GitHub Pages.

---

## Pipeline Overview

```
sync_all_feeds.py
  └─► run_workflow_feed.py       (per feed)
        └─► show_general_feed.py (generates feed dashboard HTML)
  └─► generate_podcast_index.py  (builds master index)

run_workflow.py                  (per episode, triggered manually from dashboard)
  └─► svdownload.py              (AI transcription / translation / TTS engine)
```

---

## Core Pipeline Scripts

### 1. `sync_all_feeds.py` — Master Sync

**Purpose:** The "one-click" update script for the entire library.

- Scans `./Podcasts/` for `*.feed.html` files and extracts their embedded RSS URLs and language settings.
- Calls `run_workflow_feed.py` for each feed in sequence.
- Runs `generate_podcast_index.py` after all feeds are updated.

> **Note:** Feed configuration (RSS URL, language override) is stored inside the generated dashboard HTML files themselves as `data-*` attributes — there is no separate config file.

---

### 2. `run_workflow_feed.py` — Feed Dashboard Manager

**Purpose:** Manages a single podcast show's dashboard.

- Parses the RSS feed to auto-discover the podcast title and derive a slug (`feedname`).
- Calls `show_general_feed.py` as a subprocess and captures its output to retrieve the detected language.
- Moves the generated `{feedname}.feed.html` into `./Podcasts/`.
- Commits and pushes to the Podcasts git repository.

**Arguments:**

| Argument | Required | Description |
|---|---|---|
| `--url` | Yes | RSS feed URL |
| `--lang` | No | Override language detection (e.g. `sv`, `no`) |
| `--feedname` | No | Override the auto-derived slug |

---

### 3. `show_general_feed.py` — Feed Dashboard Generator

**Purpose:** Fetches an RSS feed and writes a self-contained HTML dashboard for it.

- Fetches the feed with cache-busting headers.
- Generates up to 15 episode cards, each with a "Copy Process Command" button that copies the `run_workflow.py` invocation to the clipboard.
- Uses JavaScript `HEAD` requests to check whether each episode has already been processed and is live on GitHub Pages ("Live" vs. "Pending").
- Embeds the latest episode publish timestamp (`data-latest`) and dashboard generation time (`data-generated`) in the `<body>` tag, which powers the "⚠ Update Available" sync button and the staleness indicator in the index.
- Prints `LANG_OUTPUT:{lang_code}` to stdout so `run_workflow_feed.py` can capture the detected language.

**Arguments:**

| Argument | Required | Description |
|---|---|---|
| `--url` | Yes | RSS feed URL |
| `--lang` | No | Override language detection |
| `--feedname` | No | Override the auto-derived slug |

---

### 4. `generate_podcast_index.py` — Master Index Builder

**Purpose:** Scans all feed dashboards in `./Podcasts/` and generates the top-level `index.html`.

- Reads each `*.feed.html` to extract title, language, RSS URL, sync mode, and freshness timestamps (`data-latest`, `data-generated`).
- Generates a table of all tracked podcasts with language codes, sync mode (AUTO/MANUAL), and links to each feed dashboard.
- Highlights feeds whose dashboards are stale — where the RSS feed has a newer episode than the last time the dashboard was regenerated — with a yellow "⚠ Stale" badge, using client-side JavaScript to compare the embedded timestamps.
- Commits and pushes the updated `index.html` to the Podcasts repository.

---

### 5. `run_workflow.py` — Episode Processing Controller

**Purpose:** The master controller for processing a single podcast episode end-to-end.

- Calls `svdownload.py` with all episode parameters.
- Moves the four generated files (`{feedname}.{date}.mp3`, `.bilingual.mp3`, `.html`, `transcript.*.json`) into `./Podcasts/`.
- Commits and pushes to the Podcasts git repository.

**Arguments:**

| Argument | Required | Description |
|---|---|---|
| `--url` | Yes | Direct MP3 URL |
| `--feedname` | Yes | Podcast slug (e.g. `usapodden`) |
| `--date` | Yes | Episode date in `YYMMDD` format |
| `--title` | Yes | Episode title (used in the HTML player) |
| `--lang` | No | ISO language code, default `sv` |
| `--num_utterances` | No | Limit segments processed (for testing) |

---

### 6. `svdownload.py` — AI Processing Engine

**Purpose:** The core engine that transforms a raw podcast MP3 into a bilingual, synchronized web player.

Steps performed:
1. **Download** — Streams the MP3 to disk.
2. **Transcription** — Runs OpenAI Whisper (`small` model) to produce timestamped segments.
3. **Translation** — Sends segments in batches of 25 to Google Translate (via `deep_translator`) to produce English text.
4. **Interleaved TTS audio** — Synthesizes each original segment and its English translation via `gTTS`, concatenates them with short silences, and exports a bilingual MP3 with precise timestamps.
5. **JSON export** — Saves `{orig, en, start, end, b_start, b_end}` per segment.
6. **HTML player** — Generates a synchronized transcript viewer with dual audio sources (original vs. bilingual), auto-scrolling highlight, and playback speed controls.

**Arguments:**

| Argument | Required | Description |
|---|---|---|
| `--url` | Yes | Direct MP3 URL |
| `--feedname` | Yes | Podcast slug |
| `--date` | Yes | Episode date in `YYMMDD` format |
| `--title` | Yes | Episode title |
| `--lang` | No | ISO language code, default `no` |
| `--num_utterances` | No | Limit segments processed (for testing) |

---

## Quick Start Workflow

### Update the Entire Library (All Podcasts)

To check for new episodes across every podcast you track and rebuild the index:

```bash
python3 sync_all_feeds.py
```

### Add a New Podcast Feed

```bash
python3 run_workflow_feed.py --url "https://example.com/feed.rss"
# With a language override:
python3 run_workflow_feed.py --url "https://example.com/feed.rss" --lang sv
```

### Process a Single Episode

Copy the command from the feed dashboard, or run directly:

```bash
python3 run_workflow.py \
  --url "https://example.com/episode.mp3" \
  --feedname "mypodcast" \
  --date "260306" \
  --title "Episode Title" \
  --lang sv
```

### Rebuild the Index Only

```bash
python3 generate_podcast_index.py
```
