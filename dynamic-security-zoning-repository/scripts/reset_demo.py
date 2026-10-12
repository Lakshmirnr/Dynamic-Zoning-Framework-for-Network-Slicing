"""Reset the demo event/trigger files. Does not change firewall rules or MongoDB."""
import os
from pathlib import Path

for item in [
    Path(os.getenv("EVENT_FILE", "runtime/events.jsonl")),
    Path(os.getenv("TRIGGER_FILE", "runtime/smf_trigger.json")),
]:
    item.parent.mkdir(parents=True, exist_ok=True)
    item.write_text("", encoding="utf-8")
    print(f"Cleared {item}")
