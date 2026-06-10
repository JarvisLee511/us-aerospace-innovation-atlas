"""Extend the metro-level map to 2016-2024 (and add an Aviation/Space split)
using the PatentsView BigQuery mirror, which — unlike patents.publications —
carries the **inventor's latitude/longitude**, so patents can be placed in a
metro (CBSA).

Because BigQuery dataset schemas drift, run the schema probe FIRST and paste me
the output so the extraction query can be finalised exactly:

    py src/bigquery_map_extension.py inspect

Then fetch + spatially join to CBSA + write the recent-years warehouse:

    py src/bigquery_map_extension.py 2016 2024

Outputs (data/processed/):
    aerospace_msa_year_recent.parquet        cbsa_geoid x year x patent_count (B64 total)
    aerospace_msa_year_recent_split.parquet  + category (Aviation/Space)
The dashboard/report pick these up automatically (the map slider extends to 2024).
"""

from __future__ import annotations

import sys

import config as C

MIRROR = "patents-public-data.patentsview"

# --- schema (confirmed via `inspect` against patents-public-data.patentsview) -
# NOTE: this mirror appears frozen ~2020, so coverage realistically ends ~2020.
T_PATENT = "patent"          # id (PK), country, date (STRING 'YYYY-MM-DD'), type
T_LINK = "patent_inventor"   # patent_id, inventor_id, location_id
T_LOCATION = "location"      # id (PK), country, latitude/longitude (FLOAT64)
T_CPC = "cpc_current"        # patent_id, subsection_id ('B64'), group_id ('B64G')
COL_CPC_SUBCLASS = "subsection_id"
COL_CPC_GROUP = "group_id"
# ---------------------------------------------------------------------------


def _client():
    try:
        from google.cloud import bigquery
    except ImportError:
        sys.exit("pip install google-cloud-bigquery db-dtypes")
    import os
    proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
    return bigquery.Client(project=proj) if proj else bigquery.Client()


def inspect() -> None:
    """List the mirror's tables and the columns of the ones we need."""
    client = _client()
    ds = MIRROR.split(".", 1)[1]
    proj = MIRROR.split(".", 1)[0]
    q = f"""
      SELECT table_name, column_name, data_type
      FROM `{proj}.{ds}.INFORMATION_SCHEMA.COLUMNS`
      WHERE REGEXP_CONTAINS(table_name, r'(?i)patent|inventor|location|cpc')
      ORDER BY table_name, ordinal_position
    """
    df = client.query(q).to_dataframe()
    if df.empty:
        print(f"No matching tables in {MIRROR}. List ALL tables instead:")
        q2 = (f"SELECT table_name FROM `{proj}.{ds}.INFORMATION_SCHEMA.TABLES` "
              "ORDER BY table_name")
        print(client.query(q2).to_dataframe().to_string(index=False))
        return
    for t, g in df.groupby("table_name"):
        print(f"\n### {t}")
        print(", ".join(f"{r.column_name}:{r.data_type}" for r in g.itertuples()))


def _extract_sql(y0: int, y1: int) -> str:
    return f"""
    WITH aero AS (
      SELECT DISTINCT c.patent_id,
        EXISTS(SELECT 1 FROM `{MIRROR}.{T_CPC}` x
               WHERE x.patent_id = c.patent_id
                 AND STARTS_WITH(x.{COL_CPC_GROUP}, 'B64G')) AS is_space
      FROM `{MIRROR}.{T_CPC}` c
      WHERE c.{COL_CPC_SUBCLASS} = 'B64'
    )
    SELECT
      l.latitude  AS lat,
      l.longitude AS lon,
      CAST(SUBSTR(p.date, 1, 4) AS INT64) AS year,
      IF(a.is_space, 'Space', 'Aviation') AS category,
      pi.patent_id
    FROM aero a
    JOIN `{MIRROR}.{T_PATENT}` p   ON p.id = a.patent_id
    JOIN `{MIRROR}.{T_LINK}` pi    ON pi.patent_id = a.patent_id
    JOIN `{MIRROR}.{T_LOCATION}` l ON l.id = pi.location_id
    WHERE p.country = 'US' AND p.type = 'utility'
      AND l.country = 'US' AND l.latitude IS NOT NULL AND l.longitude IS NOT NULL
      AND CAST(SUBSTR(p.date, 1, 4) AS INT64) BETWEEN {y0} AND {y1}
    """


def fetch_and_build(y0: int, y1: int) -> None:
    import geopandas as gpd
    import pandas as pd

    client = _client()
    print(f"Querying PatentsView mirror for B64 {y0}-{y1}…")
    pts = client.query(_extract_sql(y0, y1)).to_dataframe()
    print(f"  {len(pts):,} inventor-location rows")
    if pts.empty:
        return

    # fractional count: each patent contributes 1, split across its inventor rows
    pts["frac"] = pts.groupby("patent_id")["patent_id"].transform("size").rdiv(1.0)

    # spatial join inventor points -> CBSA polygons
    gdf = gpd.GeoDataFrame(
        pts, geometry=gpd.points_from_xy(pts["lon"], pts["lat"]), crs=C.CRS_WGS84)
    msa = gpd.read_file(C.CBSA_SHAPEFILE)[["GEOID", "NAME", "geometry"]].to_crs(C.CRS_WGS84)
    joined = gpd.sjoin(gdf, msa, how="inner", predicate="within")

    split = (joined.groupby(["GEOID", "NAME", "year", "category"])["frac"]
             .sum().round(3).reset_index()
             .rename(columns={"GEOID": "cbsa_geoid", "NAME": "cbsa_name",
                              "frac": "patent_count"}))
    split.to_parquet(C.PROCESSED / "aerospace_msa_year_recent_split.parquet", index=False)

    total = (split.groupby(["cbsa_geoid", "cbsa_name", "year"])["patent_count"]
             .sum().round(3).reset_index())
    total["class_code"] = "B64"
    total["class_label"] = "Aerospace (CPC B64)"
    total["category"] = "Aeronautics & Astronautics"
    total["level"] = "Metropolitan Statistical Area"
    total.to_parquet(C.PROCESSED / "aerospace_msa_year_recent.parquet", index=False)

    print(f"Wrote recent warehouse: {len(total):,} metro-year rows, "
          f"{total['year'].min()}-{total['year'].max()}, "
          f"{total['cbsa_geoid'].nunique()} metros.")
    print("Re-run  py src/build_report.py  to extend the HTML map to",
          int(total["year"].max()))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "inspect":
        inspect()
    else:
        y0 = int(args[0]) if args else 2016
        y1 = int(args[1]) if len(args) > 1 else 2024
        fetch_and_build(y0, y1)
