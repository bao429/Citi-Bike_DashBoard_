#!/usr/bin/env python3
"""Summary tables for the "User type analysis" charts.

Reads the CLEANED trips written by citibike_prep.py (data/processed/trips_clean.parquet)
and writes small tables for the browser into data/processed/summary/:

  user_type_summary.csv  month, day_type, member_type, trips, total_duration_min
  duration_hist.csv      month, day_type, member_type, bin_start_min, trips   (1-minute bins, 0..180)
  dow_hour.csv           month, member_type, weekday, hour, trips             (weekday: 1 = Mon ... 7 = Sun)
  weekday_counts.csv     month, weekday, n_days                               (calendar days, for per-day averages)
  duration_stats.csv     member_type, trips, pct_trips, mean/median/p25/p75/p90/p95/p99, pct_weekend
                         (for the report and for checking the browser boxplot; the browser does not load it)

Column names follow citibike_prep.py (member_type, duration_min, weekday, hour, month).

Usage (from the project root, after running citibike_prep.py):
    python preprocessing/prep_user_type.py
    python preprocessing/prep_user_type.py --trips data/processed/trips_clean.parquet --out data/processed/summary
"""
import argparse
import calendar
import csv
import datetime as dt
import os
import sys

import duckdb

REQUIRED = {"member_type", "duration_min", "month", "weekday", "hour"}


def q(path):
    """Escape a path for use inside a SQL string literal."""
    return path.replace("'", "''")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trips", default=os.path.join("data", "processed", "trips_clean.parquet"),
                    help="cleaned trips written by citibike_prep.py")
    ap.add_argument("--out", default=os.path.join("data", "processed", "summary"),
                    help="folder for the summary CSV files")
    ap.add_argument("--max-min", type=float, default=180,
                    help="longest trip (minutes) allowed in the cleaned data; must match citibike_prep.py")
    args = ap.parse_args()

    if not os.path.exists(args.trips):
        sys.exit(f"Cannot find {args.trips}. Run preprocessing/citibike_prep.py first "
                 f"(it writes trips_clean.parquet next to profile.md).")
    os.makedirs(args.out, exist_ok=True)

    con = duckdb.connect()   # in-memory is enough: ~340k rows

    # ---- 1. load and check the columns -------------------------------------------------
    src = f"read_parquet('{q(args.trips)}')"
    cols = {r[0] for r in con.sql(f"DESCRIBE SELECT * FROM {src}").fetchall()}
    missing = REQUIRED - cols
    if missing:
        sys.exit(f"{args.trips} is missing columns: {sorted(missing)}. Found: {sorted(cols)}")

    con.sql(f"""
        CREATE TABLE t AS
        SELECT member_type, duration_min, month, weekday, hour,
               CASE WHEN weekday >= 6 THEN 'weekend' ELSE 'weekday' END AS day_type
        FROM {src}
    """)
    n = con.execute("SELECT count(*) FROM t").fetchone()[0]
    bad = con.execute(f"""
        SELECT count(*) FROM t
        WHERE member_type NOT IN ('member', 'casual') OR member_type IS NULL
           OR duration_min IS NULL OR duration_min <= 0 OR duration_min > {args.max_min}
           OR weekday NOT BETWEEN 1 AND 7 OR hour NOT BETWEEN 0 AND 23
    """).fetchone()[0]
    if bad:
        sys.exit(f"{bad:,} rows break the data rules (user type, duration or time fields). "
                 f"Check the cleaning step before building tables.")
    print(f"Cleaned trips read: {n:,}")

    # ---- 2. tables ----------------------------------------------------------------------
    con.execute("""
        CREATE TABLE user_type_summary AS
        SELECT month, day_type, member_type,
               count(*) AS trips,
               round(sum(duration_min), 2) AS total_duration_min
        FROM t GROUP BY ALL ORDER BY ALL;

        CREATE TABLE duration_hist AS
        SELECT month, day_type, member_type,
               CAST(floor(duration_min) AS INTEGER) AS bin_start_min,
               count(*) AS trips
        FROM t GROUP BY ALL ORDER BY ALL;

        CREATE TABLE dow_hour AS
        SELECT month, member_type, weekday, hour, count(*) AS trips
        FROM t GROUP BY ALL ORDER BY ALL;

        CREATE TABLE duration_stats AS
        SELECT member_type,
               count(*) AS trips,
               round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct_trips,
               round(avg(duration_min), 2) AS mean_min,
               round(median(duration_min), 2) AS median_min,
               round(quantile_cont(duration_min, 0.25), 2) AS p25_min,
               round(quantile_cont(duration_min, 0.75), 2) AS p75_min,
               round(quantile_cont(duration_min, 0.90), 2) AS p90_min,
               round(quantile_cont(duration_min, 0.95), 2) AS p95_min,
               round(quantile_cont(duration_min, 0.99), 2) AS p99_min,
               round(100.0 * avg((weekday >= 6)::INT), 1) AS pct_weekend
        FROM t GROUP BY member_type ORDER BY member_type;
    """)

    # number of each weekday in each month, from the calendar (not from the data, so a day
    # with no trips is still counted)
    months = [r[0] for r in con.sql("SELECT DISTINCT month FROM t ORDER BY 1").fetchall()]
    wd_rows = []
    for m in months:
        year, mon = (int(x) for x in m.split("-"))
        counts = [0] * 7
        for day in range(1, calendar.monthrange(year, mon)[1] + 1):
            counts[dt.date(year, mon, day).isoweekday() - 1] += 1
        wd_rows += [(m, i + 1, counts[i]) for i in range(7)]
    with open(os.path.join(args.out, "weekday_counts.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["month", "weekday", "n_days"])
        w.writerows(wd_rows)

    # ---- 3. checks: every table must add up to the cleaned trips -----------------------
    for name in ("user_type_summary", "duration_hist", "dow_hour", "duration_stats"):
        s = con.execute(f"SELECT sum(trips) FROM {name}").fetchone()[0]
        assert s == n, f"{name}: trips add up to {s:,} but the cleaned data has {n:,}"
    print("Checks passed: all tables add up to the cleaned trips.")

    # ---- 4. write CSV ---------------------------------------------------------------------
    print(f"\nWrote to {args.out}:")
    for name in ("user_type_summary", "duration_hist", "dow_hour", "duration_stats"):
        path = os.path.join(args.out, f"{name}.csv")
        con.execute(f"COPY {name} TO '{q(path)}' (HEADER, DELIMITER ',')")
        rows = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"  {name}.csv  {rows:,} rows  {os.path.getsize(path) / 1024:.1f} KB")
    print(f"  weekday_counts.csv  {len(wd_rows)} rows")

    print("\nMember vs casual:")
    cur = con.execute("SELECT * FROM duration_stats")
    print("  " + " | ".join(col[0] for col in cur.description))
    for r in cur.fetchall():
        print("  " + " | ".join(str(v) for v in r))
    con.close()


if __name__ == "__main__":
    main()