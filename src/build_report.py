"""Build a single self-contained interactive HTML report.

Bundles the key Plotly figures into one file you can just double-click — no
server, fully interactive, works offline. Output: reports/aerospace_atlas.html

Run:  py src/build_report.py
"""

from __future__ import annotations

import plotly.io as pio

import analysis as A
import config as C
import viz

d = viz.load()
df, allcls = d["df"], d["allcls"]
y0, y1 = int(df.year.min()), int(df.year.max())

# (title, figure, intro paragraph)
sections = [
    ("Animated map (2000–2015)",
     viz.choropleth(d, y1, "patent_count", animate=True),
     "Press ▶ to play the years. Aerospace patenting clusters tightly around a "
     "few manufacturing and defense centers."),
    ("Per-capita intensity (2015)",
     viz.choropleth(d, y1, "per_100k") if d["has_percapita"] else viz.choropleth(d, y1),
     "Patents per 100,000 residents — surfaces small, specialised metros that "
     "raw counts hide."),
    ("Leading metros (2012) — Los Angeles restored to #1",
     viz.top_n_bar(d, 2012, 15),
     "The original assignment dropped Los Angeles to zero via a name-match bug; "
     "joining on the CBSA code restores it to first place (62 patents)."),
    ("National trend", viz.national_trend(d),
     "Annual U.S. aeronautics & astronautics (USPC 244) patent grants."),
    ("Geographic concentration", viz.concentration_trend(d),
     "Top-5 share and the Herfindahl index track how concentrated innovation is."),
    ("Rank mobility", A.rank_bump(df, 10),
     "How the leading metros trade places over 16 years."),
    ("Growth & decline (CAGR)", A.growth_bar(df, y0, y1),
     "Fastest growing and declining established metros."),
    ("Shift-share decomposition", A.shift_share_fig(allcls, y0, y1),
     "Each metro's change split into national-growth, industry-mix, and "
     "competitive-shift components across technology classes."),
]

# Optional Aviation-vs-Space sections (present only after running BigQuery).
import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402

_nat = C.PROCESSED / "aviation_space_national.parquet"
_asg = C.PROCESSED / "aviation_space_assignees.parquet"
if _nat.exists() and _asg.exists():
    nat = pd.read_parquet(_nat)
    asg = pd.read_parquet(_asg)
    av_sp = px.area(nat, x="year", y="patents", color="category",
                    color_discrete_map={"Aviation": "#fe9929", "Space": "#1f77b4"},
                    title="Aviation vs Space (CPC B64), recent years")
    top = asg.sort_values("patents", ascending=False).groupby("category").head(10)
    firms = px.bar(top.sort_values("patents"), x="patents", y="assignee",
                   color="category", orientation="h",
                   color_discrete_map={"Aviation": "#fe9929", "Space": "#1f77b4"},
                   title="Top assignee companies — Aviation vs Space")
    yrs = f"{int(nat.year.min())}–{int(nat.year.max())}"
    sections += [
        (f"Aviation vs. Space ({yrs})", av_sp,
         "From Google Patents (CPC B64): aviation patents dwarf space, but space "
         "is growing. Source: granted US patents, by CPC subclass."),
        ("Top companies", firms,
         "Boeing leads both domains; note Airbus, Honeywell and DJI (drones) in "
         "aviation, and NASA, Lockheed and Northrop in space."),
    ]

# Recent-years metro maps (CPC B64 via PatentsView mirror) — separate method
# and scale from the 2000-2015 backbone, so shown as their own section.
if d.get("recent_split") is not None:
    yr = d["recent_split"]["year"]
    span = f"{int(yr.min())}–{int(yr.max())}"
    sections += [
        (f"Recent metro map, {span} (CPC B64)", viz.choropleth_recent(d),
         "Extends the map to recent years using CPC B64 with inventor "
         "coordinates. Note: a different classification and counting method "
         "than the 2000–2015 series above, so read it on its own scale."),
        (f"Where space is invented, {span}", viz.choropleth_recent(d, "Space"),
         "Space-only (CPC B64G) patenting concentrates in a handful of metros — "
         "Los Angeles, Seattle, Denver, and the DC area."),
    ]

parts = []
for i, (title, fig, blurb) in enumerate(sections):
    html = pio.to_html(fig, full_html=False,
                       include_plotlyjs=(True if i == 0 else False),
                       default_height="640px")
    parts.append(f"<section><h2>{title}</h2><p class='blurb'>{blurb}</p>{html}</section>")

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>US Aerospace Innovation Atlas</title>
<style>
 body{{font-family:'Public Sans',-apple-system,Segoe UI,Roboto,Arial,sans-serif;
   max-width:1200px;margin:0 auto;padding:24px;color:#1b1b1b;}}
 h1{{margin-bottom:.2em}} .sub{{color:#666;margin-top:0}}
 section{{margin:36px 0;padding-top:8px;border-top:1px solid #eee}}
 h2{{color:#7f2704}} .blurb{{color:#555;max-width:780px}}
 footer{{color:#888;font-size:.85em;margin-top:48px;border-top:1px solid #eee;padding-top:12px}}
</style></head><body>
<h1>US Aerospace Innovation Atlas ✈️🛰️</h1>
<p class="sub">Where U.S. aeronautics &amp; astronautics patents (USPC 244) were
invented, by metropolitan area, {y0}–{y1}. Interactive — hover, zoom, and play.</p>
{''.join(parts)}
<footer>Source: USPTO PTMT class-244 reports (via Internet Archive); U.S. Census
metro population estimates; 2018 CBSA cartographic boundaries. Generated by
src/build_report.py.</footer>
</body></html>"""

out = C.ROOT / "reports" / "aerospace_atlas.html"
out.write_text(page, encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size/1024/1024:.1f} MB)")
