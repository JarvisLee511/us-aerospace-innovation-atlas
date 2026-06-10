"""Shared data-access and Plotly figure builders.

Both the analysis notebook and the Dash app import from here so the charts
stay consistent. All functions are pure: give them a DataFrame, get a Figure.
"""

from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import config as C

# Sequential colour scale (light grey -> dark aerospace orange/red)
AERO_SCALE = [
    (0.0, "#eeeeee"), (0.15, "#fee391"), (0.4, "#fe9929"),
    (0.7, "#cc4c02"), (1.0, "#7f2704"),
]

METRICS = {
    "patent_count": ("Patents (count)", "Patents"),
    "national_share": ("Share of US total (%)", "% of US"),
    "per_100k": ("Patents per 100k residents", "per 100k"),
}


# --------------------------------------------------------------------------
# Data access
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def load() -> dict:
    """Load the processed warehouse once and cache it."""
    df = pd.read_parquet(C.MSA_YEAR_PARQUET)

    # recent-years extension is kept SEPARATE (not concatenated): 2000-2015 is
    # USPC-244 while the extension is CPC-B64 on a different scale/method, so
    # mixing them in one series would create a misleading seam. The split table
    # (Aviation vs Space) is exposed for dedicated recent-years visuals.
    split_path = C.PROCESSED / "aerospace_msa_year_recent_split.parquet"
    recent_split = pd.read_parquet(split_path) if split_path.exists() else None
    geojson = json.loads(C.PROCESSED.joinpath("cbsa.geojson").read_text(encoding="utf-8"))
    cen = pd.read_parquet(C.PROCESSED / "cbsa_centroids.parquet")

    # optional per-capita layer (written by enrich.py)
    pop_path = C.PROCESSED / "cbsa_population.parquet"
    pop = pd.read_parquet(pop_path) if pop_path.exists() else None

    # multi-class table (244 + context classes) for composition / shift-share
    allcls_path = C.PROCESSED / "patents_by_class_msa_year.parquet"
    allcls = pd.read_parquet(allcls_path) if allcls_path.exists() else None

    df = add_metrics(df, pop)
    return {"df": df, "geojson": geojson, "centroids": cen,
            "allcls": allcls, "has_percapita": pop is not None,
            "recent_split": recent_split}


def add_metrics(df: pd.DataFrame, pop: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add derived metrics: national share (per year) and per-capita."""
    df = df.copy()
    yearly_total = df.groupby("year")["patent_count"].transform("sum")
    df["national_share"] = (df["patent_count"] / yearly_total * 100).round(3)
    if pop is not None:
        keys = ["cbsa_geoid", "year"] if "year" in pop.columns else ["cbsa_geoid"]
        df = df.merge(pop[keys + ["population"]], on=keys, how="left")
        df["per_100k"] = (df["patent_count"] / df["population"] * 1e5).round(3)
    return df


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------
def choropleth(data: dict, year: int, metric: str = "patent_count",
               animate: bool = False) -> go.Figure:
    df, geojson = data["df"], data["geojson"]
    label, cbar = METRICS.get(metric, (metric, metric))
    sub = df if animate else df[df["year"] == year]
    sub = sub[sub[metric].notna()] if metric in sub else sub

    fig = px.choropleth(
        sub.sort_values("year"),
        geojson=geojson, locations="cbsa_geoid", featureidkey="properties.GEOID",
        color=metric, color_continuous_scale=AERO_SCALE,
        scope="usa", hover_name="cbsa_name",
        hover_data={"cbsa_geoid": False, metric: ":,.2f"},
        animation_frame="year" if animate else None,
        labels={metric: cbar},
        title=f"US Aerospace Patenting by Metro Area — {label}"
              + ("" if animate else f" ({year})"),
    )
    fig.update_geos(visible=False, lakecolor="white")
    fig.update_layout(margin=dict(l=0, r=0, t=50, b=0),
                      coloraxis_colorbar_title=cbar)
    return fig


def choropleth_recent(data: dict, category: str | None = None,
                      animate: bool = True) -> go.Figure:
    """Metro map from the recent CPC-B64 extension (2016-2021). Optionally
    filter to a category ('Aviation' or 'Space'). Separate scale/method from
    the 2000-2015 USPC-244 backbone."""
    rs, geojson = data.get("recent_split"), data["geojson"]
    if rs is None:
        return go.Figure()
    sub = rs if category is None else rs[rs["category"] == category]
    sub = (sub.groupby(["cbsa_geoid", "cbsa_name", "year"], as_index=False)["patent_count"]
           .sum())
    label = category or "Aviation + Space"
    fig = px.choropleth(
        sub.sort_values("year"), geojson=geojson, locations="cbsa_geoid",
        featureidkey="properties.GEOID", color="patent_count",
        color_continuous_scale=AERO_SCALE, scope="usa", hover_name="cbsa_name",
        animation_frame="year" if animate else None,
        title=f"Aerospace patenting by metro — {label} (CPC B64, "
              f"{int(sub.year.min())}–{int(sub.year.max())})")
    fig.update_geos(visible=False, lakecolor="white")
    fig.update_layout(margin=dict(l=0, r=0, t=50, b=0))
    return fig


def top_n_bar(data: dict, year: int, n: int = 15,
              metric: str = "patent_count") -> go.Figure:
    df = data["df"]
    label, _ = METRICS.get(metric, (metric, metric))
    sub = (df[df["year"] == year].nlargest(n, metric)
           .sort_values(metric))
    fig = px.bar(sub, x=metric, y="cbsa_name", orientation="h",
                 color=metric, color_continuous_scale=AERO_SCALE,
                 title=f"Top {n} metros — {label} ({year})")
    fig.update_layout(margin=dict(l=0, r=0, t=50, b=0),
                      yaxis_title="", coloraxis_showscale=False)
    return fig


def national_trend(data: dict) -> go.Figure:
    df = data["df"]
    nat = df.groupby("year")["patent_count"].sum().reset_index()
    fig = px.area(nat, x="year", y="patent_count",
                  title="US aeronautics & astronautics patents per year",
                  markers=True)
    fig.update_traces(line_color="#cc4c02", fillcolor="rgba(204,76,2,0.2)")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), yaxis_title="Patents")
    return fig


def concentration_trend(data: dict) -> go.Figure:
    """Herfindahl index + top-5 share over time (geographic concentration)."""
    df = data["df"]
    rows = []
    for year, g in df.groupby("year"):
        total = g["patent_count"].sum()
        if total <= 0:
            continue
        shares = g["patent_count"] / total
        hhi = float((shares ** 2).sum())
        top5 = float(g.nlargest(5, "patent_count")["patent_count"].sum() / total * 100)
        rows.append({"year": year, "HHI": hhi, "Top-5 share (%)": top5})
    c = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=c["year"], y=c["Top-5 share (%)"], name="Top-5 share (%)",
                             yaxis="y1", line=dict(color="#cc4c02", width=3)))
    fig.add_trace(go.Scatter(x=c["year"], y=c["HHI"], name="HHI (0-1)",
                             yaxis="y2", line=dict(color="#1f77b4", width=2, dash="dot")))
    fig.update_layout(
        title="Geographic concentration of aerospace innovation",
        yaxis=dict(title="Top-5 share (%)", range=[0, 100]),
        yaxis2=dict(title="HHI", overlaying="y", side="right", range=[0, 1]),
        margin=dict(l=10, r=10, t=50, b=10), legend=dict(x=0.01, y=0.99),
    )
    return fig


def msa_trends(data: dict, geoids: list[str], metric: str = "patent_count") -> go.Figure:
    df = data["df"]
    label, _ = METRICS.get(metric, (metric, metric))
    sub = df[df["cbsa_geoid"].isin(geoids)]
    fig = px.line(sub, x="year", y=metric, color="cbsa_name", markers=True,
                  title=f"Selected metros over time — {label}")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10),
                      legend_title="", yaxis_title=label)
    return fig
