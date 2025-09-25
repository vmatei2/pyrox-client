import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pyrox

client = pyrox.PyroxClient()


for i in range(1000):
    print(f"getting {i}")
    client.get_race(season=6, location="london", use_cache=False)

####   DATA Prep
run_cols = [f"run{i}_time" for i in range(1, 9)]
station_cols = [
    "skiErg_time","sledPush_time","sledPull_time","burpeeBroadJump_time",
    "rowErg_time","farmersCarry_time","sandbagLunges_time","wallBalls_time",
]
station_labels = ["SkiErg","Sled Push","Sled Pull","BBJ","Row","Farmers","Lunges","Wall Balls"]


def pick_athlete_row(df: pd.DataFrame, athlete: str) -> pd.Series:
    m = df["name"].astype(str).str.contains(athlete, case=False, na=False)
    sub = df[m]
    if sub.empty:
        raise ValueError(f"Athlete '{athlete}' not found")
    return sub.iloc[0]

def male_open(df: pd.DataFrame) -> pd.DataFrame:
    g = df["gender"].astype(str).str.lower().str.startswith("m")
    d = df["division"].astype(str).str.lower().str.contains("open")
    return df[g & d]


rot = client.get_race(season=6, location="rotterdam", use_cache=False)
bcn = client.get_race(season=7, location="barcelona", use_cache=False)
athlete = "matei, vlad"
me_rot = pick_athlete_row(rot, athlete)
me_bcn = pick_athlete_row(bcn, athlete)

# per-race Male Open averages
rot_mo = male_open(rot)
bcn_mo = male_open(bcn)
rot_run_avg = rot_mo[run_cols].mean()
bcn_run_avg = bcn_mo[run_cols].mean()
rot_sta_avg = rot_mo[station_cols].mean()
bcn_sta_avg = bcn_mo[station_cols].mean()

# --- build comparison frames (YOUR data) ---
runs_cmp = pd.DataFrame({
    "segment": range(1, 9),
    "Rotterdam (athlete)": [me_rot[c] for c in run_cols],
    "Barcelona (athlete)": [me_bcn[c] for c in run_cols],
}).set_index("segment")

stations_cmp = pd.DataFrame({
    "station": station_labels,
    "Rotterdam (athlete)": [me_rot.get(c, np.nan) for c in station_cols],
    "Barcelona (athlete)": [me_bcn.get(c, np.nan) for c in station_cols],
}).set_index("station")


sns.set_style("darkgrid")
plt.figure()
plt.plot(runs_cmp.index, runs_cmp["Rotterdam (athlete)"], marker="o", label="Rotterdam (athlete)")
plt.plot(runs_cmp.index, runs_cmp["Barcelona (athlete)"], marker="o", label="Barcelona (athlete)")
plt.plot(runs_cmp.index, rot_run_avg.values, marker="o", linestyle="--", label="Rotterdam Avg (Male Open)")
plt.plot(runs_cmp.index, bcn_run_avg.values, marker="o", linestyle="--", label="Barcelona Avg (Male Open)")
plt.xticks(runs_cmp.index)
plt.xlabel("Run #")
plt.ylabel("Minutes")
plt.title("Run Splits — You vs Race Averages")
plt.legend()
plt.tight_layout()
plt.show()


plt.figure()
plt.plot(stations_cmp.index, stations_cmp["Rotterdam (athlete)"], marker="o", label="Rotterdam (athlete)")
plt.plot(stations_cmp.index, stations_cmp["Barcelona (athlete)"], marker="o", label="Barcelona (athlete)")
plt.plot(stations_cmp.index, rot_sta_avg.values, marker="o", linestyle="--", label="Rotterdam Avg (Male Open)")
plt.plot(stations_cmp.index, bcn_sta_avg.values, marker="o", linestyle="--", label="Barcelona Avg (Male Open)")
plt.xticks(rotation=0)
plt.xlabel("Station")
plt.ylabel("Minutes")
plt.title("Station Splits — You vs Race Averages")
plt.legend()
plt.tight_layout()
plt.show()
