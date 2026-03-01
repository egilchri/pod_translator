import os
import argparse
import subprocess
import shutil
import sys
import re

def run_command(command_list, cwd=None):
    """Executes git commands to sync the index with GitHub."""
    try:
        subprocess.run(command_list, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        if "commit" in str(command_list):
            print("No changes to commit for the index.")
        else:
            print(f"Error: {e}")
            sys.exit(1)

def extract_metadata(filepath):
    """Extracts title, language, override status, and source RSS from the feed file."""
    title, lang, is_override, rss_url = "Unknown Podcast", "Unknown", False, "#"
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            title_match = re.search(r'<title>(.*?)</title>', content)
            if title_match: title = title_match.group(1).split(' - ')[0]
            
            lang_match = re.search(r'<html lang="(.*?)">', content)
            if lang_match: lang = lang_match.group(1).upper()
            
            # Detect manual override flag
            if 'data-is-override="true"' in content:
                is_override = True
            
            # Extract the source RSS URL
            rss_match = re.search(r'data-rss-url="(.*?)"', content)
            if rss_match: rss_url = rss_match.group(1)
                
    except Exception as e:
        print(f"Warning: Could not parse {filepath}: {e}")
    return title, lang, is_override, rss_url

def generate_index_html(podcasts_dir):
    root_url = "https://egilchri.github.io/pod_tran"
    files = [f for f in os.listdir(podcasts_dir) if f.endswith(".feed.html")]
    files.sort()

    table_rows = ""
    for filename in files:
        full_path = os.path.join(podcasts_dir, filename)
        title, lang, is_override, rss_url = extract_metadata(full_path)
        file_url = f"{root_url}/{filename}"
        
        lang_display = f"{lang}*" if is_override else lang
        override_note = '<br><small style="color:orange; font-size:0.7em;">Manual Override</small>' if is_override else ''

        table_rows += f"""
            <tr>
                <td><strong>{title}</strong></td>
                <td>
                    <code style="background:#eee; padding:2px 5px; border-radius:3px;">{lang_display}</code>
                    {override_note}
                </td>
                <td>
                    <a href="{file_url}" style="color: #004a99; text-decoration: none; font-weight: bold; border: 1px solid #004a99; padding: 5px 10px; border-radius: 4px; display: inline-block; margin-bottom: 5px;">View Dashboard</a>
                    <br><a href="{rss_url}" target="_blank" style="font-size:0.75em; color:#666; text-decoration:none;">🔗 Source RSS Feed</a>
                </td>
            </tr>"""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verified Politics Feeds Index</title>
        <style>
            body {{ font-family: system-ui, -apple-system, sans-serif; margin: 40px; background: #f4f4f9; color: #333; line-height: 1.5; }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            h1 {{ color: #004a99; border-bottom: 3px solid #004a99; padding-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 15px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; margin-top: 20px; }}
            th, td {{ padding: 18px; border-bottom: 1px solid #ddd; text-align: left; }}
            th {{ background-color: #004a99; color: white; text-transform: uppercase; font-size: 0.85em; letter-spacing: 1px; }}
            tr:hover {{ background-color: #f9f9f9; }}
            footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ccc; font-size: 0.85em; color: #666; }}
            .disclaimer {{ background: #eee; padding: 15px; border-radius: 8px; margin-top: 10px; font-style: italic; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Verified Politics Feeds Index</h1>
            <table>
                <thead>
                    <tr>
                        <th>Podcast Title</th>
                        <th>Language</th>
                        <th>Action & Source</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            <footer>
                <p><strong>Generated on:</strong> {os.popen('date').read().strip()}</p>
                <div class="disclaimer">
                    <strong>Legal Notice & Fair Use Disclaimer:</strong><br>
                    This repository is a personal research and educational project. All audio content and original show metadata are the property of their respective copyright owners. Translations and dashboards are provided for personal study and accessibility purposes under fair use principles. No commercial use is intended.
                </div>
            </footer>
        </div>
    </body>
    </html>
    """
    index_file = "index.html"
    with open(index_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    return index_file

def main():
    # Identify the correct local path for your Podcasts repo
    podcasts_repo_path = os.path.abspath("Podcasts")
    if not os.path.exists(podcasts_repo_path):
        print(f"[!] Error: {podcasts_repo_path} not found.")
        sys.exit(1)
        
    index_filename = generate_index_html(podcasts_repo_path)
    dest = os.path.join(podcasts_repo_path, index_filename)
    
    if os.path.exists(dest):
        os.remove(dest)
    shutil.move(index_filename, dest)
    
    # Automated Git Sync
    run_command(["git", "add", index_filename], cwd=podcasts_repo_path)
    run_command(["git", "commit", "-m", "Sync index with fair use disclaimer and RSS sources"], cwd=podcasts_repo_path)
    run_command(["git", "push"], cwd=podcasts_repo_path)

if __name__ == "__main__":
    main()

