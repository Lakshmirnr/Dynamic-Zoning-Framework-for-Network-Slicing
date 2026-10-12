"""Generate a synthetic anomaly event to test zone triggering.

This script deliberately does not craft or transmit PFCP packets. It writes one
telemetry record to EVENT_FILE so the end-to-end control path can be validated.
"""
import argparse
import json
import os
import time
import uuid
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--event", choices=["session_flood", "malformed_pfcp", "high_session_rate"],
                    default="session_flood")
parser.add_argument("--count", type=float, default=120,
                    help="Synthetic observed event count/rate (no packets are sent)")
parser.add_argument("--threshold", type=float, default=80)
parser.add_argument("--zone", default=None, help="Optional explicit target zone, e.g. zone1")
args = parser.parse_args()

event_file = Path(os.getenv("EVENT_FILE", "runtime/events.jsonl"))
event_file.parent.mkdir(parents=True, exist_ok=True)
event = {
    "event_id": str(uuid.uuid4()),
    "timestamp": time.time(),
    "event_type": args.event,
    "observed_count": args.count,
    "threshold": args.threshold,
    "source": "synthetic_lab_generator",
}
if args.zone:
    event["target_zone"] = args.zone

with event_file.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(event) + "\n")
print(f"Synthetic event written to {event_file}: {json.dumps(event)}")
print("No PFCP packets were generated or transmitted.")
