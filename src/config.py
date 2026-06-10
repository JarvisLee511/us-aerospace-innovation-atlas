"""Central configuration for the US Aerospace Innovation Atlas pipeline.

Every script reads paths, the CPC aerospace scope, the analysis year range,
and the patent-counting method from here so the whole project stays consistent.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Project root = parent of the src/ directory that holds this file.
ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"
RAW = DATA / "raw"            # downloaded bulk TSVs (large, gitignored)
GEO = DATA / "geo"            # CBSA shapefile
INTERIM = DATA / "interim"    # intermediate filtered tables
PROCESSED = DATA / "processed"  # final parquet warehouse (small, committed)
FIGURES = ROOT / "reports" / "figures"

for _d in (RAW, GEO, INTERIM, PROCESSED, FIGURES):
    _d.mkdir(parents=True, exist_ok=True)

# Key artefacts
CBSA_SHAPEFILE = GEO / "cb_2018_us_cbsa_500k.shp"
PATENT_2012_VALIDATION = RAW / "patent_2012_msa.csv"  # original assignment data

MSA_YEAR_PARQUET = PROCESSED / "aerospace_msa_year.parquet"   # MSA x year x category counts
PATENTS_PARQUET = PROCESSED / "aerospace_patents.parquet"      # patent-level (drill-down)
SAMPLE_PARQUET = PROCESSED / "aerospace_msa_year_sample.parquet"  # fallback shipped sample

# ---------------------------------------------------------------------------
# Aerospace scope: CPC subclass B64 (Aircraft / aviation / cosmonautics)
# Maps closely to the original assignment's USPC class 244.
# ---------------------------------------------------------------------------
# subclass -> (human label, high-level category)
CPC_SUBCLASSES: dict[str, tuple[str, str]] = {
    "B64B": ("Lighter-than-air aircraft", "Aviation"),
    "B64C": ("Aeroplanes; helicopters", "Aviation"),
    "B64D": ("Equipment for aircraft", "Aviation"),
    "B64F": ("Ground or aircraft-carrier installations", "Aviation"),
    "B64U": ("Unmanned aerial vehicles", "Aviation"),
    "B64G": ("Cosmonautics; vehicles/equipment", "Space"),
}
# To extend scope (e.g. propulsion), add subclasses such as "F02K" here.

AEROSPACE_SUBCLASSES = tuple(CPC_SUBCLASSES.keys())
CATEGORY_OF = {sub: cat for sub, (_, cat) in CPC_SUBCLASSES.items()}
CATEGORIES = ("Aviation", "Space")

# ---------------------------------------------------------------------------
# Analysis window (granted-patent year). Bulk snapshot currently ~through 2024.
# ---------------------------------------------------------------------------
YEAR_MIN = 1976
YEAR_MAX = 2024

# ---------------------------------------------------------------------------
# Patent counting method
#   "fractional": each patent contributes 1.0, split equally across the
#                 distinct MSAs of its inventors (no double counting).
#   "whole":      each patent counts 1.0 in every MSA that has an inventor.
# ---------------------------------------------------------------------------
COUNTING_METHOD = os.environ.get("AEROSPACE_COUNTING", "fractional")

# ---------------------------------------------------------------------------
# Coordinate reference systems
# ---------------------------------------------------------------------------
CRS_WGS84 = "EPSG:4326"        # lat/lon
CRS_EQUAL_AREA = "EPSG:5070"   # US Albers equal-area (for centroids / area work)
CRS_WEBMERC = "EPSG:3857"      # web display

# ---------------------------------------------------------------------------
# External services (optional; loaded from .env if present)
# ---------------------------------------------------------------------------
USPTO_API_KEY = os.environ.get("USPTO_API_KEY", "")
CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "")

# ---------------------------------------------------------------------------
# DATA SOURCES
#
# Important: After USPTO completed the PatentsView -> Open Data Portal
# migration (2026-03-20), the old free S3 bulk files now return AccessDenied
# and api.uspto.gov requires an API key. So the project's *keyless backbone*
# uses the USPTO PTMT "Patenting In Technology Classes, Breakout By U.S.
# Metropolitan Area" report for class 244 (Aeronautics & Astronautics),
# which covers CY 2000-2015 by year and is preserved on the Wayback Machine.
# The richer CPC/assignee data (1976-2024) is an OPTIONAL layer that needs a
# free USPTO API key (see api_client.py).
# ---------------------------------------------------------------------------

# --- Keyless backbone: PTMT technology-class-by-MSA reports (via Wayback) ---
# USPC class -> (human label, aerospace?). 244 is the core aerospace class and
# the exact source of the original assignment. The extra classes are pulled,
# when archived, to contextualise aerospace against other technologies.
PTMT_CLASSES: dict[str, str] = {
    "244": "Aeronautics and Astronautics",   # core aerospace (backbone)
    "060": "Power plants (propulsion)",        # context: engines/propulsion
    "701": "Data processing: vehicles/navigation",  # context: avionics/GNC
}
PTMT_CORE_CLASS = "244"
PTMT_YEARS = list(range(2000, 2016))  # CY 2000-2015 as published

# Wayback "id_" raw-capture base. download.py resolves the closest snapshot
# via the availability API, but this captured URL is a known-good fallback.
PTMT_LIVE_URL = (
    "https://www.uspto.gov/web/offices/ac/ido/oeip/taf/cls_cbsa/{cls}cbsa_gd.htm"
)
WAYBACK_AVAILABLE_API = "http://archive.org/wayback/available?url={url}"

PTMT_HTML = lambda cls: RAW / f"ptmt_class_{cls}.html"  # noqa: E731

# --- PTMT "ID Code" -> 2018 CBSA GEOID crosswalk -------------------------
# Empirically, PTMT ID code == "1" + 5-digit CBSA code for most metros, so the
# GEOID is the last 5 digits. A few metros were re-defined between the 2000s
# CBSA vintage and the 2018 shapefile; those go in the override map.
def ptmt_id_to_geoid(id_code: str | int) -> str:
    s = str(id_code).strip()
    geoid = s[-5:] if len(s) >= 5 else s.zfill(5)
    return PTMT_GEOID_OVERRIDES.get(geoid, geoid)

PTMT_GEOID_OVERRIDES: dict[str, str] = {
    # 2000s code -> 2018 CBSA GEOID (definition changes)
    "31100": "31080",  # Los Angeles-Long Beach-Santa Ana -> -Anaheim
    "35620": "35620",  # New York (kept; name changed only)
}

# --- Per-capita enrichment: Census CBSA population estimates ---------------
# Static official file (no API key, reachable without the blocked api.census.gov).
# Covers POPESTIMATE2010-2019; years 2000-2009 are backfilled with the 2010
# estimate (documented caveat).
CENSUS_POP_URL = ("https://www2.census.gov/programs-surveys/popest/datasets/"
                  "2010-2019/metro/totals/cbsa-est2019-alldata.csv")
CENSUS_POP_CSV = RAW / "cbsa-est2019-alldata.csv"
CBSA_POPULATION_PARQUET = PROCESSED / "cbsa_population.parquet"

# --- Optional richer layer: USPTO Open Data Portal API (needs key) ---------
ODP_API_BASE = "https://api.uspto.gov/api/v1/patent"
