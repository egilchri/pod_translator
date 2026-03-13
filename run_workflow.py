import argparse
import re
import subprocess
import os
import sys
import shutil

def run_command(command_list, cwd=None):
    """Utility to run shell commands in a specific directory."""
    try:
        subprocess.run(command_list, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        # If git commit fails because nothing changed, don't crash the script
        if "commit" in command_list:
            print("No changes to commit, skipping push.")
        else:
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Master Workflow: Transcribe, Move to Repo, and Push.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--feedname", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--lang", default="sv", help="ISO Language code (e.g. sv, no, de)")
    # Added num_utterances parameter to pass to svdownload.py
    parser.add_argument("--num_utterances", type=int, default=None, help="Limit number of segments for testing")
    parser.add_argument("--wordlist-only", action="store_true", help="Only produce the vocabulary JSON, skip all audio processing")
    parser.add_argument("--html-only", action="store_true", help="Only regenerate the HTML player from existing JSON files")
    parser.add_argument("--start-pattern", default=None, help="Skip segments until this text is found in the transcript")
    
    args = parser.parse_args()

    # 1. Path to your separate Podcasts repository
    podcasts_repo_path = os.path.abspath("Podcasts")

    # 2. Run the processing script with the parameters
    print(f"--- Starting Processing for {args.url} in {args.lang} ---")
    
    cmd = [
        "python3", "svdownload.py", 
        "--url", args.url, 
        "--feedname", args.feedname, 
        "--date", args.date, 
        "--title", args.title,
        "--lang", args.lang
    ]
    
    # Append the testing limit if provided
    if args.num_utterances is not None:
        cmd.extend(["--num_utterances", str(args.num_utterances)])

    if args.wordlist_only:
        cmd.append("--wordlist-only")

    if args.html_only:
        cmd.append("--html-only")

    start_pattern = args.start_pattern
    if not start_pattern:
        feed_html = os.path.join("Podcasts", f"{args.feedname}.feed.html")
        if os.path.exists(feed_html):
            with open(feed_html, encoding="utf-8") as f:
                m = re.search(r'data-start-pattern="([^"]+)"', f.read())
                if m:
                    start_pattern = m.group(1)
                    print(f"--- Using start-pattern from feed HTML: '{start_pattern}' ---")

    if start_pattern:
        cmd.extend(["--start-pattern", start_pattern])

    run_command(cmd)

    # 3. Define the generated filenames
    prefix = f"{args.feedname}.{args.date}"
    vocab_name = f"vocab.{args.feedname}.{args.date}.json"

    if args.wordlist_only:
        transcript_name = f"transcript.{args.feedname}.{args.date}.json"
        files_to_move = [vocab_name, transcript_name] if start_pattern else [vocab_name]
    elif args.html_only:
        files_to_move = [f"{prefix}.html"]
    else:
        transcript_name = f"transcript.{prefix}.json"
        files_to_move = [
            f"{prefix}.mp3",
            f"{prefix}.bilingual.mp3",
            f"{prefix}.html",
            transcript_name,
            vocab_name,
        ]

    # 4. Move files to the Podcasts repository folder
    print(f"--- Moving files to {podcasts_repo_path} ---")
    if not os.path.exists(podcasts_repo_path):
        print(f"[!] Error: Podcasts directory not found at {podcasts_repo_path}")
        sys.exit(1)

    for f in files_to_move:
        if os.path.exists(f):
            # Overwrite if file already exists in target
            dest = os.path.join(podcasts_repo_path, f)
            if os.path.exists(dest):
                os.remove(dest)
            shutil.move(f, dest)
        else:
            print(f"[!] Warning: {f} was not generated.")

    # 5. Git Operations inside the Podcasts repository
    print(f"--- Staging and Pushing ({args.lang}) in Podcasts Repo ---")
    if args.wordlist_only:
        commit_message = f"Add {args.lang} vocabulary list for {args.feedname} - {args.date}"
    elif args.html_only:
        commit_message = f"Regenerate HTML player for {args.feedname} - {args.date}"
    else:
        commit_message = f"Add {args.lang} transcript and audio for {args.feedname} - {args.date}"
    
    # Stage files that exist in the repo
    for f in files_to_move:
        if os.path.exists(os.path.join(podcasts_repo_path, f)):
            run_command(["git", "add", f], cwd=podcasts_repo_path)
    
    run_command(["git", "commit", "-m", commit_message], cwd=podcasts_repo_path)
    run_command(["git", "push"], cwd=podcasts_repo_path)

    print(f"--- Workflow Complete! {args.lang} episode is live. ---")

if __name__ == "__main__":
    main()

