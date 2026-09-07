import tempfile
import unittest
from pathlib import Path

from tools import run_classeval_image_text_blind_smoke as smoke


class BlindImageSmokeTests(unittest.TestCase):
    def test_prompt_has_schema_but_no_source_answers(self):
        smoke.assert_blind_prompt()
        self.assertIn(smoke.SOURCE_ID, smoke.PROMPT)
        self.assertNotIn(smoke.TARGET_LINES[0], smoke.PROMPT)
        self.assertNotIn(smoke._sha_bytes(smoke.SOURCE_TEXT.encode()), smoke.PROMPT)

    def test_manifest_reconstructs_losslessly(self):
        with tempfile.TemporaryDirectory(prefix="blind-image-test-") as temp:
            manifest = smoke.render_text_pages(smoke.SOURCE_TEXT, smoke.SOURCE_ID,
                                               Path(temp) / "images", font_path=smoke.FONT,
                                               width=1800, rows_per_page=42)
            self.assertEqual(smoke.reconstruct_manifest_text(manifest), smoke.SOURCE_TEXT)
            self.assertEqual(manifest["textSha256"],
                             smoke._sha_bytes(smoke.SOURCE_TEXT.encode()))
            self.assertEqual(len(manifest["pages"]), 1)
            self.assertGreaterEqual(len(manifest["pages"][0]["rows"]), 35)


if __name__ == "__main__":
    unittest.main()
