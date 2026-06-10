"""OPTIONAL richer layer via Google Patents Public Data on BigQuery.

This delivers what the keyless USPC-244 backbone cannot: a true **Aviation vs
Space** split (CPC B64G = cosmonautics vs the rest of B64), **assignee company**
names, and coverage through the most **recent years** — all from the public
`patents-public-data` dataset.

Why this instead of the USPTO API: it only needs a **Google account** (no
ID.me). Setup, once:

    pip install google-cloud-bigquery db-dtypes pyarrow
    gcloud auth application-default login          # logs in with your Google account
    # set a billing-enabled project (BigQuery has a 1 TB/month free tier):
    #   set GOOGLE_CLOUD_PROJECT=your-project-id   (Windows)
    #   export GOOGLE_CLOUD_PROJECT=your-project-id

Then:

    py src/bigquery_aerospace.py                 # 1976..2024
    py src/bigquery_aerospace.py 2000 2024

Outputs (data/processed/):
    aviation_space_national.parquet   year x category x patents
    aviation_space_assignees.parquet  category x assignee x patents (top firms)
and two charts in reports/figures/. These run alongside — they do not replace —
the keyless warehouse.

NOTE: `patents.publications` has US *patent* country but not inventor metro, so
this layer is national/company-level. Metro-level CPC would need the
`patents-public-data.patentsview` location tables (a documented extension).
"""

from __future__ import annotations

import os
import sys

import config as C

# Granted B64 utility patents, split Aviation vs Space (B64G), with first assignee.
SQL = """
WITH aero AS (
  SELECT
    publication_number,
    CAST(SUBSTR(CAST(grant_date AS STRING), 1, 4) AS INT64) AS year,
    EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code, 'B64G')) AS is_space,
    (SELECT a.name FROM UNNEST(assignee_harmonized) a ORDER BY a.name LIMIT 1) AS assignee
  FROM `patents-public-data.patents.publications`
  WHERE country_code = 'US' AND grant_date > 0
    AND EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code, 'B64'))
)
SELECT
  year,
  IF(is_space, 'Space', 'Aviation') AS category,
  COALESCE(NULLIF(assignee, ''), '(unassigned)') AS assignee,
  COUNT(*) AS patents
FROM aero
WHERE year BETWEEN @y0 AND @y1
GROUP BY year, category, assignee
"""


def run(year_from: int = 1976, year_to: int = 2024) -> None:
    try:
        from google.cloud import bigquery
    except ImportError:
        sys.exit("Install the client first:  pip install google-cloud-bigquery db-dtypes")

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    client = bigquery.Client(project=project) if project else bigquery.Client()
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("y0", "INT64", year_from),
        bigquery.ScalarQueryParameter("y1", "INT64", year_to),
    ])
    print(f"Querying Google Patents B64 {year_from}-{year_to} (project={client.project})…")
    df = client.query(SQL, job_config=job_config).to_dataframe()
    print(f"  {len(df):,} (year, category, assignee) rows")

    national = (df.groupby(["year", "category"], as_index=False)["patents"].sum())
    national.to_parquet(C.PROCESSED / "aviation_space_national.parquet", index=False)

    assignees = (df[df["assignee"] != "(unassigned)"]
                 .groupby(["category", "assignee"], as_index=False)["patents"].sum())
    assignees.to_parquet(C.PROCESSED / "aviation_space_assignees.parquet", index=False)
    print("Wrote aviation_space_national.parquet + aviation_space_assignees.parquet")

    _plot(national, assignees)


def _plot(national, assignees) -> None:
    import plotly.express as px

    fig = px.area(national, x="year", y="patents", color="category",
                  color_discrete_map={"Aviation": "#fe9929", "Space": "#1f77b4"},
                  title="US aerospace patents: Aviation vs Space (CPC B64)")
    fig.write_image(str(C.FIGURES / "aviation_vs_space.png"), width=1100, height=600, scale=2)

    top = (assignees.sort_values("patents", ascending=False)
           .groupby("category").head(10))
    fig2 = px.bar(top.sort_values("patents"), x="patents", y="assignee",
                  color="category", orientation="h",
                  color_discrete_map={"Aviation": "#fe9929", "Space": "#1f77b4"},
                  title="Top assignees — Aviation vs Space")
    fig2.write_image(str(C.FIGURES / "top_assignees.png"), width=1100, height=700, scale=2)
    print("Wrote reports/figures/aviation_vs_space.png + top_assignees.png")


if __name__ == "__main__":
    a = sys.argv[1:]
    run(int(a[0]) if a else 1976, int(a[1]) if len(a) > 1 else 2024)
