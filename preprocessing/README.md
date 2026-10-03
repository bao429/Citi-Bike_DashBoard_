# Preprocessing

`citibike_prep.py` reads the Citi Bike trip files, checks and cleans them, and writes four small summary
tables for the dashboard. The web page loads only these summary tables, never the raw trips.

## Data

- Source: https://s3.amazonaws.com/tripdata/index.html (NYCBS Data Use Policy)
- Files used: the Jersey City / Hoboken files for January, April, July and October 2025
  (`JC-202501-…`, `JC-202504-…`, `JC-202507-…`, `JC-202510-…`).
- Put the four zips in `data/raw/`. That folder is in `.gitignore`: **do not commit raw data.**

## Run

Needs Python 3.10+ and DuckDB.

```bash
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r preprocessing/requirements.txt

python preprocessing/citibike_prep.py --input data/raw/JC-2025*.zip --out data/processed
```

It takes a few seconds. Output:

- `data/processed/profile.md`: row counts, missing values, duration checks and the cleaning counts
- `data/processed/summary/*.csv`: the four tables below

The script unzips into a temporary `_work/` folder and deletes it at the end.

## Cleaning rules

Counts are for the four JC months (344,095 rows in total).

| Rule | Rows |
|---|---|
| Trip started in the month before the file's month (files hold trips that *ended* in that month) | 33 |
| No start station | 1 |
| Same start and end station and shorter than 2 minutes (false start) | 803 |
| Longer than 3 hours | 540 |
| **Dropped** | **1,365** |
| **Kept** | **342,720** |
| …of which have an end station (used for arrivals and routes) | 341,577 |

Also done: station IDs are read as text, each station ID gets one name (the most common spelling), and
coordinates outside the service area are blanked (none in these files).

Timestamps in the raw files are `YYYY-MM-DD HH:MM:SS.sss` (24-hour clock) with no time zone. The commute
peaks at 08:00 and 17:00 fit local New York time, so they are treated as local time.

## Output tables

| File | Rows | Size | Columns |
|---|---|---|---|
| `stations.csv` | 337 | 15 KB | station_id, name, lat, lon |
| `station_hourly.csv` | 83,404 | 2.4 MB | station_id, month, weekday, hour, member_type, departures, arrivals |
| `daily.csv` | 246 | 8 KB | date, member_type, trips, avg_duration_min, median_duration_min |
| `routes.csv` | 400 | 14 KB | start_station_id, end_station_id, member_type, day_type, trips, median_duration_min |

- `weekday` is 1 = Monday … 7 = Sunday. `day_type` is `weekday` or `weekend`.
- Departures are counted at the start station by start time, arrivals at the end station by end time.
- `routes.csv` leaves out round trips and keeps the top 100 routes for each member type and day type.
- `stations.csv` has 97 Jersey City / Hoboken stations plus the New York stations where some trips end.

## Options

| Flag | Default | Meaning |
|---|---|---|
| `--top-routes` | 100 | Routes kept per member type × day type |
| `--max-duration-min` | 180 | Drop trips longer than this |
| `--false-start-sec` | 120 | Drop same-station trips shorter than this |
| `--memory-limit` | 2GB | DuckDB memory limit |
| `--threads` | 0 | 0 = DuckDB default |
| `--keep-work` | off | Keep the extracted CSVs and `trips.duckdb` for extra queries |
