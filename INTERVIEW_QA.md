# 面試問答 (Interview Q&A)

> 在美國面試多為英文，所以「要說出口的答案」用英文寫好可直接用；中文是給你理解/準備的註解。
> 對應專案：US Aerospace Innovation Atlas。

---

## A. 行為面 / HR (Behavioral)

**Q1. Walk me through this project.**
> "It maps where U.S. aerospace patents are invented, by metro area. It started as a one-year class assignment; I found a data bug that erased the top metro, fixed it, then expanded it into a 16-year analysis with a reproducible pipeline and an interactive dashboard. The key finding is that Seattle overtook Los Angeles as the top aerospace-inventing metro, and the field is highly concentrated — five metros hold about 40% of all patents."

**Q2. Why did you choose this project / what motivated you?**
> "I wanted to take something I'd only done at a surface level and make it portfolio-grade — to practice the full data lifecycle, not just visualization. The aerospace patent angle also let me work with real geospatial and government data, which is messy in instructive ways."

**Q3. What was the biggest challenge?**
> "Two. First, a silent data-quality bug: Los Angeles showed zero patents because the metro had been renamed between data vintages, so a name-based join failed. Second, mid-project the free bulk data source was taken offline during a USPTO migration. I had to re-architect the data sourcing — I found an equivalent dataset on the Internet Archive and added a Google BigQuery layer — without losing the deliverable."

**Q4. What did you learn?**
> "That the join key matters more than the join. A name join *looked* fine and silently dropped the most important record. Now I validate every reconstruction against a known ground truth before trusting it. I also learned to design pipelines that degrade gracefully when an external source disappears."

**Q5. If you had more time, what would you improve?**
> "Deploy it to a public URL so it's a clickable link, extend the map to the most recent years with the metro-level CPC data, and add a statistical model — for example, what predicts a metro's aerospace patenting: population, university presence, defense spending."

**Q6. Did you work alone or on a team? / How would this work on a team?**
> "Solo, but I structured it like team work would need: a config module as the single source of truth, pure functions shared between the app and notebook, a README, and a reproducible pipeline so anyone could rebuild the data from scratch."

---

## B. 資料分析 / 技術面 (Data Analyst / Technical)

**Q7. Where did the data come from, and is it reliable?**
> "USPTO's Patent Technology Monitoring reports for the aeronautics & astronautics class, by metro, 2000–2015 — preserved on the Internet Archive after the live pages were retired. I validated it by reproducing the original 2012 numbers exactly. For recent years and an aviation-vs-space split I used Google Patents public data on BigQuery."

**Q8. Tell me about the bug you found and how you fixed it.**
> "The original joined patents to map polygons by metro *name*. The 2018 boundary file renamed 'Los Angeles–Long Beach–Santa Ana' to '…–Anaheim', so the join missed and LA — the #1 metro at 62 patents — became zero. I switched to joining on the **CBSA code**, which is stable across renames. I used a hybrid resolver: match on normalized name first, fall back to the code, with a small override table for metros that were redefined between vintages. Coverage went to ~88% of distinct areas, and all the high-volume metros matched."

**Q9. Your patent counts — how exactly are they counted? Could a patent be double-counted?**
> "I use **fractional counting**: each patent contributes 1.0, split equally across the distinct metros of its inventors. So a patent with inventors in two metros adds 0.5 to each — no double counting, and national totals stay exact. I made it configurable; whole-counting (1.0 per metro) is the alternative, which is what some official reports use."

**Q10. Why per-capita, and how did you compute it?**
> "Raw counts just track metro size — big metros win automatically. Per-capita (patents per 100k residents) reveals *specialization*: Tucson and Huntsville punch far above their size. I joined Census metro population estimates by CBSA code and year. Caveat: pre-2010 uses the 2010 population as the denominator."

**Q11. What is the shift-share analysis doing?**
> "It decomposes each metro's change in patents into three parts: national growth (the rising tide), industry mix (whether its technology classes were nationally hot), and competitive shift (local over/under-performance). It separates 'LA declined because the whole field shifted' from 'LA declined specifically' — and the data shows LA's drop is a negative competitive shift, i.e. locally driven."

**Q12. How did you measure concentration?**
> "Two ways: the top-5 metros' share of national patents, and the Herfindahl–Hirschman Index — the sum of squared shares. Both showed the field is concentrated but slowly diffusing: HHI fell from 0.086 to 0.058 over 2000–2015."

**Q13. The geospatial part — how does a patent become a point on the map?**
> "For the recent-years extension, each patent's inventor has a latitude/longitude. I build point geometries and do a spatial join — `point within polygon` — against the CBSA boundary shapefile to assign each inventor to a metro, then aggregate. I project to an equal-area CRS for any area/centroid math and use a spatial index so the join scales."

**Q14. How did you validate your results?**
> "I reconstructed 2012 and compared the top metros to the original source file — they matched exactly (LA 62, Seattle 45, Tucson 35, Dallas 18, Hartford 14) once the join was fixed. I also asserted row counts, year ranges, and no nulls in key columns in the build step."

**Q15. What are the limitations? (主動講)**
> "It counts patent *grants*, not applications, so there's a grant-lag; it attributes by inventor location, not company HQ; the 2000–2015 class combines aviation and space; about 12% of small micropolitan areas predate the 2018 boundaries and aren't mapped; and patents proxy invention activity, not commercial value."

---

## C. 工具 / 工程 (Tooling & Engineering)

**Q16. Why Plotly Dash? Why not Tableau / Power BI?**
> "I wanted it reproducible and version-controlled in code, free to host, and fully customizable — animated choropleths, click-to-drill-down, custom metrics. Dash gave me that in Python, and I also export a single self-contained HTML so non-technical viewers need zero setup."

**Q17. Why Parquet instead of CSV?**
> "Columnar, compressed, and typed — the whole warehouse is under a megabyte and loads instantly, versus parsing CSV. It also preserves dtypes, so the app and notebook don't re-infer types."

**Q18. How is the project structured / how would someone reproduce it?**
> "A `config.py` holds all paths, the technology scope, and the crosswalk — single source of truth. `download → build_dataset → enrich` is the pipeline; `viz.py` and `analysis.py` are pure functions shared by the Dash app and the notebook. `requirements.txt` plus a README make it `pip install` and run."

**Q19. The original notebook was 297 MB. Why, and how did you fix it?**
> "Each Plotly figure had the full map geometry embedded in its saved output, repeated across cells. I separated the geometry into one simplified GeoJSON, kept outputs lean, and the rebuilt notebook is about 1.5 MB."

**Q20. Write the SQL to get aerospace patents by year split into aviation vs space.** *(BigQuery)*
> ```sql
> SELECT
>   CAST(SUBSTR(CAST(grant_date AS STRING),1,4) AS INT64) AS year,
>   IF(EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code,'B64G')),
>      'Space','Aviation') AS category,
>   COUNT(*) AS patents
> FROM `patents-public-data.patents.publications`
> WHERE country_code='US' AND grant_date>0
>   AND EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code,'B64'))
> GROUP BY year, category ORDER BY year;
> ```
> 重點能講：CPC `B64`=航太、`B64G`=太空；`cpc` 是 nested/repeated 欄位，所以要 `UNNEST`。

**Q21. How would you scale this to all patents, not just aerospace?**
> "Move aggregation into BigQuery instead of pulling rows locally — group by metro, year, and CPC class server-side. Cache the aggregates in Parquet partitioned by year. For the app, pre-compute the metrics so callbacks just slice a small table."

---

## D. 釣魚題 / 心態 (Curveballs)

**Q22. Do more patents mean more innovation?**
> "Not exactly — patents measure *patenting activity*, which is shaped by industry norms, legal strategy, and funding, not just invention. It's a useful proxy with known biases, which is why I frame findings as 'patenting concentration', not 'innovation' outright."

**Q23. Someone says your map looks wrong / a metro is missing. How do you respond?**
> "That's exactly the failure mode I hit with LA — so first I'd check the join coverage and the crosswalk for that metro, then trace one record end-to-end. I keep an unmatched-areas log in the build step for precisely this."

**Q24. What's the one thing you're most proud of here?**
> "Catching a bug that made the headline result wrong, and being disciplined enough to validate against ground truth instead of trusting a plot that looked plausible."

---

## 30 秒總收尾 (記起來)

> "End to end: I ingested and cleaned government patent data, fixed a join bug that had erased the top result, modeled geographic concentration and growth, and shipped it as an interactive dashboard and a written report — all reproducible from a single command."
