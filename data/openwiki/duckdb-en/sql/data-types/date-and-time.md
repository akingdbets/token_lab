---
type: reference
title: DATE, TIME, TIMESTAMP and INTERVAL Types
description: DuckDB's temporal types — DATE, TIME/TIMETZ/TIME_NS, TIMESTAMP variants (TIMESTAMP_S/MS/NS, TIMESTAMPTZ, TIMESTAMPTZ_NS new in 2.0), special values (epoch, infinity), naive vs time-zone-aware semantics and conversions, TimeZone and Calendar settings via the icu extension, INTERVAL components, arithmetic and comparison rules, and common timestamp pitfalls.
tags: [data-types, date, time, timestamp, timestamptz, interval, time-zones, icu]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-3bf5841bfb7f39a6b8bd90a7
    resource: repo://docs/2.0/guides/sql_features/timestamps.md
  - id: openwiki-source-90f15d41fc8b2b08e9c1d1ab
    resource: repo://docs/2.0/sql/data_types/date.md
  - id: openwiki-source-e2c1e8a9a0ff971a53aae9bd
    resource: repo://docs/2.0/sql/data_types/interval.md
  - id: openwiki-source-a70baa6c4b6cae3142de54a7
    resource: repo://docs/2.0/sql/data_types/timestamp.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# DATE, TIME, TIMESTAMP and INTERVAL Types

Temporal values are written as type keyword plus ISO 8601 string. Functions on these types are on [Date, Time, Interval, Date Part and Date Format Functions](../functions/date-and-time.md) and [TIMESTAMP and TIMESTAMPTZ Functions](../functions/timestamp.md).

## `DATE`

A calendar date (year, month, day), always counted in the **Gregorian calendar**, even before it was in use. Input format `YYYY-MM-DD`:

```sql
SELECT DATE '1992-09-20';
```

## `TIME`, `TIMETZ`, `TIME_NS`

| Name | Aliases | Description |
| --- | --- | --- |
| `TIME` | `TIME WITHOUT TIME ZONE` | Time of day (microseconds) |
| `TIMETZ` | `TIME WITH TIME ZONE` | Time of day with UTC offset |
| `TIME_NS` | | Time of day, nanosecond precision (also read from Parquet `TIME` with unit `NANOS`) |

Format `hh:mm:ss[.zzzzzz[zzz]][+-TT[:tt]]`:

```sql
SELECT TIME '1992-09-20 11:30:00.123456';                 -- 11:30:00.123456
SELECT TIMETZ '1992-09-20 11:30:00.123456-02:00';         -- 13:30:00.123456+00
SELECT '15:30:00.123456789'::TIME_NS;
```

Use `TIME` only when the date part can be disregarded; most applications should use timestamps.

## Timestamp types

Format `YYYY-MM-DD hh:mm:ss[.zzzzzzzzz][+-TT[:tt]]`; digits beyond the precision are ignored.

| Name | Aliases | Description |
| --- | --- | --- |
| `TIMESTAMP_NS` | | Naive, nanoseconds |
| `TIMESTAMP` | `DATETIME`, `TIMESTAMP WITHOUT TIME ZONE` | Naive, microseconds |
| `TIMESTAMP_MS` | | Naive, milliseconds |
| `TIMESTAMP_S` | | Naive, seconds |
| `TIMESTAMPTZ` | `TIMESTAMP WITH TIME ZONE` | Time-zone aware, microseconds |
| `TIMESTAMPTZ_NS` | | Time-zone aware, nanoseconds — **new in DuckDB 2.0** (e.g. Parquet `isAdjustedToUTC=true` nanosecond columns) |

```sql
SELECT TIMESTAMP_NS '1992-09-20 11:30:00.123456789';   -- 1992-09-20 11:30:00.123456789
SELECT TIMESTAMP '1992-09-20 11:30:00.123456789';      -- 1992-09-20 11:30:00.123456
SELECT TIMESTAMP_MS '1992-09-20 11:30:00.123456789';   -- 1992-09-20 11:30:00.123
SELECT TIMESTAMPTZ '1992-09-20 12:30:00.123456789+01:00';   -- 1992-09-20 11:30:00.123456+00
SELECT TIMESTAMPTZ_NS '1992-09-20 11:30:00.123456789+00';   -- keeps nanoseconds
```

### Naive vs time-zone aware

Despite its name, `TIMESTAMP WITH TIME ZONE` **stores no time zone**: it stores an `INT64` of non-leap microseconds since `1970-01-01 00:00:00+00`, i.e. an **instant**. "Aware" means binning, arithmetic and formatting use the configured time zone. `TIMESTAMP` stores the same integer, but follows plain UTC rules without offsets; it usually represents a *local* observation in an unspecified zone.

Conversion rules:

- Strings without offsets ↔ `WITHOUT TIME ZONE`: straightforward.
- Strings with offsets or zone names → `WITH TIME ZONE`: unambiguous (zone names need the `icu` extension). Strings without offsets → `WITH TIME ZONE` are interpreted in the **configured time zone**.
- Offsets given to a `WITHOUT TIME ZONE` type are ignored; **since DuckDB 2.0 time zone names are also ignored** (earlier, names other than `UTC` raised an error).
- Casts between `WITH` and `WITHOUT TIME ZONE` use the configured time zone; use `timezone()` for another:

```sql
SELECT
    timezone('America/Denver', TIMESTAMP '2001-02-16 20:38:40') AS aware1,
    timezone('America/Denver', TIMESTAMPTZ '2001-02-16 04:38:40') AS naive1;
```

### Special values

| Input | Meaning |
| --- | --- |
| `epoch` | `1970-01-01` / `1970-01-01 00:00:00[+00]` (converted on read) |
| `infinity` | Later than all other values (kept as is) |
| `-infinity` | Earlier than all other values |

```sql
SELECT '-infinity'::DATE AS negative, 'epoch'::DATE AS epoch, 'infinity'::TIMESTAMP AS positive;
```

### Time zones and calendars

Binning `TIMESTAMPTZ` (into years, days, hours …) depends on the **time zone** (and its daylight-saving rules) and the **calendar**. Both are implemented by the `icu` extension using IANA data; **since DuckDB 2.0 it no longer depends on the ICU library** — it implements time zones, calendars and collations natively, supports DST past 2037, and is faster. It is bundled and autoloaded in the CLI, Python, R, JDBC and ODBC clients; otherwise `INSTALL icu; LOAD icu;`.

```sql
SET TimeZone = 'America/Los_Angeles';          -- SESSION scope by default in 2.0
SELECT name, abbrev, utc_offset FROM pg_timezone_names() ORDER BY name;
SET Calendar = 'japanese';                     -- era reports the Japanese imperial era
SELECT name FROM icu_calendar_names() ORDER BY 1;
SELECT * FROM duckdb_settings() WHERE name = 'TimeZone';
```

If binning behaves unexpectedly, check the `TimeZone` and `Calendar` settings (defaults come from the system locale).

## `INTERVAL`

An interval is a period stored as three independent components — **months, days, microseconds** — because a month has no fixed number of days and a day (with DST) no fixed number of microseconds. Other units are converted into the next smaller basis unit.

```sql
SELECT
    INTERVAL 1 YEAR,                  -- 12 months
    INTERVAL (random() * 10) YEAR,    -- parentheses for expressions
    INTERVAL '1 month 1 day',         -- string for multiple units
    '16 months'::INTERVAL,
    '48:00:00'::INTERVAL;             -- 48 hours in microseconds
SELECT DATE '2000-01-01' + INTERVAL (i) MONTH FROM range(12) t(i);   -- first of each month
```

> Decimal amounts with unit keywords are **truncated** (except `SECONDS`/`MILLISECONDS`): `INTERVAL '1.5' YEARS` is 12 months. Use `INTERVAL '1.5 years'` or `INTERVAL 18 MONTHS`.

`datepart` splits months into `year` (`#months // 12`) and `month` (`#months % 12`), keeps `day`, and splits microseconds into `hour`, `minute` and `microsecond` (not seconds); `century`, `decade`, `quarter`, `second` and `millisecond` are also available:

```sql
SELECT datepart('decade', INTERVAL 12 YEARS),             -- 1
       datepart('second', INTERVAL 1_234 MILLISECONDS),   -- 1
       datepart('microsecond', INTERVAL 1_234 MILLISECONDS); -- 1_234_000
```

### Arithmetic

```sql
SELECT
    DATE '2000-01-01' + INTERVAL 1 YEAR,                          -- returns a TIMESTAMP
    TIMESTAMP '2000-01-01 01:33:30' - INTERVAL '1 month 13 hours',
    TIME '02:00:00' - INTERVAL '3 days 23 hours';                -- wraps to 03:00:00
SELECT TIMESTAMP '2000-02-06 12:00:00' - TIMESTAMP '2000-01-01 11:00:00';   -- 36 days 01:00:00
```

- `DATE + INTERVAL` returns a `TIMESTAMP`.
- `TIMESTAMP - TIMESTAMP` gives an interval with only days and microseconds, so `TIMESTAMP '2000-02-01' + (TIMESTAMP '2000-02-01' - TIMESTAMP '2000-01-01')` is `2000-03-03`, not `2000-03-01`.
- `DATE - DATE` returns an **integer** number of days.
- Extracting a part of a difference differs from `datediff` (boundary counting): `datediff('day', TIMESTAMP '2020-01-01 01:00:00', TIMESTAMP '2020-01-02 00:00:00')` is 1, while `datepart('day', ...difference...)` is 0.

### Comparison

For equality and ordering only, days count as 24 hours and months as 30 days, so `INTERVAL 30 DAYS = INTERVAL 1 MONTH`, yet adding them to `DATE '2020-01-01'` gives different dates; ordering is not always preserved after addition.

## Pitfalls with timestamps

- **`DATE` → `TIMESTAMPTZ` promotion** uses midnight *in the current time zone*, so `FROM times WHERE t <= '2025-08-30'` on a `TIMESTAMPTZ` column returns different rows after `SET timezone = 'HST'` or `'America/New_York'`. Unless you need time-zone display or binning, **use plain `TIMESTAMP`** — it avoids such surprises and is faster.
- Zone-aware binning is more expensive than plain timestamp arithmetic; for repeated binning, precompute a calendar table using the list form `date_part(['year', 'month', 'day', 'hour'], ts)`, which computes all parts in one conversion.
- `x BETWEEN begin AND end` is **closed-closed** (`begin <= x AND x <= end`); temporal analytics usually wants half-open intervals, so write `begin <= x AND x < end` explicitly.
