# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

PodTranslator downloads foreign-language podcast episodes, transcribes them with OpenAI Whisper, translates segments via Google Translate, synthesizes interleaved bilingual audio (original + English TTS), and generates self-contained HTML players. Everything is deployed to GitHub Pages via a separate git repo at ./Podcasts/.

## Running the Code

Update all tracked podcast feeds:

    python3 sync_all_feeds.py

Add a new podcast feed (language auto-detected from RSS, override with --lang):

    python3 run_workflow_feed.py --url "https://example.com/feed.rss"
    python3 run_workflow_feed.py --url "https://example.com/feed.rss" --lang sv

Process a single episode manually:

    python3 run_workflow.py --url "https://example.com/episode.mp3" --feedname "mypodcast" --date "260306" --title "Episode Title" --lang sv

Limit processing for testing (only first N segments):

    python3 run_workflow.py ... --num_utterances 5

Rebuild the master index:

    python3 generate_podcast_index.py

Run tests:

    python3 -m unittest test_svdownload.py

## Architecture

The codebase has two layers: orchestration scripts and a core processing engine.

Orchestration flow:

    sync_all_feeds.py
      reads Podcasts/*.feed.html for embedded RSS URLs and lang metadata
      calls run_workflow_feed.py for each
        calls show_general_feed.py to generate a dashboard HTML
        moves {feedname}.feed.html to Podcasts/ and commits

    generate_podcast_index.py
      reads all Podcasts/*.feed.html
      generates top-level index.html with staleness highlighting

Manual episode flow:

    run_workflow.py
      calls svdownload.py (core engine)
        downloads MP3, transcribes (Whisper small), translates (batches of 25),
        synthesizes interleaved audio (original seg + 0.5s silence + English TTS + 1.0s silence),
        writes JSON with start/end/b_start/b_end timestamps and a self-contained HTML player
      moves output files to Podcasts/ and commits

## Key Design Decisions

Configuration is embedded in HTML. Feed dashboards (Podcasts/*.feed.html) carry their own metadata via data attributes (data-rss-url, data-latest, data-generated, html lang=). There are no .env or config files.

Two git repos. The main repo holds scripts. Podcasts/ is a separate git repo for generated content deployed to GitHub Pages.

LFS must not track *.mp3. GitHub Pages serves LFS pointers instead of actual files. test_svdownload.py validates this. Do not add *.mp3 filter=lfs to Podcasts/.gitattributes.

Staleness detection is client-side. Feed dashboards and the master index embed timestamps. JavaScript compares them at page load to flag stale feeds without a server.

guardian.py documents invariants in svdownload.py and show_general_feed.py that must not regress. Consult it before modifying those files.

## Language Codes

Supported: sv (Swedish), no (Norwegian), fr (French), es (Spanish), pt (Portuguese), da (Danish), it (Italian), de (German). Language is auto-detected from the RSS feed's language tag and can be overridden with --lang.
