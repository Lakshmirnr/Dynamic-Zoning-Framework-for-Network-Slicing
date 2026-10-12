import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).parents[1] / "src" / "nwdaf_monitor.py"
spec = importlib.util.spec_from_file_location("nwdaf_monitor", MODULE_PATH)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)

class EventRuleTests(unittest.TestCase):
    def test_event_above_threshold_requests_zone(self):
        with tempfile.TemporaryDirectory() as tmp:
            trigger = Path(tmp) / "trigger.json"
            with patch.object(monitor, "TRIGGER_FILE", trigger):
                ok = monitor.handle_event({
                    "event_type": "session_flood",
                    "observed_count": 120,
                    "threshold": 80,
                    "event_id": "test-1",
                })
            self.assertTrue(ok)
            payload = json.loads(trigger.read_text())
            self.assertEqual(payload["requested_zone"], "zone2")

    def test_event_below_threshold_does_not_request_zone(self):
        with tempfile.TemporaryDirectory() as tmp:
            trigger = Path(tmp) / "trigger.json"
            with patch.object(monitor, "TRIGGER_FILE", trigger):
                ok = monitor.handle_event({
                    "event_type": "session_flood",
                    "observed_count": 60,
                    "threshold": 80,
                })
            self.assertFalse(ok)
            self.assertFalse(trigger.exists())

if __name__ == "__main__":
    unittest.main()
