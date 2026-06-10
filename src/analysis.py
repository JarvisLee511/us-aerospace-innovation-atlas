"""Deeper analytics on the keyless warehouse: rank mobility, growth, and a
shift-share decomposition. All functions are pure (DataFrame -> Figure/DataFrame)
and are shared by the dashboard and the notebook.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import config as C  # noqa: F401  (kept for parity / future use)

AERO_SCALE = [
    (0.0, "#eeeeee"), (0.15, "#fee391"), (0.4, "#fe9929"),
    (0.7, "#cc4c02"), (1.0, "#7f2704"),
]


# --------------------------------------------------------------------------
# Rank mobility (bump chart)
# --------------------------------------------------------------------------
def rank_bump(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Rank of the top-N metros (by total patents) in each year."""
    totals = df.groupby("cbsa_geoid")["patent_count"].sum().nlargest(top_n).index
    sub = df[df["cbsa_geoid"].isin(totals)].copy()
    sub["rank"] = (sub.groupby("year")["patent_count"]
                   .rank(ascending=False, method="first"))
    fig = px.line(sub.sort_values("year"), x="year", y="rank",
                  color="cbsa_name", markers=True,
                  title=f"Rank mobility — top {top_n} aerospace metros")
    fig.update_yaxes(autorange="reversed", dtick=1, title="Rank (1 = top)")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), legend_title="")
    return fig


# --------------------------------------------------------------------------
# Growth / CAGR
# --------------------------------------------------------------------------
def growth_table(df: pd.DataFrame, start: int, end: int,
                 min_total: int = 30) -> pd.DataFrame:
    """CAGR of patent counts between two years for established metros."""
    piv = (df[df["year"].isin([start, end])]
           .pivot_table(index=["cbsa_geoid", "cbsa_name"], columns="year",
                        values="patent_count", aggfunc="sum")
           .fillna(0))
    piv = piv[df.groupby(["cbsa_geoid", "cbsa_name"])["patent_count"]
              .sum().reindex(piv.index) >= min_total]
    yrs = end - start
    piv["CAGR_%"] = ((piv[end] + 1) / (piv[start] + 1)) ** (1 / yrs) * 100 - 100
    out = (piv.reset_index()
           .rename(columns={start: f"y{start}", end: f"y{end}"})
           .sort_values("CAGR_%", ascending=False))
    out["CAGR_%"] = out["CAGR_%"].round(1)
    return out[["cbsa_name", f"y{start}", f"y{end}", "CAGR_%"]]


def growth_bar(df: pd.DataFrame, start: int, end: int, n: int = 12) -> go.Figure:
    g = growth_table(df, start, end)
    top = pd.concat([g.head(n), g.tail(n)]).drop_duplicates()
    top = top.sort_values("CAGR_%")
    fig = px.bar(top, x="CAGR_%", y="cbsa_name", orientation="h",
                 color="CAGR_%", color_continuous_scale="RdYlGn",
                 title=f"Fastest growing & declining metros, {start}–{end} (CAGR)")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10),
                      yaxis_title="", coloraxis_showscale=False)
    return fig


# --------------------------------------------------------------------------
# Shift-share decomposition (region x industry/class)
# --------------------------------------------------------------------------
def shift_share(allcls: pd.DataFrame, start: int, end: int,
                top_n: int = 12) -> pd.DataFrame:
    """Decompose each metro's change in total patents (across the available
    technology classes) into National Share, Industry Mix, and Competitive
    Shift components — the classic regional shift-share model."""
    a = allcls[allcls["year"].isin([start, end])]
    wide = (a.pivot_table(index=["cbsa_geoid", "cbsa_name", "class_label"],
                          columns="year", values="patent_count", aggfunc="sum")
            .fillna(0).reset_index())
    s, e = start, end

    nat = wide[[s, e]].sum()
    g = nat[e] / nat[s] - 1                       # overall national growth
    ind = wide.groupby("class_label")[[s, e]].sum()
    g_i = (ind[e] / ind[s] - 1).to_dict()         # per-class national growth

    wide["NS"] = wide[s] * g
    wide["IM"] = wide.apply(lambda r: r[s] * (g_i[r["class_label"]] - g), axis=1)
    wide["CS"] = wide.apply(
        lambda r: r[s] * ((r[e] / r[s] - 1 if r[s] else 0) - g_i[r["class_label"]]),
        axis=1)

    reg = (wide.groupby(["cbsa_geoid", "cbsa_name"])[["NS", "IM", "CS", s, e]]
           .sum().reset_index())
    reg["actual_change"] = reg[e] - reg[s]
    reg = reg.nlargest(top_n, e)
    for c in ("NS", "IM", "CS", "actual_change"):
        reg[c] = reg[c].round(1)
    return reg.rename(columns={s: f"y{start}", e: f"y{end}"})


def shift_share_fig(allcls: pd.DataFrame, start: int, end: int,
                    top_n: int = 12) -> go.Figure:
    reg = shift_share(allcls, start, end, top_n)
    fig = go.Figure()
    for comp, color, name in [
        ("NS", "#9ecae1", "National growth"),
        ("IM", "#fdae6b", "Industry mix"),
        ("CS", "#a1d99b", "Competitive shift"),
    ]:
        fig.add_bar(y=reg["cbsa_name"], x=reg[comp], name=name,
                    orientation="h", marker_color=color)
    fig.add_trace(go.Scatter(
        y=reg["cbsa_name"], x=reg["actual_change"], mode="markers",
        name="Actual change", marker=dict(color="black", symbol="diamond", size=8)))
    fig.update_layout(
        barmode="relative",
        title=f"Shift-share: sources of patent growth by metro, {start}–{end}",
        margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=-0.12),
        xaxis_title="Patents (decomposed change)")
    return fig


# --------------------------------------------------------------------------
# Per-metro detail (for app drill-down)
# --------------------------------------------------------------------------
def metro_timeseries(df: pd.DataFrame, geoid: str) -> go.Figure:
    sub = df[df["cbsa_geoid"] == geoid].sort_values("year")
    name = sub["cbsa_name"].iloc[0] if len(sub) else geoid
    fig = px.area(sub, x="year", y="patent_count", markers=True,
                  title=f"{name} — aerospace patents per year")
    fig.update_traces(line_color="#cc4c02", fillcolor="rgba(204,76,2,0.2)")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), yaxis_title="Patents")
    return fig


def metro_class_mix(allcls: pd.DataFrame, geoid: str) -> go.Figure:
    sub = allcls[allcls["cbsa_geoid"] == geoid].sort_values("year")
    name = sub["cbsa_name"].iloc[0] if len(sub) else geoid
    fig = px.area(sub, x="year", y="patent_count", color="class_label",
                  title=f"{name} — technology composition")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10),
                      legend_title="", yaxis_title="Patents")
    return fig
