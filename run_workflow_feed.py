import argparse
import subprocess
import os
import sys
import shutil

def run_command_with_output(command_list, cwd=None):
    """Utility to run shell commands and capture their output."""
    try:
        result = subprocess.run(command_list, check=True, cwd=cwd, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e.stderr}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Master Workflow: Automated Feed Builder.")
    parser.add_argument("--url", required=True, help="The RSS feed URL")
    parser.add_argument("--lang", help="Optional: Override language detection (e.g., 'fr', 'es')")
    args = parser.parse_args()

    podcasts_repo_path = os.path.abspath("Podcasts")

    # 1. Run the processing script and pass the optional language override
    print(f"--- Generating Feed Dashboard for {args.url} ---")
    gen_cmd = ["python3", "show_general_feed.py", "--url", args.url]
    if args.lang:
        gen_cmd.extend(["--lang", args.lang])
        
    stdout_output = run_command_with_output(gen_cmd)

    # 2. Extract feedname and lang from the script output
    feedname = None
    lang = args.lang if args.lang else "unknown"
    for line in stdout_output.splitlines():
        if line.startswith("FEEDNAME_OUTPUT:"):
            feedname = line.replace("FEEDNAME_OUTPUT:", "").strip()
        if not args.lang and line.startswith("LANG_OUTPUT:"):
            lang = line.replace("LANG_OUTPUT:", "").strip()

    if not feedname:
        print("[!] Error: show_general_feed.py failed to return a feedname.")
        sys.exit(1)

    print(f"--- Detected Feed: {feedname} (Language: {lang}) ---")

    # 3. Define and move the generated files
    prefix = feedname
    feed_file = f"{prefix}.feed.html"

    if not os.path.exists(podcasts_repo_path):
        print(f"[!] Error: Podcasts directory not found at {podcasts_repo_path}")
        sys.exit(1)

    if os.path.exists(feed_file):
        print(f"--- Moving {feed_file} to {podcasts_repo_path} ---")
        dest = os.path.join(podcasts_repo_path, feed_file)
        if os.path.exists(dest):
            os.remove(dest)
        shutil.move(feed_file, dest)
    else:
        print(f"[!] Warning: {feed_file} was not generated.")
        sys.exit(1)

    # 4. Git Operations
    print(f"--- Staging and Pushing to Repository ---")
    commit_message = f"Update feed: {prefix} ({lang})"
    
    try:
        subprocess.run(["git", "add", feed_file], cwd=podcasts_repo_path, check=True)
        subprocess.run(["git", "commit", "-m", commit_message], cwd=podcasts_repo_path, check=True)
        subprocess.run(["git", "push"], cwd=podcasts_repo_path, check=True)
        print(f"--- Workflow Complete! {prefix} dashboard is live. ---")
    except subprocess.CalledProcessError:
        print("Nothing to commit (or git error), skipping push.")

if __name__ == "__main__":
    main()

