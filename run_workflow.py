import argparse
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
    # Added language parameter
    parser.add_argument("--lang", default="sv", help="ISO Language code (e.g. sv, no, de)")
    
    args = parser.parse_args()

    # 1. Path to your separate Podcasts repository
    podcasts_repo_path = os.path.abspath("Podcasts")

    # 2. Run the processing script with the language parameter
    print(f"--- Starting Processing for {args.url} in {args.lang} ---")
    run_command([
        "python3", "svdownload.py", 
        "--url", args.url, 
        "--feedname", args.feedname, 
        "--date", args.date, 
        "--title", args.title,
        "--lang", args.lang
    ])

    # 3. Define the generated filenames
    prefix = f"{args.feedname}.{args.date}"
    transcript_name = f"transcript.{args.feedname}.{args.date}.json"
    files_to_move = [
        f"{prefix}.mp3",
        f"{prefix}.html",
        f"{transcript_name}"
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
    commit_message = f"Add {args.lang} transcript and audio for {args.feedname} - {args.date}"
    
    for f in files_to_move:
        run_command(["git", "add", f], cwd=podcasts_repo_path)
    
    run_command(["git", "commit", "-m", commit_message], cwd=podcasts_repo_path)
    run_command(["git", "push"], cwd=podcasts_repo_path)

    print(f"--- Workflow Complete! {args.lang} episode is live. ---")

if __name__ == "__main__":
    main()

