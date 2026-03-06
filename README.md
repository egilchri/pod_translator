# Podcast Translator & Feed Dashboard Pipeline

This repository contains a suite of Python scripts designed to automate the translation of foreign language politics podcasts. The pipeline handles everything from RSS feed discovery to deployment on GitHub Pages.

---

## 🛠 Core Pipeline Scripts

### 1. `sync_all_feeds.py` (Master Sync)
**Purpose:** The "One-Click" update script for the entire library.
* **Essential Features:** Scans the `/Podcasts` directory for existing dashboards, extracts their RSS URLs, and triggers `run_workflow_feed.py` for each one.
* **Final Step:** Automatically runs `generate_podcast_index.py` after all feeds are updated.

### 2. `run_workflow_feed.py`
**Purpose:** Manages a specific podcast show. It discovers feed metadata and generates a persistent HTML dashboard.
* **Essential Features:** Orchestrates dashboard generation and syncs with the remote repository.

### 3. `show_general_feed.py`
**Purpose:** Generates the interactive HTML dashboard for a specific RSS feed.
* **Essential Features:** Includes "Live Status Checking" via JavaScript to see if processed episodes are already on GitHub Pages.

### 4. `run_workflow.py`
**Purpose:** The master controller for processing a single podcast episode.
* **Essential Features:** Coordinates transcription, moves generated assets (MP3, JSON, HTML) to the repository, and pushes to Git.

### 5. `svdownload.py`
**Purpose:** The AI-driven engine for audio transformation.
* **Essential Features:** Performs Whisper transcription, generates interleaved bilingual audio (Original → English), and creates the synchronized web player.

---

## 🚀 Quick Start Workflow

### Update the Entire Library (All Podcasts)
To look for new episodes across every podcast you track and rebuild the index:
```bash
python3 sync_all_feeds.py
