"""
APEDA Exporter's Directory — local search tool.

Proxies https://apeda.gov.in/exporter-directory's live backend
(traceability.apeda.gov.in) server-side, so the browser never hits
CORS restrictions the public site's own JS relies on being same-origin.

Run:
    .venv/bin/python app.py
Then open http://127.0.0.1:5055
"""
from flask import Flask, jsonify, render_template, request
import requests

app = Flask(__name__)

API_BASE = "https://traceability.apeda.gov.in/apedamobile/api/apedaWebsite"
TIMEOUT = 30

EXPORTER_TYPES = [
    {"code": "ALL", "name": "All"},
    {"code": "2", "name": "Manufacturer"},
    {"code": "1", "name": "Merchant"},
    {"code": "4", "name": "Manufacturer cum Merchant"},
]

_cache = {"states": None, "products": None}


def _fetch_states():
    r = requests.post(f"{API_BASE}/ExporterDirectory_state", json={"qType": "7"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json().get("table", [])


def _fetch_products():
    r = requests.post(f"{API_BASE}/ExporterDirectory_product", json={"qType": "1"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json().get("table", [])


def get_states():
    if _cache["states"] is None:
        try:
            _cache["states"] = _fetch_states()
        except requests.RequestException:
            _cache["states"] = []
    return _cache["states"]


def get_products():
    if _cache["products"] is None:
        try:
            _cache["products"] = _fetch_products()
        except requests.RequestException:
            _cache["products"] = []
    return _cache["products"]


@app.route("/")
def index():
    return render_template(
        "index.html",
        states=get_states(),
        products=get_products(),
        exporter_types=EXPORTER_TYPES,
    )


@app.route("/api/search")
def api_search():
    state = (request.args.get("state") or "").strip()
    product = (request.args.get("product") or "0000").strip()
    exp_type = (request.args.get("type") or "ALL").strip()
    name = (request.args.get("name") or "").strip()
    district = (request.args.get("district") or "").strip().lower()

    if not state:
        return jsonify({"error": "APEDA's directory requires a state to be selected — it has no nationwide search."}), 400

    payload = {
        "qType": "13",
        "expName": name,
        "expState": state,
        "expType": exp_type,
        "expProduct": product,
    }

    try:
        r = requests.post(f"{API_BASE}/ExporterDirectory_AllResult", json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        return jsonify({"error": f"APEDA's live directory could not be reached: {exc}"}), 502

    rows = data.get("table", [])

    if district:
        rows = [
            row for row in rows
            if district in (row.get("city") or "").lower()
            or district in (row.get("address") or "").lower()
        ]

    return jsonify({"count": len(rows), "results": rows})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=True)
