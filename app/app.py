"""US Aerospace Innovation Atlas — interactive Plotly Dash dashboard.

Run:  py app/app.py   then open http://127.0.0.1:8050
"""

from __future__ import annotations

import sys
from pathlib import Path

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, dcc, html

# make src/ importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import analysis as A  # noqa: E402
import viz  # noqa: E402

DATA = viz.load()
DF = DATA["df"]
ALLCLS = DATA["allcls"]
YEARS = sorted(DF["year"].unique())
YMIN, YMAX = int(YEARS[0]), int(YEARS[-1])

# metric options (drop per-capita if enrichment not built yet)
METRIC_OPTS = [{"label": lbl, "value": key}
               for key, (lbl, _) in viz.METRICS.items()
               if key != "per_100k" or DATA["has_percapita"]]

# MSA options for the trends multi-select (top 40 by total, plus alpha)
_tot = DF.groupby(["cbsa_geoid", "cbsa_name"])["patent_count"].sum().reset_index()
MSA_OPTS = [{"label": r.cbsa_name, "value": r.cbsa_geoid}
            for r in _tot.nlargest(60, "patent_count").itertuples()]
DEFAULT_MSAS = [o["value"] for o in MSA_OPTS[:5]]

app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY],
           title="US Aerospace Innovation Atlas")
server = app.server  # for deployment


def _year_slider(_id: str) -> dcc.Slider:
    return dcc.Slider(
        id=_id, min=YMIN, max=YMAX, step=1, value=YMAX,
        marks={y: str(y) for y in YEARS if y % 3 == 0 or y in (YMIN, YMAX)},
        tooltip={"placement": "bottom", "always_visible": False},
    )


def _metric_dd(_id: str) -> dcc.Dropdown:
    return dcc.Dropdown(id=_id, options=METRIC_OPTS, value="patent_count",
                        clearable=False)


header = dbc.Container([
    html.H2("US Aerospace Innovation Atlas", className="mt-3 mb-0"),
    html.P("Where U.S. aeronautics & astronautics patents (USPC 244) were "
           "invented, by metropolitan area, 2000–2015.",
           className="text-muted"),
], fluid=True)

map_tab = dbc.Container([
    dbc.Row([
        dbc.Col([html.Label("Metric"), _metric_dd("map-metric")], md=3),
        dbc.Col([html.Label("Year"), _year_slider("map-year")], md=7),
        dbc.Col([html.Label("Animate"),
                 dbc.Switch(id="map-animate", value=False, label="Play years")], md=2),
    ], className="g-3 mt-1"),
    dcc.Loading(dcc.Graph(id="map-graph", style={"height": "60vh"})),
    html.Hr(),
    html.Small("Click any metro on the map for its detail ↓", className="text-muted"),
    dbc.Row([
        dbc.Col(dcc.Loading(dcc.Graph(id="detail-ts")), md=6),
        dbc.Col(dcc.Loading(dcc.Graph(id="detail-mix")), md=6),
    ], className="mt-1"),
], fluid=True)

rank_tab = dbc.Container([
    dbc.Row([
        dbc.Col([html.Label("Metric"), _metric_dd("rank-metric")], md=3),
        dbc.Col([html.Label("Year"), _year_slider("rank-year")], md=6),
        dbc.Col([html.Label("Top N"),
                 dcc.Slider(id="rank-n", min=5, max=25, step=5, value=15,
                            marks={n: str(n) for n in (5, 10, 15, 20, 25)})], md=3),
    ], className="g-3 mt-1"),
    dcc.Loading(dcc.Graph(id="rank-graph", style={"height": "70vh"})),
], fluid=True)

trends_tab = dbc.Container([
    dbc.Row([
        dbc.Col(dcc.Loading(dcc.Graph(id="nat-graph")), md=6),
        dbc.Col(dcc.Loading(dcc.Graph(id="conc-graph")), md=6),
    ], className="mt-2"),
    html.Label("Compare metros"),
    dcc.Dropdown(id="trend-msas", options=MSA_OPTS, value=DEFAULT_MSAS, multi=True),
    dcc.Loading(dcc.Graph(id="trend-graph")),
], fluid=True)

analysis_tab = dbc.Container([
    dbc.Row([
        dbc.Col([html.Label("Bump chart — top N"),
                 dcc.Slider(id="bump-n", min=5, max=15, step=1, value=10,
                            marks={n: str(n) for n in (5, 10, 15)})], md=6),
    ], className="mt-2"),
    dcc.Loading(dcc.Graph(id="bump-graph")),
    html.Hr(),
    dbc.Row([
        dbc.Col(dcc.Loading(dcc.Graph(id="growth-graph")), md=6),
        dbc.Col(dcc.Loading(dcc.Graph(id="shift-graph")), md=6),
    ]),
    html.Small(f"Growth & shift-share computed {YMIN}→{YMAX}. Shift-share "
               "decomposes each metro's change across the available technology "
               "classes into national-growth, industry-mix, and competitive "
               "components.", className="text-muted"),
], fluid=True)

app.layout = html.Div([
    header,
    dbc.Container(dbc.Tabs([
        dbc.Tab(map_tab, label="🗺 Map"),
        dbc.Tab(rank_tab, label="🏆 Rankings"),
        dbc.Tab(trends_tab, label="📈 Trends"),
        dbc.Tab(analysis_tab, label="🔬 Analysis"),
    ]), fluid=True),
    dbc.Container(html.Small(
        "Source: USPTO PTMT class-244 reports (via Internet Archive). "
        "Counts = utility patent grants by inventor metro area.",
        className="text-muted"), fluid=True, className="my-3"),
])


# --------------------------------------------------------------------------
# Callbacks
# --------------------------------------------------------------------------
@app.callback(
    Output("map-graph", "figure"),
    Input("map-metric", "value"), Input("map-year", "value"),
    Input("map-animate", "value"),
)
def _update_map(metric, year, animate):
    return viz.choropleth(DATA, int(year), metric=metric, animate=bool(animate))


@app.callback(
    Output("rank-graph", "figure"),
    Input("rank-metric", "value"), Input("rank-year", "value"), Input("rank-n", "value"),
)
def _update_rank(metric, year, n):
    return viz.top_n_bar(DATA, int(year), n=int(n), metric=metric)


@app.callback(Output("nat-graph", "figure"), Input("trend-msas", "value"))
def _update_nat(_):
    return viz.national_trend(DATA)


@app.callback(Output("conc-graph", "figure"), Input("trend-msas", "value"))
def _update_conc(_):
    return viz.concentration_trend(DATA)


@app.callback(Output("trend-graph", "figure"), Input("trend-msas", "value"))
def _update_trends(geoids):
    return viz.msa_trends(DATA, geoids or DEFAULT_MSAS)


# --- map drill-down -------------------------------------------------------
@app.callback(
    Output("detail-ts", "figure"), Output("detail-mix", "figure"),
    Input("map-graph", "clickData"),
)
def _drilldown(click):
    geoid = DEFAULT_MSAS[0]
    if click and click.get("points"):
        geoid = str(click["points"][0].get("location", geoid))
    ts = A.metro_timeseries(DF, geoid)
    mix = A.metro_class_mix(ALLCLS, geoid) if ALLCLS is not None else ts
    return ts, mix


# --- analysis tab ---------------------------------------------------------
@app.callback(Output("bump-graph", "figure"), Input("bump-n", "value"))
def _update_bump(n):
    return A.rank_bump(DF, int(n))


@app.callback(Output("growth-graph", "figure"), Input("bump-n", "value"))
def _update_growth(_):
    return A.growth_bar(DF, YMIN, YMAX)


@app.callback(Output("shift-graph", "figure"), Input("bump-n", "value"))
def _update_shift(_):
    if ALLCLS is None:
        return A.growth_bar(DF, YMIN, YMAX)
    return A.shift_share_fig(ALLCLS, YMIN, YMAX)


if __name__ == "__main__":
    app.run(debug=False, port=8050)
