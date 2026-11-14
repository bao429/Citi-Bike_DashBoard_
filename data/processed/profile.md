# Citi Bike preprocessing profile

Inputs: JC-202501-citibike-tripdata.csv, JC-202504-citibike-tripdata.csv, JC-202507-citibike-tripdata.csv, JC-202510-citibike-tripdata.csv  
DuckDB 2.0.0, memory_limit=2GB

## 1. Files


Raw header line per CSV:

- `JC-202501-citibike-tripdata.csv` (10.6 MB): `"ride_id","rideable_type","started_at","ended_at","start_station_name","start_station_id","end_station_name","end_station_id","start_lat","start_lng","end_lat","end_lng","member_casual"`
- `JC-202504-citibike-tripdata.csv` (17.0 MB): `"ride_id","rideable_type","started_at","ended_at","start_station_name","start_station_id","end_station_name","end_station_id","start_lat","start_lng","end_lat","end_lng","member_casual"`
- `JC-202507-citibike-tripdata.csv` (22.2 MB): `"ride_id","rideable_type","started_at","ended_at","start_station_name","start_station_id","end_station_name","end_station_id","start_lat","start_lng","end_lat","end_lng","member_casual"`
- `JC-202510-citibike-tripdata.csv` (21.6 MB): `"ride_id","rideable_type","started_at","ended_at","start_station_name","start_station_id","end_station_name","end_station_id","start_lat","start_lng","end_lat","end_lng","member_casual"`

## 2. Row counts and types


| file | file_month | rows |
|---|---|---|
| JC-202501-citibike-tripdata.csv | 202501 | 50,611 |
| JC-202504-citibike-tripdata.csv | 202504 | 81,553 |
| JC-202507-citibike-tripdata.csv | 202507 | 107,726 |
| JC-202510-citibike-tripdata.csv | 202510 | 104,205 |


**Total rows: 344,095**

Column types used for loading (all station IDs are read as text on purpose):


| column_name | column_type |
|---|---|
| ride_id | VARCHAR |
| rideable_type | VARCHAR |
| started_at | TIMESTAMP |
| ended_at | TIMESTAMP |
| start_station_name | VARCHAR |
| start_station_id | VARCHAR |
| end_station_name | VARCHAR |
| end_station_id | VARCHAR |
| start_lat | DOUBLE |
| start_lng | DOUBLE |
| end_lat | DOUBLE |
| end_lng | DOUBLE |
| member_casual | VARCHAR |
| file_month | VARCHAR |


## 3. Timestamp format and time zone evidence

Raw text of `started_at` / `ended_at` checked against `YYYY-MM-DD HH:MM:SS(.fff)`:


| n | started_iso | ended_iso | am_pm_or_offset | example |
|---|---|---|---|---|
| 344,095 | 344,095 | 344,095 | 0 | 2025-04-17 13:19:09.286 |


Range of parsed timestamps:


| min_started | max_started | min_ended | max_ended |
|---|---|---|---|
| 2024-12-31 23:46:42.360000 | 2025-10-31 23:54:52.363000 | 2025-01-01 00:09:08.455000 | 2025-10-31 23:59:35.827000 |


Which month does each file hold? (rows whose start/end month differs from the month in the file name)


| file_month | started_other_month | ended_other_month |
|---|---|---|
| 202501 | 2 | 0 |
| 202504 | 1 | 0 |
| 202507 | 14 | 0 |
| 202510 | 16 | 0 |


Weekday trips by start hour (local-time check: commute peaks should be near 08 and 17-18):


| hour | weekday_trips |
|---|---|
| 0 | 1,869 |
| 1 | 898 |
| 2 | 516 |
| 3 | 299 |
| 4 | 989 |
| 5 | 3,211 |
| 6 | 9,119 |
| 7 | 17,803 |
| 8 | 22,340 |
| 9 | 11,250 |
| 10 | 8,495 |
| 11 | 9,389 |
| 12 | 10,860 |
| 13 | 11,040 |
| 14 | 11,880 |
| 15 | 14,664 |
| 16 | 18,905 |
| 17 | 29,853 |
| 18 | 27,940 |
| 19 | 19,068 |
| 20 | 12,919 |
| 21 | 9,254 |
| 22 | 6,685 |
| 23 | 4,313 |


## 4. Missing values by rideable_type


| rideable_type | rows | no_start_id | no_start_name | no_start_coord | no_end_id | no_end_name | no_end_coord | end_name_but_no_id | end_coord_but_no_station |
|---|---|---|---|---|---|---|---|---|---|
| ALL | 344,095 | 1 | 1 | 1 | 1,351 | 1,023 | 996 | 328 | 355 |
| classic_bike | 122,491 | 0 | 0 | 0 | 115 | 115 | 111 | 0 | 4 |
| electric_bike | 221,604 | 1 | 1 | 1 | 1,236 | 908 | 885 | 328 | 351 |


Other columns:


| no_ride_id | no_rideable_type | no_started_at | no_ended_at | no_member_casual |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 |


Category values:


| rideable_type | member_casual | rows |
|---|---|---|
| classic_bike | casual | 20,225 |
| classic_bike | member | 102,266 |
| electric_bike | casual | 55,500 |
| electric_bike | member | 166,104 |


## 5. Station ID problems


| rows_with_1_decimal_id | rows_with_trailing_underscore |
|---|---|
| 0 | 0 |


IDs that are not public stations after normalisation (excluded):


| id | name | appearances |
|---|---|---|


Same ID with several names (after normalisation; the most frequent name is kept):


| id | names |
|---|---|
| JC075 | ['Monmouth & 6th', 'Monmouth and 6th'] |


| raw_start_ids | normalised_start_ids | raw_end_ids | normalised_end_ids |
|---|---|---|---|
| 97 | 97 | 338 | 338 |


## 6. Durations


| end_before_start | zero | under_1min | under_2min | under_2min_same_station | over_3h | over_24h | min_sec | max_hours |
|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 13,668 | 803 | 540 | 117 | 60.1 | 25 |


Duration percentiles (minutes) by rider type:


| member_casual | p01 | p25 | median | mean | p75 | p99 |
|---|---|---|---|---|---|---|
| casual | 1.94 | 5.28 | 7.95 | 15.9 | 13.56 | 105.91 |
| member | 1.34 | 3.68 | 5.51 | 8.13 | 8.49 | 41.37 |


## 7. Duplicates


| duplicate_ride_ids | duplicate_rows_ignoring_ride_id |
|---|---|
| 0 | 0 |


## 8. Coordinates outside the expected area

Box used (our assumption): lat 40.55..40.95, lng -74.2..-73.7.


| start_outside | end_outside | any_zero_coord |
|---|---|---|
| 0 | 0 | 0 |


| side | id | name | lat | lng | rows |
|---|---|---|---|---|---|


Observed coordinate range of start points (helps tell which area a file covers):


| min_lat | max_lat | min_lng | max_lng |
|---|---|---|---|
| 40.7045 | 40.7545 | -74.0937 | -74.024 |


| start_id_family | rows | stations |
|---|---|---|
| JC (Jersey City) | 186,504 | 64 |
| HB (Hoboken) | 157,590 | 33 |
| missing | 1 | 0 |


| end_id_family | rows | stations |
|---|---|---|
| JC (Jersey City) | 184,256 | 64 |
| HB (Hoboken) | 157,252 | 33 |
| missing | 1,351 | 0 |
| numeric (NYC) | 1,236 | 241 |


## 9. Cleaning rules applied (counts are not exclusive; a row can hit several)


| started_outside_file_month | no_start_station | test_or_service_station | end_before_start | same_station_under_120s | over_180min | dropped_total | kept_trips | kept_but_no_end_station | kept_with_both_stations |
|---|---|---|---|---|---|---|---|---|---|
| 33 | 1 | 0 | 0 | 803 | 540 | 1,365 | 342,720 | 1,143 | 341,577 |


`kept_trips` feed departures and daily counts; `kept_with_both_stations` feed arrivals and routes.

## 10. Summary tables for the browser

Routes exclude round trips (start = end) and keep the top 100 per member_type x day_type.

| file | rows | CSV size | gzip size |
|---|---|---|---|
| summary/stations.csv | 337 | 15.3 KB | 5.8 KB |
| summary/station_hourly.csv | 83,404 | 2.4 MB | 321.2 KB |
| summary/daily.csv | 246 | 7.9 KB | 2.4 KB |
| summary/routes.csv | 400 | 13.9 KB | 3.0 KB |

Raw CSV input: 71.4 MB. Summary total: 2.4 MB.

Preview, top 5 routes per group:


| member_type | day_type | start_name | end_name | trips |
|---|---|---|---|---|
| casual | weekday | Hoboken Terminal - Hudson St & Hudson Pl | Hoboken Ave at Monmouth St | 531 |
| casual | weekday | Hoboken Ave at Monmouth St | Hoboken Terminal - Hudson St & Hudson Pl | 296 |
| casual | weekday | Hoboken Terminal - Hudson St & Hudson Pl | Southwest Park - Jackson St & Observer Hwy | 216 |
| casual | weekday | Fairmount Ave | Bergen Ave & Sip Ave | 198 |
| casual | weekday | McGinley Square | Bergen Ave & Sip Ave | 197 |
| casual | weekend | Hoboken Terminal - Hudson St & Hudson Pl | Hoboken Ave at Monmouth St | 190 |
| casual | weekend | Hoboken Ave at Monmouth St | Hoboken Terminal - Hudson St & Hudson Pl | 96 |
| casual | weekend | South Waterfront Walkway - Sinatra Dr & 1 St | 12 St & Sinatra Dr N | 71 |
| casual | weekend | Grove St PATH | Liberty Light Rail | 71 |
| casual | weekend | McGinley Square | Bergen Ave & Sip Ave | 71 |
| member | weekday | Grove St PATH | Marin Light Rail | 1,078 |
| member | weekday | McGinley Square | Bergen Ave & Sip Ave | 963 |
| member | weekday | Marin Light Rail | Grove St PATH | 931 |
| member | weekday | Liberty Light Rail | Grove St PATH | 922 |
| member | weekday | Grove St PATH | Liberty Light Rail | 891 |
| member | weekend | Grove St PATH | Marin Light Rail | 238 |
| member | weekend | McGinley Square | Bergen Ave & Sip Ave | 231 |
| member | weekend | Bergen Ave & Sip Ave | McGinley Square | 209 |
| member | weekend | Marin Light Rail | Grove St PATH | 202 |
| member | weekend | Hoboken Terminal - Hudson St & Hudson Pl | Hoboken Ave at Monmouth St | 190 |


Preview, largest net outflow / inflow stations (departures - arrivals, whole period):


| name | departures | arrivals | net_out |
|---|---|---|---|
| Oakland Ave | 2,663 | 2,188 | 475 |
| McGinley Square | 3,802 | 3,338 | 464 |
| Fairmount Ave | 1,709 | 1,437 | 272 |
| River St & 1 St | 6,846 | 6,595 | 251 |
| Glenwood Ave | 1,192 | 948 | 244 |


| name | departures | arrivals | net_out |
|---|---|---|---|
| Grove St PATH | 15,490 | 16,362 | -872 |
| Hoboken Terminal - River St & Hudson Pl | 7,062 | 7,530 | -468 |
| Hoboken Terminal - Hudson St & Hudson Pl | 8,866 | 9,244 | -378 |
| Vesey Pl & River Terrace | 0 | 175 | -175 |
| River St & Newark St | 6,595 | 6,688 | -93 |


Preview, member vs casual:


| member_type | trips | pct | median_min | pct_weekend |
|---|---|---|---|---|
| casual | 75,132 | 21.9 | 7.94 | 32.8 |
| member | 267,588 | 78.1 | 5.52 | 20.7 |


_Run time: 2.6 s._
