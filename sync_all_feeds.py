import os
import re
import subprocess
import sys

def get_active_feeds(podcasts_dir):
    """Scans the Podcasts directory and extracts RSS URLs from existing dashboards."""
    feeds = []
    if not os.path.exists(podcasts_dir):
        return feeds

    for filename in os.listdir(podcasts_dir):
        if filename.endswith(".feed.html"):
            filepath = os.path.join(podcasts_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extract RSS URL and Language from the HTML metadata
                url_match = re.search(r'data-rss-url="([^"]+)"', content)
                lang_match = re.search(r'<html lang="([^"]+)"', content)
                is_override = 'data-is-override="true"' in content
                
                pattern_match = re.search(r'data-start-pattern="([^"]+)"', content)
                if url_match:
                    feeds.append({
                        "url": url_match.group(1),
                        "lang": lang_match.group(1) if lang_match and is_override else None,
                        "name": filename.replace(".feed.html", ""),
                        "start_pattern": pattern_match.group(1) if pattern_match else None,
                    })
    return feeds

def main():
    podcasts_dir = os.path.abspath("Podcasts")
    feeds = get_active_feeds(podcasts_dir)

    if not feeds:
        print("No active feeds found in the Podcasts directory.")
        return

    print(f"--- Found {len(feeds)} podcasts to sync ---")

    for feed in feeds:
        print(f"\n>>> Updating: {feed['name']}...")
        cmd = ["python3", "run_workflow_feed.py", "--url", feed['url']]
        if feed['lang']:
            cmd.extend(["--lang", feed['lang']])
        if feed.get('start_pattern'):
            cmd.extend(["--start-pattern", feed['start_pattern']])
        
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            print(f"Failed to update {feed['name']}, skipping...")

    print("\n--- All feeds updated. Rebuilding global index... ---")
    try:
        subprocess.run(["python3", "generate_podcast_index.py"], check=True)
        print("--- Global Sync Complete! ---")
    except subprocess.CalledProcessError:
        print("Error rebuilding index.")

if __name__ == "__main__":
    main()

