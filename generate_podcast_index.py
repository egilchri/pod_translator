import os
import argparse
import subprocess
import shutil
import sys
import re

def run_command(command_list, cwd=None):
    try:
        subprocess.run(command_list, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        if "commit" in str(command_list):
            print("No changes to commit for the index.")
        else:
            print(f"Error: {e}")
            sys.exit(1)

def extract_metadata(filepath):
    """Extracts the title and language from the generated .feed.html file."""
    title = "Unknown Podcast"
    lang = "Unknown"
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            title_match = re.search(r'<title>(.*?)</title>', content)
            if title_match:
                title = title_match.group(1).split(' - ')[0]
            lang_match = re.search(r'<html lang="(.*?)">', content)
            if lang_match:
                lang = lang_match.group(1).upper()
    except Exception as e:
        print(f"Warning: Could not parse {filepath}: {e}")
    return title, lang

def generate_index_html(podcasts_dir):
    root_url = "https://egilchri.github.io/pod_tran"
    files = [f for f in os.listdir(podcasts_dir) if f.endswith(".feed.html")]
    files.sort()

    table_rows = ""
    for filename in files:
        full_path = os.path.join(podcasts_dir, filename)
        title, lang = extract_metadata(full_path)
        file_url = f"{root_url}/{filename}"
        
        # Removed target="_blank" to open in the same window
        table_rows += f"""
            <tr>
                <td><strong>{title}</strong></td>
                <td><code style="background:#eee; padding:2px 5px; border-radius:3px;">{lang}</code></td>
                <td><a href="{file_url}" style="color: #004a99; text-decoration: none; font-weight: bold; border: 1px solid #004a99; padding: 5px 10px; border-radius: 4px;">View Dashboard</a></td>
            </tr>"""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Podcast Feed Index</title>
        <style>
            body {{ font-family: system-ui, -apple-system, sans-serif; margin: 40px; background: #f4f4f9; color: #333; }}
            h1 {{ color: #004a99; border-bottom: 2px solid #004a99; padding-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 15px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }}
            th, td {{ padding: 15px; border-bottom: 1px solid #ddd; text-align: left; }}
            th {{ background-color: #004a99; color: white; text-transform: uppercase; font-size: 0.85em; }}
            tr:hover {{ background-color: #f9f9f9; }}
        </style>
    </head>
    <body>
        <h1>Verified Politics Feeds Index</h1>
        <table>
            <thead>
                <tr>
                    <th>Podcast Title</th>
                    <th>Language</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        <p style="margin-top:20px; font-size:0.8em; color:#666;">Generated on: {os.popen('date').read()}</p>
    </body>
    </html>
    """
    index_file = "index.html"
    with open(index_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    return index_file

def main():
    podcasts_repo_path = os.path.abspath("Podcasts")
    if not os.path.exists(podcasts_repo_path):
        print(f"[!] Error: {podcasts_repo_path} not found.")
        sys.exit(1)
    index_filename = generate_index_html(podcasts_repo_path)
    dest = os.path.join(podcasts_repo_path, index_filename)
    if os.path.exists(dest):
        os.remove(dest)
    shutil.move(index_filename, dest)
    run_command(["git", "add", index_filename], cwd=podcasts_repo_path)
    run_command(["git", "commit", "-m", "Update index: same-window navigation"], cwd=podcasts_repo_path)
    run_command(["git", "push"], cwd=podcasts_repo_path)

if __name__ == "__main__":
    main()

