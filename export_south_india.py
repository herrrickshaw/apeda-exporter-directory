import csv
import json
import sys
import time
import requests

API = "https://traceability.apeda.gov.in/apedamobile/api/apedaWebsite/ExporterDirectory_AllResult"

SOUTH_STATES = [
    ("AP", "Andhra Pradesh"),
    ("TG", "Telangana"),
    ("KA", "Karnataka"),
    ("KE", "Kerala"),
    ("TN", "Tamil Nadu"),
    ("PY", "Puducherry"),
]

COLS = ["rcmcno", "exporter_name", "keyPerson", "address", "city", "state", "pin",
        "email", "mobile", "expType", "expStatus", "qtyinMT", "valueinRsCrore"]

def fetch_state(code, name, retries=3):
    payload = {"qType": "13", "expName": "", "expState": code, "expType": "ALL", "expProduct": "0000"}
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(API, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            rows = data.get("table", [])
            print(f"{name} ({code}): {len(rows)} exporters", file=sys.stderr)
            return rows
        except Exception as e:
            print(f"  attempt {attempt} failed for {name}: {e}", file=sys.stderr)
            time.sleep(2)
    print(f"  giving up on {name}", file=sys.stderr)
    return []

def main():
    all_rows = []
    seen = set()
    for code, name in SOUTH_STATES:
        rows = fetch_state(code, name)
        for row in rows:
            key = row.get("rcmcno")
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(row)

    out_path = "south_india_exporters.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for row in all_rows:
            w.writerow(row)

    print(f"\nTotal unique exporters: {len(all_rows)}", file=sys.stderr)
    print(f"Written to {out_path}", file=sys.stderr)

if __name__ == "__main__":
    main()
