# Podcast Translator & Feed Dashboard Pipeline

This repository contains a suite of Python scripts designed to automate the translation of foreign language politics podcasts. The pipeline handles everything from RSS feed discovery and dashboard generation to transcription, bilingual audio synthesis, and deployment to GitHub Pages.

---

## 🛠 Core Pipeline Scripts

### 1. `run_workflow_feed.py`
**Purpose:** The entry point for managing a specific podcast show. It discovers the feed metadata and generates a persistent HTML dashboard for that show.
* **Essential Features:**
    * **Feed Discovery:** Automatically determines show titles and creates "slugs" for filenames.
    * **Automation:** Orchestrates the generation of individual show dashboards.
    * **Git Integration:** Automatically pushes generated dashboards to the `/Podcasts` directory and syncs with the remote repository.

### 2. `show_general_feed.py`
**Purpose:** Generates the interactive HTML dashboard for a specific podcast RSS feed.
* **Essential Features:**
    * **Cache-Busting:** Fetches fresh RSS data to ensure the latest episodes are visible.
    * **Live Status Checking:** Includes embedded JavaScript to check if processed episodes (MP3s/HTML) are already live on GitHub Pages.
    * **Command Generation:** Provides a "Copy Process Command" button to help the user trigger the transcription workflow for specific episodes.

### 3. `run_workflow.py`
**Purpose:** The master controller for processing a single podcast episode.
* **Essential Features:**
    * **File Management:** Coordinates the transcription script, moves generated assets (MP3, JSON, HTML) to the repository, and handles Git staging.
    * **Testing Mode:** Supports `num_utterances` to allow for rapid testing of short segments.

### 4. `svdownload.py`
**Purpose:** The "heavy lifter" script that performs the actual AI-driven transformation of an audio file.
* **Essential Features:**
    * **Transcription:** Uses the OpenAI Whisper 'small' model to transcribe audio in the source language.
    * **Bilingual Synthesis:** Uses Google TTS (`gTTS`) to create an interleaved audio track (Original Language → 500ms silence → English Translation).
    * **Interactive Player:** Generates a mobile-friendly HTML player with synchronized transcript highlighting and playback speed controls.

---

## 📊 Maintenance & Indexing

### 5. `generate_podcast_index.py`
**Purpose:** Scans the repository for all active show dashboards and rebuilds the central `index.html`.
* **Essential Features:**
    * **Metadata Extraction:** Parses existing `.feed.html` files to display the show title, language, and original RSS source.
    * **Status Labeling:** Visually identifies if a feed is using an "Auto" detected language or a "Manual" override.

### 6. `guardian.py`
**Purpose:** A regression testing utility to ensure core functionality isn't lost during updates.
* **Essential Features:**
    * **Health Checks:** Verifies that essential code snippets (like Async Live Checks or Mobile Viewports) exist in the scripts before allowing a workflow to proceed.

---

## 🚀 Quick Start Workflow

1.  **Generate/Update a Dashboard:**
    ```bash
    python3 run_workflow_feed.py --url "[RSS_FEED_URL]" --lang "sv"
    ```

2.  **Process a Specific Episode:**
    Open the generated `.feed.html` file, click **"⚡ Copy Process Command"** for an episode, and paste it into your terminal. This typically runs:
    ```bash
    python3 run_workflow.py --url "[MP3_URL]" --feedname "slug" --date "YYMMDD" --title "Title" --lang "sv"
    ```

3.  **Update the Global Index:**
    ```bash
    python3 generate_podcast_index.py
    ```

---

**Next Step:** Would you like me to help you configure a **GitHub Action** to run the `generate_podcast_index.py` automatically whenever you push a new feed?
