import os
import shutil
import sys
import re
import subprocess  # Fixed the missing import regression

def run_command(command_list, cwd=None):
    """Executes git commands to sync the index with GitHub."""
    try:
        subprocess.run(command_list, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        if "commit" in str(command_list):
            print("No changes to commit for the index.")
        else:
            print(f"Error executing git command: {e}")
            sys.exit(1)

def extract_metadata(filepath):
    """Extracts metadata precisely to avoid attribute spill-over in columns."""
    title, lang, is_override, rss_url = "Unknown Podcast", "??", False, "#"
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Precise Title Extraction
            t_match = re.search(r'<title>(.*?)</title>', content)
            if t_match: title = t_match.group(1).split(' - ')[0]
            
            # Precise Language Extraction (prevents capturing data- attributes)
            l_match = re.search(r'<html lang="([^"]+)"', content)
            if l_match: lang = l_match.group(1).upper()
            
            # Metadata Flags
            is_override = 'data-is-override="true"' in content
            
            r_match = re.search(r'data-rss-url="([^"]+)"', content)
            if r_match: rss_url = r_match.group(1)
                
    except Exception as e:
        print(f"Warning parsing {filepath}: {e}")
    return title, lang, is_override, rss_url

def generate_index_html(podcasts_dir):
    """Generates the multi-column index with legal disclaimer."""
    root_url = "https://egilchri.github.io/pod_tran"
    files = [f for f in os.listdir(podcasts_dir) if f.endswith(".feed.html")]
    files.sort()

    table_rows = ""
    for filename in files:
        full_path = os.path.join(podcasts_dir, filename)
        title, lang, is_override, rss_url = extract_metadata(full_path)
        
        # New Sync Mode logic for the dedicated column
        status_label = '<span style="color:orange; font-weight:bold; font-size:0.8em;">MANUAL OVERRIDE</span>' if is_override else '<span style="color:gray; font-size:0.8em;">AUTO</span>'

        table_rows += f"""
            <tr>
                <td><strong>{title}</strong></td>
                <td><code style="background:#eee; padding:2px 5px; border-radius:3px;">{lang}</code></td>
                <td>{status_label}</td>
                <td><a href="{rss_url}" target="_blank" style="text-decoration:none; font-size:0.9em;">🔗 RSS Source</a></td>
                <td><a href="{root_url}/{filename}" style="color: #004a99; font-weight: bold; text-decoration: none; border: 1px solid #004a99; padding: 5px 10px; border-radius: 4px;">View Dashboard</a></td>
            </tr>"""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verified Politics Feeds Index</title>
        <style>
            body {{ font-family: system-ui, -apple-system, sans-serif; margin: 40px; background: #f4f4f9; color: #333; line-height: 1.5; }}
            .container {{ max-width: 1100px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
            h1 {{ color: #004a99; border-bottom: 3px solid #004a99; padding-bottom: 10px; margin-top: 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th {{ background-color: #004a99; color: white; text-align: left; padding: 15px; text-transform: uppercase; font-size: 0.8em; letter-spacing: 1px; }}
            td {{ padding: 15px; border-bottom: 1px solid #eee; }}
            tr:hover {{ background-color: #fcfcfc; }}
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
                        <th>Podcast</th>
                        <th>Lang</th>
                        <th>Sync Mode</th>
                        <th>Source</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>{table_rows}</tbody>
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
    repo_path = os.path.abspath("Podcasts")
    if not os.path.exists(repo_path):
        print(f"[!] Error: {repo_path} not found.")
        sys.exit(1)
        
    index_filename = generate_index_html(repo_path)
    dest = os.path.join(repo_path, index_filename)
    
    if os.path.exists(dest):
        os.remove(dest)
    shutil.move(index_filename, dest)
    
    # Automated Git Sync restored
    run_command(["git", "add", index_filename], cwd=repo_path)
    run_command(["git", "commit", "-m", "Fixed metadata column display and restored Git sync"], cwd=repo_path)
    run_command(["git", "push"], cwd=repo_path)

if __name__ == "__main__":
    main()
    
