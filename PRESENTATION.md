# 如何介紹這個專案 (Presentation Guide)

> 你在美國面試多半用英文，所以下面「要說出口的話」用英文寫好可直接用；說明用中文。

---

## 1. 一句話電梯簡報 (10–15 秒)

> **"I turned a one-off class assignment — a static map of 2012 aerospace patents — into a full data product: a reproducible pipeline, a 16-year geographic analysis, and an interactive dashboard. Along the way I found and fixed a data bug that had erased the #1 metro from the original map."**

中文重點：**從一張靜態圖 → 完整資料產品；而且抓到一個讓全美第一名消失的 bug。** 「發現並修正 bug」這句話一定要講，這是最強的鉤子。

## 2. 一分鐘版本 (面試「介紹一個你的專案」)

> "The project maps where in the U.S. aerospace patents are invented, by metro area.
>
> The original version only covered one year and joined patents to map regions **by name**. I noticed Los Angeles — which should be #1 — was showing **zero**. The cause: the 2018 boundary file had renamed the LA metro, so the name match silently failed. I re-joined on the stable **CBSA code**, which fixed it and validated exactly against the source.
>
> Then I expanded it: 16 years of data from the USPTO archive, per-capita normalization with Census population, and concentration and growth analytics. I built a reproducible Python pipeline that outputs a Parquet warehouse, a clean notebook, and an interactive **Plotly Dash** dashboard. The headline finding is that **Seattle overtook Los Angeles** as the top aerospace-inventing metro around 2013, and that the field is highly concentrated — the top 5 metros hold ~40% of all patents."

## 3. Demo 腳本 (打開 dashboard 或 HTML 時，2–3 分鐘)

照這個順序講，每個畫面一句話：

1. **Map（動畫）** — "Press play. Watch the orange intensify in the Pacific Northwest — that's Seattle rising." 按播放，講群聚。
2. **點一個 metro 下鑽** — "Click Seattle: here's its trajectory and what technologies it specializes in." 展示互動。
3. **Rankings** — "Switch the metric to *per-capita* — now small specialist towns like Tucson and Huntsville surface." 講絕對 vs 人均。
4. **Trends / Concentration** — "Top-5 share and the Herfindahl index show the field is concentrated but slowly diffusing." 講集中度。
5. **Analysis（shift-share）** — "This decomposes each metro's growth into national, industry-mix, and competitive components — LA's decline is locally driven, not just the national trend." 展示分析深度。
6. **(若有跑 BigQuery)** — "And from Google Patents, the aviation-vs-space split and top companies — Boeing leads both."

## 4. 為什麼這個專案「有料」(你的賣點清單)

面試官在找這些訊號，主動把它們講出來：

- **資料嚴謹度** — "I validated my reconstruction against the original source numbers before trusting it." (發現 bug + 驗證)
- **端到端能力** — 不只畫圖：ingestion → cleaning → spatial join → modeling → product。
- **Resourcefulness** — "When the free bulk data was taken offline mid-project, I sourced an equivalent dataset from the Internet Archive; when the API required ID.me, I switched to Google's BigQuery public data." (遇阻找路)
- **方法選擇有理由** — fractional counting、per-capita、HHI、shift-share，每個都能解釋為什麼。
- **產品思維** — 做了 live dashboard + 一鍵 HTML + README + report，讓別人零安裝就能看。

## 5. 看對象調整講法

| 對象 | 強調 |
|---|---|
| **HR / Recruiter（非技術）** | 故事：「發現 bug、修正、把作業變成真產品」；影響：「能回答『美國航太創新在哪、怎麼變化』」。少講工具名。 |
| **Data Analyst / DS 面試官** | 方法與嚴謹度：spatial join、counting method、normalization、concentration metrics、validation、limitations。 |
| **航太 / 領域人士** | 發現：Seattle 超車 LA、群聚、aviation vs space、Boeing 主導；以及資料的侷限。 |

## 6. 一定要主動講的「限制」(展現成熟度)

> "It counts grants not applications; the 2000–2015 class combines aviation and space; and patent counts proxy *invention activity*, not commercial success or R&D spend."

主動講限制，面試官會覺得你誠實、懂資料。

---

*配套：完整發現見 [REPORT.md](REPORT.md)；常見面試問答見 [INTERVIEW_QA.md](INTERVIEW_QA.md)。*
