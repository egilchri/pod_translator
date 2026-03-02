import os
import shutil
import sys
import re
import subprocess 

def run_command(command_list, cwd=None):
    try:
        subprocess.run(command_list, check=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        if "commit" in str(command_list):
            print("No changes to commit for the index.")
        else:
            print(f"Error executing git command: {e}")
            sys.exit(1)

def extract_metadata(filepath):
    """Extracts metadata precisely to avoid attribute spill-over."""
    title, lang, is_override, rss_url = "Unknown Podcast", "??", False, "#"
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Precise Title Extraction
            t_match = re.search(r'<title>(.*?)</title>', content)
            if t_match: title = t_match.group(1).split(' - ')[0]
            
            # Precise Language Extraction (stops at first closing quote)
            l_match = re.search(r'<html lang="([^"]+)"', content)
            if l_match: lang = l_match.group(1).upper()
            
            # Metadata Flags
            is_override = 'data-is-override="true"' in content
            
            # Extract the actual feed URL from metadata
            r_match = re.search(r'data-rss-url="([^"]+)"', content)
            if r_match: rss_url = r_match.group(1)
                
    except Exception as e:
        print(f"Warning parsing {filepath}: {e}")
    return title, lang, is_override, rss_url

def generate_index_html(podcasts_dir):
    root_url = "https://egilchri.github.io/pod_tran"
    files = [f for f in os.listdir(podcasts_dir) if f.endswith(".feed.html")]
    files.sort()

    table_rows = ""
    for filename in files:
        full_path = os.path.join(podcasts_dir, filename)
        title, lang, is_override, rss_url = extract_metadata(full_path)
        
        # Color-coded Sync Mode labels
        status_label = '<span style="color:#d97706; font-weight:bold; font-size:0.75em;">MANUAL</span>' if is_override else '<span style="color:#059669; font-weight:bold; font-size:0.75em;">AUTO</span>'
        
        # Clean Feed Link (shortened for display)
        feed_link = f'<a href="{rss_url}" target="_blank" style="text-decoration:none; font-size:0.8em; color:#6366f1;">🔗 RSS Feed</a>' if rss_url != "#" else '<span style="color:#94a3b8; font-size:0.8em;">No URL Saved</span>'

        table_rows += f"""
            <tr>
                <td><strong>{title}</strong></td>
                <td><code style="background:#f1f5f9; padding:3px 6px; border-radius:4px; font-size:0.85em;">{lang}</code></td>
                <td style="text-align:center;">{status_label}</td>
                <td>{feed_link}</td>
                <td><a href="{root_url}/{filename}" style="color: #1e40af; font-weight: bold; text-decoration: none; border: 1px solid #1e40af; padding: 6px 12px; border-radius: 6px; font-size: 0.85em; display: inline-block;">Open Dashboard</a></td>
            </tr>"""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verified Politics Feeds Index</title>
        <style>
            body {{ font-family: system-ui, -apple-system, sans-serif; margin: 40px; background: #f8fafc; color: #1e293b; line-height: 1.5; }}
            .container {{ max-width: 1100px; margin: 0 auto; background: white; padding: 40px; border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1); }}
            h1 {{ color: #1e3a8a; border-bottom: 4px solid #1e3a8a; padding-bottom: 12px; margin-top: 0; font-size: 2em; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 25px; }}
            th {{ background-color: #1e3a8a; color: white; text-align: left; padding: 16px; text-transform: uppercase; font-size: 0.75em; letter-spacing: 0.05em; }}
            td {{ padding: 16px; border-bottom: 1px solid #e2e8f0; }}
            tr:hover {{ background-color: #f1f5f9; }}
            footer {{ margin-top: 50px; padding-top: 25px; border-top: 1px solid #e2e8f0; font-size: 0.8em; color: #64748b; }}
            .disclaimer {{ background: #f1f5f9; padding: 20px; border-radius: 10px; margin-top: 15px; font-style: italic; border-left: 5px solid #cbd5e1; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Verified Politics Feeds Index</h1>
            <table>
                <thead>
                    <tr>
                        <th style="width: 35%;">Podcast Title</th>
                        <th style="width: 10%;">Lang</th>
                        <th style="width: 15%; text-align:center;">Sync Mode</th>
                        <th style="width: 20%;">Feed URL</th>
                        <th style="width: 20%;">Action</th>
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
    
    run_command(["git", "add", index_filename], cwd=repo_path)
    run_command(["git", "commit", "-m", "Improved column layout with dedicated Feed URL column"], cwd=repo_path)
    run_command(["git", "push"], cwd=repo_path)

if __name__ == "__main__":
    main()

