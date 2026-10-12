"""Telemetry event monitor for the dynamic security zoning prototype.

Default mode consumes JSON Lines events from EVENT_FILE. Optional smf_log mode
watches an existing SMF log for an explicit anomaly pattern. It does not send
network traffic.
"""
import json
import os
import re
import time
from pathlib import Path

EVENT_FILE = Path(os.getenv("EVENT_FILE", "runtime/events.jsonl"))
TRIGGER_FILE = Path(os.getenv("TRIGGER_FILE", "runtime/smf_trigger.json"))
MONITOR_MODE = os.getenv("MONITOR_MODE", "events").strip().lower()
SMF_LOG_PATH = os.getenv("SMF_LOG_PATH", "/var/log/open5gs/smf.log")
ANOMALY_PATTERN = re.compile(os.getenv(
    "ANOMALY_PATTERN", r"ANOMALY|PFCP_FLOOD|MALFORMED_PFCP"
), re.IGNORECASE)
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "0.5"))

# Explicit event-to-zone mapping; adjust to match the zone semantics in the paper.
ZONE_BY_EVENT = {
    "session_flood": "zone2",
    "malformed_pfcp": "zone1",
    "high_session_rate": "zone2",
}

def request_zone(zone: str, event: dict) -> None:
    """Atomically publish a validated, auditable zone-change request."""
    TRIGGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "requested_zone": zone,
        "event_type": str(event.get("event_type", "unknown")),
        "observed_count": event.get("observed_count"),
        "threshold": event.get("threshold"),
        "event_id": event.get("event_id"),
        "timestamp": event.get("timestamp") or time.time(),
        "source": event.get("source", "telemetry"),
    }
    tmp = TRIGGER_FILE.with_suffix(TRIGGER_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(TRIGGER_FILE)
    print(f"[monitor] zone request written: {zone}; event={payload['event_type']}")

def handle_event(event: dict) -> bool:
    """Return True when an event crosses its threshold and maps to a zone."""
    event_type = str(event.get("event_type", "")).strip().lower()
    try:
        observed = float(event["observed_count"])
        threshold = float(event["threshold"])
    except (KeyError, TypeError, ValueError):
        print(f"[monitor] ignored event with missing/invalid count or threshold: {event}")
        return False

    if observed <= threshold:
        print(f"[monitor] no trigger: {event_type} count={observed:g} threshold={threshold:g}")
        return False

    zone = str(event.get("target_zone") or ZONE_BY_EVENT.get(event_type, "")).strip()
    if not re.fullmatch(r"zone[1-9][0-9]*", zone):
        print(f"[monitor] no zone mapping for event type: {event_type}")
        return False

    request_zone(zone, event)
    return True

def run_event_monitor() -> None:
    EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    EVENT_FILE.touch(exist_ok=True)
    print(f"[monitor] reading synthetic/telemetry events from {EVENT_FILE}")
    # Track byte offset so only newly appended JSONL records are processed.
    offset = EVENT_FILE.stat().st_size
    while True:
        try:
            with EVENT_FILE.open("r", encoding="utf-8") as stream:
                stream.seek(offset)
                for line in stream:
                    offset = stream.tell()
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        print("[monitor] ignored malformed JSON event")
                        continue
                    handle_event(event)
                offset = stream.tell()
        except FileNotFoundError:
            EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
            EVENT_FILE.touch(exist_ok=True)
            offset = 0
        time.sleep(POLL_INTERVAL)

def run_smf_log_monitor() -> None:
    """Optional log watcher; requires read permission for the configured log."""
    path = Path(SMF_LOG_PATH)
    print(f"[monitor] watching SMF log {path}")
    offset = path.stat().st_size if path.exists() else 0
    while True:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as stream:
                stream.seek(offset)
                for line in stream:
                    offset = stream.tell()
                    if ANOMALY_PATTERN.search(line):
                        # Log mode only recognizes explicit anomaly labels.
                        event = {
                            "event_type": "malformed_pfcp",
                            "observed_count": 1,
                            "threshold": 0,
                            "source": "smf_log",
                            "timestamp": time.time(),
                        }
                        handle_event(event)
                offset = stream.tell()
        except FileNotFoundError:
            pass
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    if MONITOR_MODE == "smf_log":
        run_smf_log_monitor()
    elif MONITOR_MODE == "events":
        run_event_monitor()
    else:
        raise SystemExit("MONITOR_MODE must be 'events' or 'smf_log'")
