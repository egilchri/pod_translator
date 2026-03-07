import sys
import os

# The "Source of Truth" for your project's features
REGISTRY = {
    "svdownload.py": {
        "Rate Limiting (Sleep)": "time.sleep(0.5)",
        "Audio Status Indicators": "async function checkAudioStatus()",
        "Relative Path Support": 'sources = {{ orig: "{audio_file}"',
        "Interleaved Synthesis": "combined_audio += orig_audio_seg",
        "Mobile-Friendly Viewport": '<meta name="viewport" content="width=device-width'
    },
    # Future-proofing: You can add other scripts here
    "build_audio.py": {
        "HTML Generation": "html_template =",
        "Audio Processing": "AudioSegment.from_mp3"
    },
    "show_general_feed.py": {
        "Async Live Check": "async function checkLiveStatus",
        "MP3 URL Construction": 'expected_mp3_url = f"{base_gh_url}/{feed_name_attr}.{date_param}.mp3"',
        "Status Tag Initialization": 'class="status-tag tag-checking">Checking...</span>',
        "JS Execution Trigger": 'script>checkLiveStatus({i}, "{expected_mp3_url}");</script>',
        "RSS Metadata Storage": 'data-rss-url="{url}"'
    }
}

def verify_script_health(script_name):
    """
    Checks a specific script for required features defined in the REGISTRY.
    Returns True if healthy, exits the program if a regression is found.
    """
    if script_name not in REGISTRY:
        print(f"⚠️  No health rules defined for {script_name}. Skipping check.")
        return True

    if not os.path.exists(script_name):
        print(f"❌ ERROR: {script_name} is missing from the directory.")
        sys.exit(1)

    with open(script_name, "r") as f:
        content = f.read()

    missing = []
    features = REGISTRY[script_name]
    
    for feature_name, snippet in features.items():
        if snippet not in content:
            missing.append(feature_name)

    if missing:
        print(f"\n⚠️  REGRESSION ALERT in {script_name}:")
        for item in missing:
            print(f"  - MISSING FEATURE: {item}")
        print("\nAborting to prevent broken output. Please restore the missing code.")
        sys.exit(1)
    
    print(f"✅ {script_name} health check passed.")
    return True

if __name__ == "__main__":
    # If run directly, check everything in the registry
    print("--- Running Global Project Health Check ---")
    for script in REGISTRY.keys():
        if os.path.exists(script):
            verify_script_health(script)

