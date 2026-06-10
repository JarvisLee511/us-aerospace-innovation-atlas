"""Optional richer layer: pull aerospace patents from the USPTO Open Data
Portal PatentSearch API (CPC subclass B64), including assignee companies and
recent grant years (2016+) that the PTMT backbone does not cover.

This layer is OPTIONAL. The PTMT pipeline (download.py + build_dataset.py)
produces the full keyless dataset on its own. This module only runs when a
USPTO API key is present.

    Get a free key: https://account.uspto.gov/api-manager/  (requires an
    ID.me-verified USPTO.gov account), then put it in .env as USPTO_API_KEY.

NOTE ON STABILITY: USPTO completed the PatentsView -> ODP migration in 2026 and
the ODP search endpoint/auth header can change. The request below follows the
PatentsView-style query language that ODP inherited; if it returns 4xx, verify
the endpoint, header name, and field names against the current Swagger at
https://data.uspto.gov/apis/  and adjust ENDPOINT / _auth_headers / FIELDS.

Run:  py src/api_client.py            # 2016..current
      py src/api_client.py 2016 2020  # custom range
"""

from __future__ import annotations

import json
import sys
import time

import pandas as pd
import requests

import config as C

ENDPOINT = f"{C.ODP_API_BASE}/search"      # ODP PatentSearch (verify vs Swagger)
PAGE_SIZE = 100
FIELDS = [
    "patent_id", "patent_date",
    "assignees.assignee_organization",
    "inventors.inventor_city", "inventors.inventor_state",
    "cpc_current.cpc_subclass_id",
]


def _auth_headers() -> dict:
    # ODP commonly expects the key in the X-API-KEY header.
    return {"X-API-KEY": C.USPTO_API_KEY, "Accept": "application/json",
            "Content-Type": "application/json"}


def _query(year_from: int, year_to: int) -> dict:
    """PatentsView-style query: B64* CPC subclass within a grant-date range."""
    return {
        "_and": [
            {"_gte": {"patent_date": f"{year_from}-01-01"}},
            {"_lte": {"patent_date": f"{year_to}-12-31"}},
            {"_begins": {"cpc_current.cpc_subclass_id": "B64"}},
        ]
    }


def fetch(year_from: int, year_to: int) -> pd.DataFrame:
    """Page through all matching patents. Returns one row per patent."""
    if not C.USPTO_API_KEY:
        print("No USPTO_API_KEY set — skipping API layer. See module docstring.")
        return pd.DataFrame()

    rows, page = [], 1
    while True:
        body = {"q": _query(year_from, year_to), "f": FIELDS,
                "o": {"size": PAGE_SIZE, "page": page}}
        r = requests.post(ENDPOINT, headers=_auth_headers(),
                          data=json.dumps(body), timeout=120)
        if r.status_code != 200:
            print(f"[warn] API returned {r.status_code}: {r.text[:200]}\n"
                  "Verify endpoint/headers/fields against current ODP Swagger.")
            break
        payload = r.json()
        batch = payload.get("patents") or payload.get("results") or []
        if not batch:
            break
        rows.extend(batch)
        print(f"  page {page}: +{len(batch)} (total {len(rows)})")
        if len(batch) < PAGE_SIZE:
            break
        page += 1
        time.sleep(0.5)
    return pd.json_normalize(rows) if rows else pd.DataFrame()


def build(year_from: int = 2016, year_to: int = 2024) -> None:
    df = fetch(year_from, year_to)
    if df.empty:
        return
    out = C.PROCESSED / "aerospace_patents_api.parquet"
    df.to_parquet(out, index=False)
    print(f"Wrote {out.name}: {len(df):,} patents {year_from}-{year_to}")
    print("Next step: map inventor city/state to CBSA and append to the warehouse.")


if __name__ == "__main__":
    a = sys.argv[1:]
    yf = int(a[0]) if len(a) > 0 else 2016
    yt = int(a[1]) if len(a) > 1 else C.YEAR_MAX
    build(yf, yt)
