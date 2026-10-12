"""Insert/update the demo slice-zone document in MongoDB."""
import json
import os
from pathlib import Path
from pymongo import MongoClient

uri = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017/")
database = os.getenv("MONGODB_DATABASE", "open5gs")
collection_name = os.getenv("MONGODB_COLLECTION", "open5gs_slice_zone_map")
sst = int(os.getenv("SLICE_SST", "1"))
sd = int(os.getenv("SLICE_SD", "1"))

document = {
    "sst": sst,
    "sd": sd,
    "current_zone": "zone3",
    "zones": [
        {"zone1": {"firewall": "strict"}},
        {"zone2": {"firewall": "medium"}},
        {"zone3": {"firewall": "none"}},
    ],
}
client = MongoClient(uri, serverSelectionTimeoutMS=5000)
try:
    client.admin.command("ping")
    result = client[database][collection_name].replace_one(
        {"sst": sst, "sd": sd}, document, upsert=True
    )
    print(f"Seeded slice document (matched={result.matched_count}, upserted_id={result.upserted_id})")
finally:
    client.close()
