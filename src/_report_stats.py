import pandas as pd
import viz, analysis as A

d = viz.load(); df = d["df"]; allcls = d["allcls"]
y0, y1 = int(df.year.min()), int(df.year.max())
pd.set_option("display.width", 160)

print("=== WINDOW ===", y0, y1, "| MSAs:", df.cbsa_geoid.nunique(), "| rows:", len(df))

print("\n=== NATIONAL TOTALS BY YEAR ===")
nat = df.groupby("year")["patent_count"].sum()
print(nat.to_string())
print("peak year:", nat.idxmax(), int(nat.max()), "| total all years:", int(nat.sum()))

print("\n=== TOP 10 BY TOTAL (2000-2015) ===")
tot = df.groupby("cbsa_name")["patent_count"].sum().nlargest(10)
print(tot.to_string())
print("top-10 share of all:", round(tot.sum()/nat.sum()*100,1), "%")

print("\n=== 2012 RANK (validation) ===")
print(df[df.year==2012].nlargest(6,"patent_count")[["cbsa_name","patent_count"]].to_string(index=False))

print("\n=== CONCENTRATION: top-5 share & HHI, first vs last ===")
for y in (y0, y1):
    g = df[df.year==y]; t = g.patent_count.sum()
    top5 = g.nlargest(5,"patent_count").patent_count.sum()/t*100
    hhi = ((g.patent_count/t)**2).sum()
    print(f"{y}: top5={top5:.1f}%  HHI={hhi:.3f}")

print("\n=== SEATTLE vs LA by year ===")
sea_la = df[df.cbsa_name.str.contains("Seattle|Los Angeles", regex=True)]
print(sea_la.pivot_table(index="year", columns="cbsa_name", values="patent_count").to_string())

print("\n=== GROWTH (CAGR) top & bottom ===")
g = A.growth_table(df, y0, y1)
print("FASTEST:\n", g.head(6).to_string(index=False))
print("DECLINING:\n", g.tail(6).to_string(index=False))

print("\n=== PER-CAPITA leaders 2015 (pop>250k) ===")
if d["has_percapita"]:
    s = df[(df.year==2015)&(df.population>250000)]
    print(s.nlargest(8,"per_100k")[["cbsa_name","patent_count","per_100k"]].to_string(index=False))

print("\n=== SHIFT-SHARE (top metros) ===")
ss = A.shift_share(allcls, y0, y1, 12)
print(ss[["cbsa_name","NS","IM","CS","actual_change"]].to_string(index=False))
