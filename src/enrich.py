"""Per-capita enrichment: attach Census CBSA population so the dashboard can
show patents per 100k residents.

Source: official Census Bureau metro population-estimates file (no API key;
served from www2.census.gov, which is reachable even though api.census.gov may
be firewalled). The file covers 2010-2019; years 2000-2009 are backfilled with
the 2010 estimate (a documented approximation for that early period).

Run:  py src/enrich.py
"""

from __future__ import annotations

import pandas as pd
import requests

import config as C

HEADERS = {"User-Agent": "aerospace-atlas/1.0"}


def _download() -> None:
    if C.CENSUS_POP_CSV.exists():
        return
    print(f"[get ] {C.CENSUS_POP_URL}")
    r = requests.get(C.CENSUS_POP_URL, headers=HEADERS, timeout=120)
    r.raise_for_status()
    C.CENSUS_POP_CSV.write_bytes(r.content)
    print(f"[ok  ] -> {C.CENSUS_POP_CSV.name} ({C.CENSUS_POP_CSV.stat().st_size:,} bytes)")


def build() -> None:
    _download()
    df = pd.read_csv(C.CENSUS_POP_CSV, encoding="latin-1", dtype={"CBSA": str})

    # CBSA-level total rows only (county rows carry STCOU; exclude them)
    df = df[df["STCOU"].isna() & df["LSAD"].str.contains("Statistical Area", na=False)]
    df["cbsa_geoid"] = df["CBSA"].str.zfill(5)

    pop_cols = {f"POPESTIMATE{y}": y for y in range(2010, 2016)}
    long = df.melt(
        id_vars=["cbsa_geoid"], value_vars=list(pop_cols),
        var_name="col", value_name="population",
    )
    long["year"] = long["col"].map(pop_cols)
    long = long[["cbsa_geoid", "year", "population"]]

    # backfill 2000-2009 with the 2010 estimate
    base2010 = long[long["year"] == 2010][["cbsa_geoid", "population"]]
    early = pd.concat([
        base2010.assign(year=y) for y in range(C.YEAR_MIN, 2010)
    ], ignore_index=True)
    pop = pd.concat([early, long], ignore_index=True)
    pop = pop.dropna(subset=["population"])
    pop["population"] = pop["population"].astype(int)

    pop.to_parquet(C.CBSA_POPULATION_PARQUET, index=False)
    print(f"Wrote {C.CBSA_POPULATION_PARQUET.name}: {len(pop):,} rows "
          f"({pop['cbsa_geoid'].nunique()} CBSAs x {pop['year'].nunique()} years, "
          f"{pop['year'].min()}-{pop['year'].max()})")


if __name__ == "__main__":
    build()
