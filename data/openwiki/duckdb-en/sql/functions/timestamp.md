---
type: reference
title: TIMESTAMP and TIMESTAMPTZ Functions
description: Functions and operators for TIMESTAMP and TIMESTAMP WITH TIME ZONE — arithmetic, age/ago, date_diff vs date_sub, date_trunc, struct date_part, epoch/epoch_ms/epoch_us/epoch_ns, make_timestamp variants, strptime with format lists, time_bucket, range/generate_series, current_timestamp/now, ICU time-zone-aware functions, timezone() and AT TIME ZONE, string casts with offsets, calendars and DST behavior.
tags: [sql, functions, timestamp, timestamptz, time-zones, icu, time-bucket, at-time-zone]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-cfe9bc0df123bf4b7701b0fd
    resource: repo://docs/2.0/sql/functions/timestamp.md
  - id: openwiki-source-95e52355d4027127813280a1
    resource: repo://docs/2.0/sql/functions/timestamptz.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# TIMESTAMP and TIMESTAMPTZ Functions

Type semantics (naive vs aware, `TimeZone` and `Calendar` settings) are on [DATE, TIME, TIMESTAMP and INTERVAL Types](../data-types/date-and-time.md); date parts and format specifiers on [Date, Time, Interval, Date Part and Date Format Functions](date-and-time.md).

## `TIMESTAMP` operators

| Operator | Example | Result |
| --- | --- | --- |
| `+` interval | `TIMESTAMP '1992-03-22 01:02:03' + INTERVAL 5 DAY` | `1992-03-27 01:02:03` |
| `-` timestamps | `TIMESTAMP '1992-03-27' - TIMESTAMP '1992-03-22'` | `5 days` |
| `-` interval | `TIMESTAMP '1992-03-27 01:02:03' - INTERVAL 5 DAY` | `1992-03-22 01:02:03` |

Arithmetic on infinite values returns the same infinite value.

## `TIMESTAMP` functions

| Function | Example | Result |
| --- | --- | --- |
| `age(ts, ts)` | `age(TIMESTAMP '2001-04-10', TIMESTAMP '1992-09-20')` | `8 years 6 months 20 days` |
| `age(ts)` | subtract from `current_date` | |
| `ago(interval)` | `ago(INTERVAL 1 HOUR)` | current timestamp minus 1 hour |
| `date_diff(part, start, end)` | `date_diff('hour', TIMESTAMP '1992-09-30 23:59:59', TIMESTAMP '1992-10-01 01:58:00')` | `2` (boundaries) |
| `date_sub(part, start, end)` | same arguments | `1` (whole elapsed hours) |
| `date_part(part, ts)` / `extract(field FROM ts)` | `date_part('minute', TIMESTAMP '1992-09-20 20:38:40')` | `38` |
| `date_part([part, ...], ts)` | `date_part(['year', 'month', 'day'], TIMESTAMP '1992-09-20 20:38:40')` | `{year: 1992, month: 9, day: 20}` (constant list) |
| `date_trunc(part, ts)` | `date_trunc('hour', TIMESTAMP '1992-09-20 20:38:40')` | `1992-09-20 20:00:00` |
| `epoch(ts)` | `epoch('2022-11-07 08:43:04'::TIMESTAMP)` | `1667810584.0` (`DOUBLE`, keeps sub-seconds) |
| `epoch_ms`, `epoch_us`, `epoch_ns` | `epoch_ms(TIMESTAMP '2021-08-03 11:59:44.123456')` | `1627991984123` (`BIGINT`) |
| `make_timestamp(y, m, d, h, min, s)` | `make_timestamp(1992, 9, 20, 13, 34, 27.123456)` | `1992-09-20 13:34:27.123456` |
| `make_timestamp(µs)`, `make_timestamp_ms(ms)`, `make_timestamp_ns(ns)` | `make_timestamp_ms(1667810584123)` | `2022-11-07 08:43:04.123` |
| `strftime(ts, format)` | `strftime(timestamp '1992-01-01 20:38:40', '%a, %-d %B %Y - %I:%M:%S %p')` | `Wed, 1 January 1992 - 08:38:40 PM` |
| `strptime(text, format)` / `strptime(text, format-list)` | `strptime('4/15/2023 10:56:00', ['%d/%m/%Y %H:%M:%S', '%m/%d/%Y %H:%M:%S'])` | `2023-04-15 10:56:00` (first format that succeeds) |
| `try_strptime(text, format[-list])` | returns `NULL` instead of erroring | |
| `time_bucket(width, ts[, offset])` / `time_bucket(width, ts[, origin])` | grid anchored at `2000-01-01 00:00:00` (month+ widths) or `2000-01-03 00:00:00` | |
| `dayname`, `monthname`, `century`, `julian`, `last_day`, `greatest`, `least`, `isfinite`, `isinf` | as for dates | |
| `current_localtimestamp()` | current timestamp at transaction start | |

Part extractors (`year(ts)`, `hour(ts)`, …) exist for each [date part](date-and-time.md). Infinite timestamps return themselves (`greatest`) or `NULL` (`date_part`).

### Table functions

```sql
SELECT * FROM generate_series(TIMESTAMP '2024-01-01', TIMESTAMP '2024-01-02', INTERVAL 6 HOUR);  -- closed range
SELECT * FROM range(TIMESTAMP '2024-01-01', TIMESTAMP '2024-01-02', INTERVAL 6 HOUR);            -- half-open
```

Infinite values are not allowed as bounds.

## `TIMESTAMPTZ` functions

Time-zone support comes from the built-in **`icu` extension** (implemented natively since 2.0). Examples assume `TimeZone = 'America/Los_Angeles'` and the Gregorian calendar.

**Always available** (no binning or display involved): `current_timestamp`, `now()`, `get_current_timestamp()`, `transaction_timestamp()` (all = start of the current transaction), `to_timestamp(double)` (epoch seconds → `TIMESTAMPTZ`), `greatest`, `least`, `isfinite`, `isinf`, `timetz_byte_comparable(timetz)`.

**String casts:** without a time-zone extension, `TIMESTAMPTZ` values use offset notation and display in GMT:

```sql
SELECT '2022-10-08 13:13:34-07'::TIMESTAMPTZ;                       -- 2022-10-08 20:13:34+00
SELECT '2022-10-08 13:13:34 Europe/Amsterdam'::TIMESTAMPTZ::VARCHAR; -- with ICU: shown in the local zone
```

**ICU operators:** `+`/`-` with intervals and `-` between `TIMESTAMPTZ`s. Interval addition follows ICU `Calendar::add`: positive intervals increment fields from most to least significant, negative ones decrement from least to most — matching PostgreSQL (not some newer calendar RFCs).

**ICU functions** (zone-aware binning): `age`, `date_diff`, `date_sub`, `date_part` (incl. list form), `date_trunc`, `extract`, `epoch_us`, `epoch_ns`, `last_day`, `strftime`, `strptime` (returns `TIMESTAMPTZ` when `%Z` is used), and:

| Function | Description |
| --- | --- |
| `make_timestamptz(y, m, d, h, min, s[, zone])` | Build from parts in the current or given time zone |
| `make_timestamptz(µs)` | From microseconds since the epoch |
| `time_bucket(width, tstz[, offset \| origin \| timezone])` | Bucketing; origin defaults to `2000-01-01 00:00:00+00:00` (month+) / `2000-01-03 00:00:00+00:00`; the `timezone` variant bins in that zone |
| `generate_series(tstz, tstz, interval)` / `range(...)` | Closed / half-open timestamp ranges |

## Naive local timestamps and `timezone()`

ICU also provides functions that treat a plain `TIMESTAMP` as a **local** timestamp (encoding a zone's part values). Use them carefully: DST creates gaps and ambiguities; the struct form of `date_part` is often more reliable.

| Function | Description |
| --- | --- |
| `current_localtimestamp()` / `localtimestamp` | Local date and time as `TIMESTAMP` |
| `current_localtime()` / `localtime` | Local time as `TIME` |
| `timezone(text, timestamp)` | Interpret the naive timestamp in the zone → `TIMESTAMPTZ` |
| `timezone(text, timestamptz)` | Express the instant as local time in the zone → `TIMESTAMP` |

`AT TIME ZONE` is sugar for the two-argument `timezone`:

```sql
SELECT TIMESTAMP '2001-02-16 20:38:40' AT TIME ZONE 'America/Denver' AS ts;                  -- 2001-02-16 19:38:40-08
SELECT TIMESTAMP WITH TIME ZONE '2001-02-16 20:38:40-05' AT TIME ZONE 'America/Denver' AS ts; -- 2001-02-16 18:38:40
SELECT TIMESTAMP '2001-02-16 20:38:40-05' AT TIME ZONE '0200' AS ts;   -- Not implemented Error: Unknown TimeZone '0200'
```

Numeric time zones are not allowed in `AT TIME ZONE`.

## Calendars and DST

- Non-Gregorian calendars (`SET Calendar = 'japanese'`) change display and binning.
- When adding calendar intervals across a DST gap, DuckDB follows PostgreSQL and moves forward to the next valid time:

```sql
SET timezone = 'Europe/Amsterdam';
SELECT TIMESTAMPTZ '2025-03-29 02:30:00+01' + INTERVAL '1 day';   -- 2025-03-30 03:30:00+02
```

Prefer plain `TIMESTAMP` unless zone-aware display or binning is needed — it is simpler and faster (see the pitfalls on the [types page](../data-types/date-and-time.md)).
