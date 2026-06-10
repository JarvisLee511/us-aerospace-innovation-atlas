"""Build the tidy parquet warehouse from the downloaded PTMT class reports.

Pipeline:
  1. Parse each PTMT class HTML table (wide: one column per year) into long form.
  2. Keep Metropolitan/Micropolitan Statistical Areas; drop state roll-ups.
  3. Map the PTMT "ID Code" to the 2018 CBSA GEOID (fixes the name-match bug
     that dropped Los Angeles in the original assignment).
  4. Validate coverage against the CBSA shapefile and against the original 2012
     assignment file.
  5. Write:
       data/processed/aerospace_msa_year.parquet   (core class 244 backbone)
       data/processed/patents_by_class_msa_year.parquet  (all classes, context)
       data/processed/cbsa.geojson                  (simplified geometry, keyed by GEOID)
       data/processed/cbsa_centroids.parquet        (GEOID -> lon/lat)

Run:  py src/build_dataset.py
"""

from __future__ import annotations

import re
from io import StringIO

import geopandas as gpd
import pandas as pd

import config as C

ID_VARS = ["U.S. Regional Level", "ID Code", "U.S. Regional Title"]


def _norm(name: str) -> str:
    """Normalise an MSA name for matching: upper, drop punctuation/extra spaces."""
    s = str(name).upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return s.strip()


def parse_ptmt(cls: str) -> pd.DataFrame:
    """Parse one PTMT class report HTML into a long DataFrame."""
    html = C.PTMT_HTML(cls).read_text(encoding="utf-8")
    tables = pd.read_html(StringIO(html))
    df = max(tables, key=lambda t: t.size)
    year_cols = [c for c in df.columns if str(c).isdigit() and len(str(c)) == 4]
    long = df.melt(
        id_vars=ID_VARS, value_vars=year_cols,
        var_name="year", value_name="patent_count",
    )
    long = long.rename(columns={
        "U.S. Regional Level": "level",
        "ID Code": "id_code",
        "U.S. Regional Title": "msa_name",
    })
    long["year"] = long["year"].astype(int)
    long["patent_count"] = pd.to_numeric(long["patent_count"], errors="coerce").fillna(0.0)
    long["class_code"] = cls
    long["class_label"] = C.PTMT_CLASSES.get(cls, cls)
    return long


def load_cbsa() -> gpd.GeoDataFrame:
    msa = gpd.read_file(C.CBSA_SHAPEFILE)
    # cb_2018_us_cbsa_500k: GEOID (5-digit), NAME, LSAD, geometry
    msa["GEOID"] = msa["GEOID"].astype(str).str.zfill(5)
    return msa


def build() -> None:
    # 1-2. parse + keep statistical areas with a numeric ID code (drops the
    #      "-- Subtotal --" roll-up rows that carry no CBSA code).
    frames = [parse_ptmt(c) for c in C.PTMT_CLASSES if C.PTMT_HTML(c).exists()]
    allcls = pd.concat(frames, ignore_index=True)
    allcls = allcls[allcls["level"].str.contains("Statistical Area", na=False)].copy()
    allcls = allcls[allcls["id_code"].astype(str).str.fullmatch(r"\d+")].copy()

    # 3. hybrid crosswalk: normalised-name match first (safe), then the
    #    PTMT code rule for areas that were renamed (e.g. Los Angeles).
    msa = load_cbsa()
    valid = set(msa["GEOID"])
    name_by_geoid = msa.set_index("GEOID")["NAME"]
    name2geoid = {_norm(n): g for g, n in zip(msa["GEOID"], msa["NAME"])}

    def resolve(id_code: str, msa_name: str) -> str:
        g = name2geoid.get(_norm(msa_name))          # 1. exact (normalised) name
        if g is None:
            cg = C.ptmt_id_to_geoid(id_code)          # 2. code rule + overrides
            g = cg if cg in valid else cg             # keep code even if no geom
        return g

    allcls["cbsa_geoid"] = [resolve(i, n) for i, n in
                            zip(allcls["id_code"], allcls["msa_name"])]

    # 4. report coverage
    keys = allcls[["cbsa_geoid", "msa_name"]].drop_duplicates()
    matched = keys["cbsa_geoid"].isin(valid)
    print(f"CBSA crosswalk: {matched.sum()}/{len(keys)} distinct areas matched "
          f"the 2018 shapefile ({matched.mean():.1%}).")
    unmatched = keys.loc[~matched].sort_values("msa_name")
    if len(unmatched):
        print("Unmatched (first 15) — kept in data, no geometry:")
        for _, r in unmatched.head(15).iterrows():
            print(f"   {r['cbsa_geoid']}  {r['msa_name']}")

    allcls["cbsa_name"] = allcls["cbsa_geoid"].map(name_by_geoid).fillna(allcls["msa_name"])
    allcls["category"] = "Aeronautics & Astronautics"  # PTMT 244 is combined

    # core backbone (class 244) + all-class context table
    cols = ["cbsa_geoid", "cbsa_name", "year", "patent_count",
            "class_code", "class_label", "category", "level"]
    core = allcls.loc[allcls["class_code"] == C.PTMT_CORE_CLASS, cols].reset_index(drop=True)
    core.to_parquet(C.MSA_YEAR_PARQUET, index=False)
    allcls[cols].to_parquet(C.PROCESSED / "patents_by_class_msa_year.parquet", index=False)
    print(f"\nWrote {C.MSA_YEAR_PARQUET.name}: {len(core):,} rows "
          f"({core['cbsa_geoid'].nunique()} MSAs x {core['year'].nunique()} years)")

    # ship a small sample (top-40 MSAs by total) so app/notebook run without raw data
    top = (core.groupby("cbsa_geoid")["patent_count"].sum()
           .nlargest(40).index)
    core[core["cbsa_geoid"].isin(top)].to_parquet(C.SAMPLE_PARQUET, index=False)

    # geometry: simplify + keep only CBSAs we have data for -> small geojson
    used = set(core["cbsa_geoid"]) & valid
    geo = msa[msa["GEOID"].isin(used)][["GEOID", "NAME", "geometry"]].copy()
    geo["geometry"] = geo["geometry"].simplify(0.01, preserve_topology=True)
    C.PROCESSED.joinpath("cbsa.geojson").write_text(geo.to_json(), encoding="utf-8")
    # centroids (equal-area projection for correctness) -> lon/lat
    cen = geo.to_crs(C.CRS_EQUAL_AREA).geometry.centroid.to_crs(C.CRS_WGS84)
    pd.DataFrame({"cbsa_geoid": geo["GEOID"].values,
                  "lon": cen.x.values, "lat": cen.y.values}
                 ).to_parquet(C.PROCESSED / "cbsa_centroids.parquet", index=False)
    print(f"Wrote cbsa.geojson ({len(geo)} polygons, "
          f"{C.PROCESSED.joinpath('cbsa.geojson').stat().st_size/1024:.0f} KB) + centroids")

    _validate_2012(core)


def _validate_2012(core: pd.DataFrame) -> None:
    """Compare reconstructed 2012 top MSAs against the original assignment file."""
    if not C.PATENT_2012_VALIDATION.exists():
        return
    orig = pd.read_csv(C.PATENT_2012_VALIDATION)
    orig = orig.rename(columns={"U.S. Regional Title": "msa", "2012": "orig_2012"})
    orig = orig[["msa", "orig_2012"]].dropna()
    mine = (core[core["year"] == 2012]
            .sort_values("patent_count", ascending=False)
            .head(8)[["cbsa_name", "patent_count"]])
    print("\nValidation — reconstructed 2012 top 8 vs original file:")
    print(mine.to_string(index=False))
    print("Original file top 5:")
    print(orig.sort_values("orig_2012", ascending=False).head(5).to_string(index=False))


if __name__ == "__main__":
    build()
