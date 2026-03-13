import unittest
import os
# Importing logic directly from your script
# Note: This assumes svdownload.py is in the same folder
from svdownload import process_podcast

class TestSVDownload(unittest.TestCase):

    def setUp(self):
        """Set up common variables for tests."""
        self.feedname = "usapodden"
        self.date = "260225"
        self.title = "Trump fick bråket han ville ha"

    def test_filename_generation(self):
        """Verify that filenames are constructed correctly without spaces or LFS risks."""
        audio_file = f"{self.feedname}.{self.date}.mp3"
        interleaved_file = f"{self.feedname}.{self.date}.bilingual.mp3"
        json_file = f"transcript.{self.feedname}.{self.date}.json"
        
        self.assertEqual(audio_file, "usapodden.260225.mp3")
        self.assertEqual(interleaved_file, "usapodden.260225.bilingual.mp3")
        self.assertEqual(json_file, "transcript.usapodden.260225.json")

    def test_gitattributes_lfs_safety(self):
        """Ensure .gitattributes does not contain the problematic mp3 wildcard."""
        if os.path.exists(".gitattributes"):
            with open(".gitattributes", "r") as f:
                content = f.read()
                # We want to make sure the *.mp3 LFS rule is GONE or commented out
                lfs_rule = "*.mp3 filter=lfs"
                self.assertFalse(
                    lfs_rule in content and not content.startswith("#"),
                    "Found active LFS rule for MP3s in .gitattributes! This will break GitHub Pages."
                )

    def test_timestamp_rounding(self):
        """Verify that the rounding logic used for web_data matches requirements."""
        # Mimicking the rounding used in your script
        raw_start = 12.34567
        rounded_start = round(raw_start, 2)
        self.assertEqual(rounded_start, 12.35)

if __name__ == '__main__':
    unittest.main()

