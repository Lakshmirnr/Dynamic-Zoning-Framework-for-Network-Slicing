# Dynamic Security Zoning for 5G Network Slices


1. `nwdaf_monitor.py` consumes anomaly events (synthetic events by default, or optional SMF-log monitoring).
2. The monitor writes a validated zone-change request to `runtime/smf_trigger.json`.
3. `smf_daemon.py` validates the requested zone against MongoDB's slice-zone document.
4. The daemon updates `current_zone` and invokes `apply_iptables.sh` to apply the corresponding policy.
5. The experiment scripts can inject a **synthetic PFCP/session-flood anomaly event** to test the full decision path. They do not generate or transmit PFCP packets.

## Repository layout

```text
.
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   └── slice_zone_map.example.json
├── src/
│   ├── nwdaf_monitor.py
│   └── smf_daemon.py
├── scripts/
│   ├── apply_iptables.sh
│   ├── seed_mongodb.py
│   ├── simulate_pfcp_anomaly.py
│   └── reset_demo.py
├── data/
│   └── sample_telemetry.csv
└── tests/
    └── test_event_rules.py
```

## Important notes

- The anomaly generator is a **synthetic event generator**, not a PFCP exploit or packet-flooding tool. It is provided to validate zone triggering in an isolated lab without attacking a network.
- The CSV file is **illustrative synthetic data** for testing plotting code and the repository workflow. It is not experimental evidence and must not be reported as measured results.
- The default configuration uses `DRY_RUN=1`; no firewall rules are changed until explicitly disabled.
- The firewall script uses a dedicated `DSZ_SLICE` chain instead of flushing the global `FORWARD` chain. Review the subnet and policy semantics before using it on a live host.
-

## Requirements

- Python 3.10+
- MongoDB reachable at the configured URI
- `pymongo`
- Linux `iptables` only if applying firewall rules for real
- Open5gs and UERANSIM

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The scripts read environment variables directly. For convenience, export the variables from `.env` before running:

```bash
set -a
source .env
set +a
```

## 1. Configure MongoDB

The default database and collection are `open5gs.open5gs_slice_zone_map`. 
```bash
python scripts/seed_mongodb.py
```

The seed script inserts or replaces the configured slice document with `current_zone=zone3` and three demo zones. Check the names and subnet against your testbed before use.

Example document:

```json
{
  "sst": 1,
  "sd": 1,
  "current_zone": "zone3",
  "zones": [
    {"zone1": {"firewall": "strict"}},
    {"zone2": {"firewall": "medium"}},
    {"zone3": {"firewall": "none"}}
  ]
}
```

In this demo, `zone3` is the permissive baseline, `zone2` is the intermediate policy, and `zone1` is the restrictive policy. 

## 2. Start the zone reassignment daemon

In terminal 1:

```bash
python src/smf_daemon.py
```

The daemon applies the current policy in dry-run mode and polls for validated zone-change requests.

## 3. Start the monitor

In terminal 2:

```bash
python src/nwdaf_monitor.py
```

The default monitor watches `runtime/events.jsonl`. The directory and event file are created automatically.

## 4. Trigger a controlled anomaly event

In terminal 3:

```bash
python scripts/simulate_pfcp_anomaly.py --event session_flood --count 120 --threshold 80
```

The script writes a synthetic telemetry event. If the count exceeds the threshold, the monitor requests `zone2`. The daemon validates the request and updates MongoDB. This tests the event-to-zone-assignment pipeline without transmitting attack traffic.

To request the stricter zone for a higher-severity test:

```bash
python scripts/simulate_pfcp_anomaly.py --event malformed_pfcp --count 50 --threshold 10 --zone zone1
```

## Optional: monitor an existing SMF log

Set `MONITOR_MODE=smf_log` and `SMF_LOG_PATH` to a log file you own and have permission to read. The log monitor uses a configurable regular expression. Avoid treating ordinary session establishment as an attack indicator; the default pattern is intentionally an explicit anomaly keyword. Real detection should be based on validated telemetry, not a single generic “session added” message.

## Firewall policy behavior

- `none`: removes rules from the dedicated `DSZ_SLICE` chain; it does not change the global `FORWARD` policy.
- `medium`: permits TCP/UDP DNS traffic (port 53) from the configured slice subnet and drops other forwarded traffic from that subnet.
- `strict`: drops forwarded traffic from the configured slice subnet.

They may interrupt service. Keep `DRY_RUN=1` for initial testing.

## Reproducibility data

`data/sample_telemetry.csv` contains synthetic rows for exercising plots and sanity checks. Replace them with timestamped measurements from your own repeated runs before making claims about compliance distributions, migration delay, latency, signaling overhead, session disruption, or reconfiguration frequency.

## Suggested experiments

Record at least:
- run ID and start/end timestamps;
- slice SST/SD and zone before/after;
- anomaly type, observed count, and threshold;
- detection-to-trigger delay and trigger-to-policy-application delay;
- control-plane latency (P50/P90/P99) with and without the framework;
- signaling rate and legitimate session disruption;
- repeated trials and false-positive/false-negative counts.

