import json
import tempfile
import unittest
from pathlib import Path

from hand_visual_state import write_hand_state


class HandVisualStateTests(unittest.TestCase):
    def test_write_hand_state_creates_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "hand_state.json"
            payload = write_hand_state("ouvrir", target=target)

            self.assertTrue(target.exists())
            self.assertEqual(payload["state"], "ouvrir")
            self.assertEqual(payload["source"], "raspberry")
            with target.open("r", encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["state"], "ouvrir")


if __name__ == "__main__":
    unittest.main()
