"""Zone reassignment daemon.

Reads validated zone requests, looks up the firewall policy in MongoDB, updates
the selected slice's current zone, and applies policy only when DRY_RUN=0.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

from pymongo import MongoClient

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017/")
DATABASE = os.getenv("MONGODB_DATABASE", "open5gs")
COLLECTION = os.getenv("MONGODB_COLLECTION", "open5gs_slice_zone_map")
SLICE_SST = int(os.getenv("SLICE_SST", "1"))
SLICE_SD = int(os.getenv("SLICE_SD", "1"))
SLICE_SUBNET = os.getenv("SLICE_SUBNET", "10.45.0.0/24")
TRIGGER_FILE = Path(os.getenv("TRIGGER_FILE", "runtime/smf_trigger.json"))
DRY_RUN = os.getenv("DRY_RUN", "1").strip().lower() not in {"0", "false", "no"}
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "0.5"))
FIREWALL_SCRIPT = Path(os.getenv("FIREWALL_SCRIPT", "scripts/apply_iptables.sh"))

def find_policy(document: dict, zone: str):
    for zone_data in document.get("zones", []):
        if zone in zone_data:
            return zone_data[zone].get("firewall")
    return None

def apply_policy(policy: str) -> None:
    if policy not in {"none", "medium", "strict"}:
        raise ValueError(f"Unsupported firewall policy: {policy}")
    if DRY_RUN:
        print(f"[daemon][DRY RUN] would apply policy={policy}, subnet={SLICE_SUBNET}")
        return
    subprocess.run(
        ["sudo", str(FIREWALL_SCRIPT), SLICE_SUBNET, policy],
        check=True,
    )
    print(f"[daemon] firewall policy applied: {policy}")

def process_trigger(collection) -> None:
    if not TRIGGER_FILE.exists():
        return
    try:
        payload = json.loads(TRIGGER_FILE.read_text(encoding="utf-8"))
        zone = str(payload.get("requested_zone", "")).strip()
        if not re.fullmatch(r"zone[1-9][0-9]*", zone):
            raise ValueError("Invalid requested_zone")
        doc = collection.find_one({"sst": SLICE_SST, "sd": SLICE_SD})
        if not doc:
            raise RuntimeError(f"No slice document for SST={SLICE_SST}, SD={SLICE_SD}")
        policy = find_policy(doc, zone)
        if policy not in {"none", "medium", "strict"}:
            raise ValueError(f"No valid firewall policy configured for {zone}")

        if doc.get("current_zone") == zone:
            print(f"[daemon] slice already assigned to {zone}; no change")
            return

        apply_policy(policy)
        collection.update_one(
            {"sst": SLICE_SST, "sd": SLICE_SD},
            {"$set": {
                "current_zone": zone,
                "last_zone_change_at": time.time(),
                "last_zone_change_reason": payload.get("event_type", "unspecified"),
            }},
        )
        print(
            f"[daemon] zone changed to {zone}; policy={policy}; "
            f"reason={payload.get('event_type', 'unspecified')}"
        )
    finally:
        # Consume request even if invalid to avoid a tight retry loop.
        TRIGGER_FILE.unlink(missing_ok=True)

def main() -> None:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        collection = client[DATABASE][COLLECTION]
        print(f"[daemon] connected to MongoDB {DATABASE}.{COLLECTION}; DRY_RUN={DRY_RUN}")
        while True:
            try:
                process_trigger(collection)
            except Exception as exc:
                print(f"[daemon] request failed: {exc}")
            time.sleep(POLL_INTERVAL)
    finally:
        client.close()

if __name__ == "__main__":
    main()
