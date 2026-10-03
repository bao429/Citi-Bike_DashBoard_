#!/usr/bin/env python3
"""Profile, clean and aggregate Citi Bike trip-history files with DuckDB.

Works for the NYC monthly files (e.g. 202501-citibike-tripdata.zip, which holds
several CSVs) and the Jersey City / Hoboken files (JC-YYYYMM-citibike-tripdata*.zip).

The raw trips are loaded once into an on-disk DuckDB database inside --work, so
memory stays bounded (DuckDB spills to disk above --memory-limit). Only the small
summary tables in --out/summary/ are meant for the browser.

Usage:
    python citibike_prep.py --input ZIP_OR_CSV_OR_DIR [...] --out OUT_DIR [--work WORK_DIR]
"""
import argparse
import glob
import gzip
import json
import os
import shutil
import sys
import time
import zipfile

import duckdb

EXPECTED_COLUMNS = [
    "ride_id", "rideable_type", "started_at", "ended_at",
    "start_station_name", "start_station_id", "end_station_name", "end_station_id",
    "start_lat", "start_lng", "end_lat", "end_lng", "member_casual",
]

# Generous box around the Citi Bike service area (NYC boroughs + Jersey City/Hoboken).
# This is our own assumption, not an official boundary.
BBOX = dict(lat_min=40.55, lat_max=40.95, lng_min=-74.20, lng_max=-73.70)

# Public station IDs look like "6182.02" (NYC) or "JC019" / "HB101" (NJ).
# Anything else (SYS016, "Shop Morgan", "LA Metro Demo 1", ...) is treated as non-public.
PUBLIC_ID_RE = r"^(\d+\.\d{2}|(JC|HB)\d+)$"


# --------------------------------------------------------------------------- input


def collect_csvs(inputs, work_dir):
    """Return (csv_paths, extraction_log). Zips are extracted into work_dir/raw/."""
    csvs, log = [], []
    for item in inputs:
        if os.path.isdir(item):
            for p in sorted(glob.glob(os.path.join(item, "**", "*.csv"), recursive=True)):
                if "__MACOSX" not in p and not os.path.basename(p).startswith("._"):
                    csvs.append(p)
        elif item.lower().endswith(".zip"):
            dest = os.path.join(work_dir, "raw", os.path.splitext(os.path.basename(item))[0])
            os.makedirs(dest, exist_ok=True)
            with zipfile.ZipFile(item) as zf:
                for info in zf.infolist():
                    name = info.filename
                    skipped = ("__MACOSX" in name or os.path.basename(name).startswith("._")
                               or not name.lower().endswith(".csv"))
                    log.append(dict(zip=os.path.basename(item), member=name,
                                    bytes=info.file_size, used=not skipped))
                    if skipped:
                        continue
                    target = os.path.join(dest, os.path.basename(name))
                    if not (os.path.exists(target) and os.path.getsize(target) == info.file_size):
                        with zf.open(info) as src, open(target, "wb") as dst:
                            while chunk := src.read(1 << 20):
                                dst.write(chunk)
                    csvs.append(target)
        elif item.lower().endswith(".csv"):
            csvs.append(item)
        else:
            sys.exit(f"Unsupported input: {item}")
    if not csvs:
        sys.exit("No CSV files found in the inputs.")
    return csvs, log


# --------------------------------------------------------------------------- helpers


def md_table(rel):
    """Render a DuckDB relation as a markdown table."""
    cols = rel.columns
    rows = rel.fetchall()

    def fmt(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:,.1f}" if abs(v) >= 1000 else f"{v:.4f}".rstrip("0").rstrip(".")
        if isinstance(v, int):
            return f"{v:,}"
        return str(v)

    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(fmt(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def sql_list(paths):
    return "[" + ", ".join("'" + p.replace("'", "''") + "'" for p in paths) + "]"


def human(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


# --------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", nargs="+", required=True, help="zip files, CSV files or directories")
    ap.add_argument("--out", required=True, help="output folder (profile.md + summary/)")
    ap.add_argument("--work", help="scratch folder for extracted CSVs and the DuckDB file (default: OUT/_work)")
    ap.add_argument("--memory-limit", default="2GB")
    ap.add_argument("--threads", type=int, default=0, help="0 = DuckDB default")
    ap.add_argument("--max-duration-min", type=float, default=180, help="drop longer trips (default 180)")
    ap.add_argument("--false-start-sec", type=float, default=120,
                    help="drop same-station trips shorter than this (default 120)")
    ap.add_argument("--top-routes", type=int, default=100, help="routes kept per member_type x day_type")
    ap.add_argument("--keep-work", action="store_true",
                    help="keep extracted CSVs and trips.duckdb (default: delete them at the end)")
    args = ap.parse_args()

    t0 = time.time()
    work = args.work or os.path.join(args.out, "_work")
    summary_dir = os.path.join(args.out, "summary")
    os.makedirs(work, exist_ok=True)
    os.makedirs(summary_dir, exist_ok=True)

    csvs, zlog = collect_csvs(args.input, work)

    db_path = os.path.join(work, "trips.duckdb")
    if os.path.exists(db_path):
        os.remove(db_path)
    con = duckdb.connect(db_path)
    con.execute(f"SET memory_limit='{args.memory_limit}'")
    con.execute(f"SET temp_directory='{os.path.join(work, 'duckdb_tmp')}'")
    if args.threads:
        con.execute(f"SET threads={args.threads}")

    report = []          # markdown chunks
    facts = {}           # machine-readable numbers
    H = lambda s: report.append(f"\n## {s}\n")
    P = lambda s: report.append(s)
    T = lambda sql: report.append("\n" + md_table(con.sql(sql)) + "\n")

    report.append("# Citi Bike preprocessing profile\n")
    P(f"Inputs: {', '.join(os.path.basename(i) for i in args.input)}  ")
    P(f"DuckDB {duckdb.__version__}, memory_limit={args.memory_limit}")

    # ---- 1. files and raw header -------------------------------------------------
    H("1. Files")
    if zlog:
        P("Zip members (`used` = read as data; __MACOSX/._ resource files are skipped):\n")
        P("| zip | member | bytes | used |\n|---|---|---|---|")
        for z in zlog:
            P(f"| {z['zip']} | {z['member']} | {z['bytes']:,} | {z['used']} |")
    headers = {}
    for p in csvs:
        with open(p, "r", encoding="utf-8", newline="") as f:
            headers[p] = f.readline().rstrip("\r\n")
    P("\nRaw header line per CSV:\n")
    for p, h in headers.items():
        P(f"- `{os.path.basename(p)}` ({human(os.path.getsize(p))}): `{h}`")
    parsed = [c.strip('"') for c in next(iter(headers.values())).split(",")]
    if any([c.strip('"') for c in h.split(",")] != parsed for h in headers.values()):
        sys.exit("CSV headers differ between files; stop and inspect.")
    if parsed != EXPECTED_COLUMNS:
        sys.exit(f"Unexpected header {parsed}; update EXPECTED_COLUMNS after checking.")
    facts["columns"] = parsed

    # ---- 2. load ------------------------------------------------------------------
    con.execute(f"""
        CREATE TABLE raw AS
        SELECT *, regexp_extract(filename, '(\\d{{6}})-citibike', 1) AS file_month
        FROM read_csv({sql_list(csvs)}, header=true, filename=true,
             types={{'ride_id':'VARCHAR','rideable_type':'VARCHAR','started_at':'TIMESTAMP',
                     'ended_at':'TIMESTAMP','start_station_name':'VARCHAR','start_station_id':'VARCHAR',
                     'end_station_name':'VARCHAR','end_station_id':'VARCHAR','start_lat':'DOUBLE',
                     'start_lng':'DOUBLE','end_lat':'DOUBLE','end_lng':'DOUBLE','member_casual':'VARCHAR'}})
    """)
    H("2. Row counts and types")
    T("SELECT regexp_extract(filename, '[^/\\\\]+$') AS file, file_month, count(*) AS rows FROM raw GROUP BY ALL ORDER BY 1")
    n_raw = con.sql("SELECT count(*) FROM raw").fetchone()[0]
    facts["rows_raw"] = n_raw
    P(f"\n**Total rows: {n_raw:,}**\n")
    P("Column types used for loading (all station IDs are read as text on purpose):\n")
    T("SELECT column_name, column_type FROM (DESCRIBE raw) WHERE column_name NOT IN ('filename')")

    # ---- 3. timestamps ------------------------------------------------------------
    H("3. Timestamp format and time zone evidence")
    ts = con.sql(f"""
        SELECT count(*) AS n,
               count(*) FILTER (regexp_full_match(started_at, '\\d{{4}}-\\d{{2}}-\\d{{2}} \\d{{2}}:\\d{{2}}:\\d{{2}}(\\.\\d+)?')) AS started_iso,
               count(*) FILTER (regexp_full_match(ended_at,   '\\d{{4}}-\\d{{2}}-\\d{{2}} \\d{{2}}:\\d{{2}}:\\d{{2}}(\\.\\d+)?')) AS ended_iso,
               count(*) FILTER (regexp_matches(started_at || ended_at, '[AaPp][Mm]|[+-]\\d{{2}}:?\\d{{2}}$|Z$')) AS am_pm_or_offset,
               any_value(started_at) AS example
        FROM read_csv({sql_list(csvs)}, header=true, all_varchar=true)
    """)
    P("Raw text of `started_at` / `ended_at` checked against `YYYY-MM-DD HH:MM:SS(.fff)`:\n")
    P("\n" + md_table(ts) + "\n")
    P("\nRange of parsed timestamps:\n")
    T("SELECT min(started_at) AS min_started, max(started_at) AS max_started, min(ended_at) AS min_ended, max(ended_at) AS max_ended FROM raw")
    P("\nWhich month does each file hold? (rows whose start/end month differs from the month in the file name)\n")
    T("""SELECT file_month,
                count(*) FILTER (strftime(started_at, '%Y%m') <> file_month) AS started_other_month,
                count(*) FILTER (strftime(ended_at,   '%Y%m') <> file_month) AS ended_other_month
         FROM raw GROUP BY 1 ORDER BY 1""")
    P("\nWeekday trips by start hour (local-time check: commute peaks should be near 08 and 17-18):\n")
    T("""SELECT hour(started_at) AS hour, count(*) AS weekday_trips
         FROM raw WHERE isodow(started_at) <= 5 GROUP BY 1 ORDER BY 1""")

    # ---- 4. missing values ----------------------------------------------------------
    H("4. Missing values by rideable_type")
    T("""SELECT coalesce(rideable_type, 'ALL') AS rideable_type, count(*) AS rows,
                count(*) FILTER (start_station_id IS NULL)   AS no_start_id,
                count(*) FILTER (start_station_name IS NULL) AS no_start_name,
                count(*) FILTER (start_lat IS NULL OR start_lng IS NULL) AS no_start_coord,
                count(*) FILTER (end_station_id IS NULL)     AS no_end_id,
                count(*) FILTER (end_station_name IS NULL)   AS no_end_name,
                count(*) FILTER (end_lat IS NULL OR end_lng IS NULL) AS no_end_coord,
                count(*) FILTER (end_station_name IS NOT NULL AND end_station_id IS NULL) AS end_name_but_no_id,
                count(*) FILTER (end_station_id IS NULL AND end_lat IS NOT NULL) AS end_coord_but_no_station
         FROM raw GROUP BY ROLLUP(rideable_type) ORDER BY rideable_type NULLS LAST""")
    P("\nOther columns:\n")
    T("""SELECT count(*) FILTER (ride_id IS NULL) AS no_ride_id, count(*) FILTER (rideable_type IS NULL) AS no_rideable_type,
                count(*) FILTER (started_at IS NULL) AS no_started_at, count(*) FILTER (ended_at IS NULL) AS no_ended_at,
                count(*) FILTER (member_casual IS NULL) AS no_member_casual FROM raw""")
    P("\nCategory values:\n")
    T("SELECT rideable_type, member_casual, count(*) AS rows FROM raw GROUP BY ALL ORDER BY ALL")

    # ---- 5. station IDs -------------------------------------------------------------
    con.execute(f"""
        CREATE MACRO norm_id(x) AS
            regexp_replace(rtrim(trim(x), '_'), '^(\\d+\\.\\d)$', '\\10');
        CREATE MACRO is_public(x) AS regexp_full_match(x, '{PUBLIC_ID_RE}');
    """)
    H("5. Station ID problems")
    T("""SELECT count(*) FILTER (regexp_full_match(start_station_id, '\\d+\\.\\d') OR regexp_full_match(end_station_id, '\\d+\\.\\d')) AS rows_with_1_decimal_id,
                count(*) FILTER (start_station_id LIKE '%\\_' ESCAPE '\\' OR end_station_id LIKE '%\\_' ESCAPE '\\') AS rows_with_trailing_underscore
         FROM raw""")
    P("\nIDs that are not public stations after normalisation (excluded):\n")
    T("""WITH s AS (SELECT norm_id(start_station_id) AS id, start_station_name AS name FROM raw
                    UNION ALL SELECT norm_id(end_station_id), end_station_name FROM raw)
         SELECT id, any_value(name) AS name, count(*) AS appearances FROM s
         WHERE id IS NOT NULL AND NOT is_public(id) GROUP BY id ORDER BY appearances DESC""")
    P("\nSame ID with several names (after normalisation; the most frequent name is kept):\n")
    T("""WITH s AS (SELECT norm_id(start_station_id) AS id, start_station_name AS name FROM raw
                    UNION ALL SELECT norm_id(end_station_id), end_station_name FROM raw)
         SELECT id, list(DISTINCT name ORDER BY name) AS names FROM s WHERE id IS NOT NULL
         GROUP BY id HAVING count(DISTINCT name) > 1 ORDER BY id""")
    T("""SELECT count(DISTINCT start_station_id) AS raw_start_ids, count(DISTINCT norm_id(start_station_id)) AS normalised_start_ids,
                count(DISTINCT end_station_id) AS raw_end_ids, count(DISTINCT norm_id(end_station_id)) AS normalised_end_ids FROM raw""")

    # ---- 6. durations, duplicates, coordinates ---------------------------------------
    con.execute("CREATE MACRO in_bbox(la, lo) AS la BETWEEN {lat_min} AND {lat_max} AND lo BETWEEN {lng_min} AND {lng_max}".format(**BBOX))
    H("6. Durations")
    T("""WITH d AS (SELECT epoch(ended_at - started_at) AS s, start_station_id = end_station_id AS same FROM raw)
         SELECT count(*) FILTER (s < 0) AS end_before_start, count(*) FILTER (s = 0) AS zero,
                count(*) FILTER (s < 60) AS under_1min, count(*) FILTER (s < 120) AS under_2min,
                count(*) FILTER (s < 120 AND same) AS under_2min_same_station,
                count(*) FILTER (s > 3 * 3600) AS over_3h, count(*) FILTER (s > 24 * 3600) AS over_24h,
                round(min(s), 1) AS min_sec, round(max(s) / 3600, 2) AS max_hours FROM d""")
    P("\nDuration percentiles (minutes) by rider type:\n")
    T("""SELECT member_casual, round(quantile_cont(m, 0.01), 2) AS p01, round(quantile_cont(m, 0.25), 2) AS p25,
                round(median(m), 2) AS median, round(avg(m), 2) AS mean, round(quantile_cont(m, 0.75), 2) AS p75,
                round(quantile_cont(m, 0.99), 2) AS p99
         FROM (SELECT member_casual, epoch(ended_at - started_at) / 60 AS m FROM raw) GROUP BY 1 ORDER BY 1""")
    H("7. Duplicates")
    T("""SELECT count(*) - count(DISTINCT ride_id) AS duplicate_ride_ids,
                count(*) - count(DISTINCT (rideable_type, started_at, ended_at, start_station_id, end_station_id,
                                           start_lat, start_lng, end_lat, end_lng, member_casual)) AS duplicate_rows_ignoring_ride_id
         FROM raw""")
    H("8. Coordinates outside the expected area")
    P("Box used (our assumption): lat {lat_min}..{lat_max}, lng {lng_min}..{lng_max}.\n".format(**BBOX))
    T("""SELECT count(*) FILTER (start_lat IS NOT NULL AND NOT in_bbox(start_lat, start_lng)) AS start_outside,
                count(*) FILTER (end_lat IS NOT NULL AND NOT in_bbox(end_lat, end_lng)) AS end_outside,
                count(*) FILTER (start_lat = 0 OR start_lng = 0 OR end_lat = 0 OR end_lng = 0) AS any_zero_coord FROM raw""")
    T("""SELECT 'end' AS side, end_station_id AS id, end_station_name AS name, end_lat AS lat, end_lng AS lng, count(*) AS rows
         FROM raw WHERE end_lat IS NOT NULL AND NOT in_bbox(end_lat, end_lng) GROUP BY ALL
         UNION ALL
         SELECT 'start', start_station_id, start_station_name, start_lat, start_lng, count(*)
         FROM raw WHERE start_lat IS NOT NULL AND NOT in_bbox(start_lat, start_lng) GROUP BY ALL
         ORDER BY rows DESC LIMIT 20""")
    P("\nObserved coordinate range of start points (helps tell which area a file covers):\n")
    T("""SELECT round(min(start_lat), 4) AS min_lat, round(max(start_lat), 4) AS max_lat,
                round(min(start_lng), 4) AS min_lng, round(max(start_lng), 4) AS max_lng FROM raw""")
    T("""SELECT CASE WHEN start_station_id LIKE 'JC%' THEN 'JC (Jersey City)' WHEN start_station_id LIKE 'HB%' THEN 'HB (Hoboken)'
                     WHEN start_station_id IS NULL THEN 'missing' ELSE 'numeric (NYC)' END AS start_id_family,
                count(*) AS rows, count(DISTINCT start_station_id) AS stations FROM raw GROUP BY 1 ORDER BY 2 DESC""")
    T("""SELECT CASE WHEN end_station_id LIKE 'JC%' THEN 'JC (Jersey City)' WHEN end_station_id LIKE 'HB%' THEN 'HB (Hoboken)'
                     WHEN end_station_id IS NULL THEN 'missing' ELSE 'numeric (NYC)' END AS end_id_family,
                count(*) AS rows, count(DISTINCT end_station_id) AS stations FROM raw GROUP BY 1 ORDER BY 2 DESC""")

    # ---- 9. clean + derive ---------------------------------------------------------
    con.execute(f"""
        CREATE TABLE trips AS
        WITH b AS (
            SELECT ride_id, rideable_type, member_casual AS member_type, started_at, ended_at, file_month,
                   norm_id(start_station_id) AS start_id, start_station_name AS start_name,
                   norm_id(end_station_id)   AS end_id,   end_station_name   AS end_name,
                   CASE WHEN in_bbox(start_lat, start_lng) THEN start_lat END AS start_lat,
                   CASE WHEN in_bbox(start_lat, start_lng) THEN start_lng END AS start_lng,
                   CASE WHEN in_bbox(end_lat, end_lng) THEN end_lat END AS end_lat,
                   CASE WHEN in_bbox(end_lat, end_lng) THEN end_lng END AS end_lng,
                   epoch(ended_at - started_at) AS dur_s
            FROM raw)
        SELECT *,
               dur_s / 60.0                               AS duration_min,
               CAST(started_at AS DATE)                   AS date,
               strftime(started_at, '%Y-%m')              AS month,
               isodow(started_at)                         AS weekday,      -- 1 = Mon ... 7 = Sun
               hour(started_at)                           AS hour,
               isodow(started_at) >= 6                    AS is_weekend,
               file_month IS NOT NULL AND strftime(started_at, '%Y%m') <> file_month AS f_other_month,
               start_id IS NULL                           AS f_no_start,
               (start_id IS NOT NULL AND NOT is_public(start_id)) OR (end_id IS NOT NULL AND NOT is_public(end_id)) AS f_nonpublic,
               dur_s < 0                                  AS f_negative,
               start_id = end_id AND dur_s < {args.false_start_sec} AS f_false_start,
               dur_s > {args.max_duration_min} * 60       AS f_too_long,
               end_id IS NULL                             AS f_no_end
        FROM b
    """)
    con.execute("""
        ALTER TABLE trips ADD COLUMN keep BOOLEAN;
        UPDATE trips SET keep = NOT (f_other_month OR f_no_start OR f_nonpublic OR f_negative OR f_false_start OR f_too_long);
        ALTER TABLE trips ADD COLUMN keep_od BOOLEAN;
        UPDATE trips SET keep_od = keep AND NOT f_no_end;
    """)
    H("9. Cleaning rules applied (counts are not exclusive; a row can hit several)")
    T(f"""SELECT count(*) FILTER (f_other_month) AS started_outside_file_month,
                 count(*) FILTER (f_no_start) AS no_start_station,
                 count(*) FILTER (f_nonpublic) AS test_or_service_station,
                 count(*) FILTER (f_negative) AS end_before_start,
                 count(*) FILTER (f_false_start) AS same_station_under_{int(args.false_start_sec)}s,
                 count(*) FILTER (f_too_long) AS over_{int(args.max_duration_min)}min,
                 count(*) FILTER (NOT keep) AS dropped_total,
                 count(*) FILTER (keep) AS kept_trips,
                 count(*) FILTER (keep AND f_no_end) AS kept_but_no_end_station,
                 count(*) FILTER (keep_od) AS kept_with_both_stations
          FROM trips""")
    kept, kept_od = con.sql("SELECT count(*) FILTER (keep), count(*) FILTER (keep_od) FROM trips").fetchone()
    facts.update(kept_trips=kept, kept_od=kept_od)
    P("\n`kept_trips` feed departures and daily counts; `kept_with_both_stations` feed arrivals and routes.")

    # ---- 10. summary tables ----------------------------------------------------------
    con.execute("""
        CREATE TABLE stations AS
        WITH pts AS (
            SELECT start_id AS id, start_name AS name, start_lat AS lat, start_lng AS lng, rideable_type FROM trips WHERE keep
            UNION ALL
            SELECT end_id, end_name, end_lat, end_lng, rideable_type FROM trips WHERE keep_od)
        SELECT id AS station_id,
               mode(name) AS name,
               round(coalesce(median(lat) FILTER (rideable_type = 'classic_bike'), median(lat)), 5) AS lat,
               round(coalesce(median(lng) FILTER (rideable_type = 'classic_bike'), median(lng)), 5) AS lon
        FROM pts GROUP BY id ORDER BY id;

        CREATE TABLE station_hourly AS
        WITH dep AS (
            SELECT start_id AS station_id, month, weekday, hour, member_type, count(*) AS departures
            FROM trips WHERE keep GROUP BY ALL),
        arr AS (
            SELECT end_id AS station_id, strftime(ended_at, '%Y-%m') AS month, isodow(ended_at) AS weekday,
                   hour(ended_at) AS hour, member_type, count(*) AS arrivals
            FROM trips WHERE keep_od GROUP BY ALL)
        SELECT coalesce(dep.station_id, arr.station_id) AS station_id, coalesce(dep.month, arr.month) AS month,
               coalesce(dep.weekday, arr.weekday) AS weekday, coalesce(dep.hour, arr.hour) AS hour,
               coalesce(dep.member_type, arr.member_type) AS member_type,
               coalesce(departures, 0) AS departures, coalesce(arrivals, 0) AS arrivals
        FROM dep FULL OUTER JOIN arr USING (station_id, month, weekday, hour, member_type)
        ORDER BY ALL;

        CREATE TABLE daily AS
        SELECT date, member_type, count(*) AS trips,
               round(avg(duration_min), 2) AS avg_duration_min,
               round(median(duration_min), 2) AS median_duration_min
        FROM trips WHERE keep GROUP BY ALL ORDER BY ALL;
    """)
    con.execute(f"""
        CREATE TABLE routes AS
        SELECT start_id AS start_station_id, end_id AS end_station_id, member_type, day_type, trips, median_duration_min
        FROM (
            SELECT *, row_number() OVER (PARTITION BY member_type, day_type ORDER BY trips DESC, start_id, end_id) AS rk
            FROM (
                SELECT start_id, end_id, member_type,
                       CASE WHEN is_weekend THEN 'weekend' ELSE 'weekday' END AS day_type,
                       count(*) AS trips, round(median(duration_min), 2) AS median_duration_min
                FROM trips WHERE keep_od AND start_id <> end_id GROUP BY 1, 2, 3, 4))
        WHERE rk <= {args.top_routes}
        ORDER BY member_type, day_type, trips DESC, start_station_id, end_station_id
    """)
    # sanity: arrivals/departures must reconcile with the trip table
    dep_sum, arr_sum = con.sql("SELECT sum(departures), sum(arrivals) FROM station_hourly").fetchone()
    assert dep_sum == kept and arr_sum == kept_od, (dep_sum, arr_sum, kept, kept_od)

    H("10. Summary tables for the browser")
    P(f"Routes exclude round trips (start = end) and keep the top {args.top_routes} per member_type x day_type.\n")
    P("| file | rows | CSV size | gzip size |\n|---|---|---|---|")
    sizes = {}
    for name in ["stations", "station_hourly", "daily", "routes"]:
        path = os.path.join(summary_dir, f"{name}.csv")
        con.execute(f"COPY {name} TO '{path}' (HEADER, DELIMITER ',')")
        raw_bytes = open(path, "rb").read()
        gz = len(gzip.compress(raw_bytes, 9))
        rows = con.sql(f"SELECT count(*) FROM {name}").fetchone()[0]
        sizes[name] = dict(rows=rows, bytes=len(raw_bytes), gzip_bytes=gz)
        P(f"| summary/{name}.csv | {rows:,} | {human(len(raw_bytes))} | {human(gz)} |")
    facts["summary"] = sizes
    raw_total = sum(os.path.getsize(p) for p in csvs)
    facts["raw_csv_bytes"] = raw_total
    P(f"\nRaw CSV input: {human(raw_total)}. Summary total: {human(sum(s['bytes'] for s in sizes.values()))}.")

    P("\nPreview, top 5 routes per group:\n")
    T("""SELECT r.member_type, r.day_type, s1.name AS start_name, s2.name AS end_name, r.trips
         FROM (SELECT *, row_number() OVER (PARTITION BY member_type, day_type ORDER BY trips DESC) rk FROM routes) r
         JOIN stations s1 ON s1.station_id = r.start_station_id JOIN stations s2 ON s2.station_id = r.end_station_id
         WHERE rk <= 5 ORDER BY r.member_type, r.day_type, r.trips DESC""")
    P("\nPreview, largest net outflow / inflow stations (departures - arrivals, whole period):\n")
    T("""SELECT s.name, sum(departures) AS departures, sum(arrivals) AS arrivals, sum(departures) - sum(arrivals) AS net_out
         FROM station_hourly h JOIN stations s USING (station_id) GROUP BY s.name ORDER BY net_out DESC LIMIT 5""")
    T("""SELECT s.name, sum(departures) AS departures, sum(arrivals) AS arrivals, sum(departures) - sum(arrivals) AS net_out
         FROM station_hourly h JOIN stations s USING (station_id) GROUP BY s.name ORDER BY net_out ASC LIMIT 5""")
    P("\nPreview, member vs casual:\n")
    T("""SELECT member_type, count(*) AS trips, round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct,
                round(median(duration_min), 2) AS median_min, round(100.0 * avg(is_weekend::INT), 1) AS pct_weekend
         FROM trips WHERE keep GROUP BY 1 ORDER BY 1""")

    elapsed = time.time() - t0
    P(f"\n_Run time: {elapsed:.1f} s._")
    facts["runtime_s"] = round(elapsed, 1)
    with open(os.path.join(args.out, "profile.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    with open(os.path.join(args.out, "profile.json"), "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2, default=str)
    con.close()
    if not args.keep_work:
        # only remove what this script created: extracted zip members, the DuckDB file, its temp dir
        extracted = [os.path.join(work, "raw", os.path.splitext(os.path.basename(i))[0])
                     for i in args.input if i.lower().endswith(".zip")]
        for leftover in extracted + [db_path, db_path + ".wal", os.path.join(work, "duckdb_tmp")]:
            if os.path.isdir(leftover):
                shutil.rmtree(leftover)
            elif os.path.exists(leftover):
                os.remove(leftover)
        for d in [os.path.join(work, "raw"), work]:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
    print(f"Done in {elapsed:.1f} s. Wrote {args.out}/profile.md and {summary_dir}/*.csv")


if __name__ == "__main__":
    main()
