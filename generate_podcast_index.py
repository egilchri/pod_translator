import os
import shutil
import sys
import re

def extract_metadata(filepath):
    title, lang, is_override = "Unknown Podcast", "Unknown", False
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            title_match = re.search(r'<title>(.*?)</title>', content)
            if title_match: title = title_match.group(1).split(' - ')[0]
            lang_match = re.search(r'<html lang="(.*?)">', content)
            if lang_match: lang = lang_match.group(1).upper()
            
            # Detect the override flag
            if 'data-is-override="true"' in content:
                is_override = True
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
    return title, lang, is_override

def generate_index_html(podcasts_dir):
    root_url = "https://egilchri.github.io/pod_tran"
    files = [f for f in os.listdir(podcasts_dir) if f.endswith(".feed.html")]
    files.sort()

    table_rows = ""
    for filename in files:
        full_path = os.path.join(podcasts_dir, filename)
        title, lang, is_override = extract_metadata(full_path)
        file_url = f"{root_url}/{filename}"
        
        # Add an asterisk to overridden languages
        lang_display = f"{lang}*" if is_override else lang
        
        table_rows += f"""
            <tr>
                <td><strong>{title}</strong></td>
                <td>
                    <code style="background:#eee; padding:2px 5px;">{lang_display}</code>
                    {"<br><small style='color:orange;'>Manual Override</small>" if is_override else ""}
                </td>
                <td><a href="{file_url}">View Dashboard</a></td>
            </tr>"""

    # ... wrap table_rows in full HTML template as previously defined ...
    return "index.html"
