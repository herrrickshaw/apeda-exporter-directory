# APEDA Exporter's Directory (unofficial search tool)

A small local Flask app that searches APEDA's public exporter directory
(https://apeda.gov.in/exporter-directory) by **state**, **product**,
**exporter type**, **name**, and a free-text **city/district** filter,
with CSV export. Not affiliated with APEDA.

## Why a local server instead of a hosted page

APEDA's directory results come from a live API at
`traceability.apeda.gov.in`. That API only allows requests from
APEDA's own site origin in a browser (CORS), so a page hosted anywhere
else can't call it directly from client-side JS. This app's Flask
backend calls that API server-to-server (no CORS involved) and the
browser only ever talks to `localhost`.

## Run it

```bash
cd apeda-exporter-directory
.venv/bin/python app.py
```

Then open http://127.0.0.1:5055

## Data limits (from APEDA's own API, not this tool's choice)

- **State is required.** The directory has no nationwide search —
  every query must include a state.
- **No official "district" field.** Only city and pincode are
  returned per exporter, so the "City / district" filter here is a
  free-text match against each record's city and address — not an
  administrative district lookup.
- **No exporter-website field.** Only email and mobile number are
  returned. This tool does not fabricate a website column.
- **Product filter is real** (verified against the live API — it
  changes result counts per product), but the quantity/value columns
  shown (`qtyinMT`, `valueinRsCrore`) are each exporter's all-time,
  all-product totals, not specific to the selected product.

## Files

- `app.py` — Flask backend; proxies `ExporterDirectory_state`,
  `ExporterDirectory_product`, and `ExporterDirectory_AllResult` from
  APEDA's `traceability.apeda.gov.in` API.
- `templates/index.html` — single-page UI (vanilla JS, no build step).
