---
type: reference
title: Date, Time, Interval, Date Part and Date Format Functions
description: Functions and operators for DATE, TIME and INTERVAL values — date arithmetic, date_add/date_diff/date_sub/date_trunc, time_bucket, make_date, last_day, dayname, the date part specifiers and their synonyms for date_part/extract, interval constructors (to_days, to_months, ...), and strftime/strptime/try_strptime format specifiers including CSV dateformat options.
tags: [sql, functions, date, time, interval, date-part, strftime, strptime]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-c61ded2427f26527c24f6de4
    resource: repo://docs/2.0/sql/functions/date.md
  - id: openwiki-source-67afa66d9d4a91b9a9b31382
    resource: repo://docs/2.0/sql/functions/dateformat.md
  - id: openwiki-source-764204ddb242f9df70b01f8b
    resource: repo://docs/2.0/sql/functions/datepart.md
  - id: openwiki-source-aad528b7a27d8aa2b5a7bac7
    resource: repo://docs/2.0/sql/functions/interval.md
  - id: openwiki-source-d2f7c9b29335df8760456317
    resource: repo://docs/2.0/sql/functions/time.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Date, Time, Interval, Date Part and Date Format Functions

Type semantics are on [DATE, TIME, TIMESTAMP and INTERVAL Types](../data-types/date-and-time.md); timestamp-specific and time-zone functions are on [TIMESTAMP and TIMESTAMPTZ Functions](timestamp.md). Dates can also be passed to timestamp functions through type promotion.

## Date operators

| Operator | Example | Result |
| --- | --- | --- |
| `+` days (integer) | `DATE '1992-03-22' + 5` | `1992-03-27` |
| `+` interval | `DATE '1992-03-22' + INTERVAL 5 DAY` | `1992-03-27 00:00:00` (a timestamp) |
| `+` variable interval | `DATE '1992-03-22' + INTERVAL (d.days) DAY` | |
| `-` dates | `DATE '1992-03-27' - DATE '1992-03-22'` | `5` (integer days) |
| `-` interval | `DATE '1992-03-27' - INTERVAL 5 DAY` | `1992-03-22 00:00:00` |

Adding to or subtracting from infinite dates returns the same infinite value.

## Date functions

| Function | Example | Result |
| --- | --- | --- |
| `date_add(date, interval)` | `date_add(DATE '1992-09-15', INTERVAL 2 MONTH)` | `1992-11-15 00:00:00` |
| `date_diff(part, start, end)` | `date_diff('month', DATE '1992-09-15', DATE '1992-11-14')` | `2` (part boundaries crossed) |
| `date_sub(part, start, end)` | `date_sub('month', DATE '1992-09-15', DATE '1992-11-14')` | `1` (whole elapsed parts) |
| `date_part(part, date)` / `extract(part FROM date)` | `date_part('year', DATE '1992-09-20')` | `1992` |
| `date_trunc(part, date)` | `date_trunc('month', DATE '1992-03-07')` | `1992-03-01 00:00:00` |
| `dayname(date)` / `monthname(date)` | `dayname(DATE '1992-09-20')` | `Sunday` |
| `days_in_month(date)` | `days_in_month(DATE '1992-02-15')` | `29` |
| `greatest(d1, d2)` / `least(d1, d2)` | `greatest(DATE '1992-09-20', DATE '1992-03-07')` | `1992-09-20` |
| `isfinite(date)` / `isinf(date)` | `isinf(DATE '-infinity')` | `true` |
| `julian(date)` | `julian(DATE '1992-09-20')` | `2448886.0` |
| `last_day(date)` | `last_day(DATE '1992-09-20')` | `1992-09-30` |
| `make_date(year, month, day)` | `make_date(1992, 9, 20)` | `1992-09-20` |
| `strftime(date, format)` | `strftime(DATE '1992-01-01', '%a, %-d %B %Y')` | `Wed, 1 January 1992` |
| `time_bucket(width, date[, offset])` | `time_bucket(INTERVAL '2 months', DATE '1992-04-20', INTERVAL '1 month')` | `1992-04-01` |
| `time_bucket(width, date[, origin])` | `time_bucket(INTERVAL '2 weeks', DATE '1992-04-20', DATE '1992-04-01')` | `1992-04-15` |
| `today()` | current date at transaction start, local time zone | |

`date_diff` counts boundaries (inclusive of the larger, exclusive of the smaller value); `date_sub` gives the signed length truncated to whole `part`s. `time_bucket` grids are anchored at `2000-01-01` (plus offset) for month-or-coarser widths and at `2000-01-03` (a Monday) otherwise, unless an `origin` is given. Functions applied to infinite dates return the infinite value (e.g. `greatest`) or `NULL` when parts are needed (e.g. `date_part`).

## Time functions

```sql
SELECT TIME '01:02:03' + INTERVAL 5 HOUR;   -- 06:02:03
```

| Function | Description |
| --- | --- |
| `current_localtime()` | Current local time (transaction start) as `TIME` |
| `get_current_time()` | Current time (transaction start) |
| `date_diff(part, start, end)`, `date_sub(part, start, end)` | As for dates |
| `date_part(part, time)` / `extract(part FROM time)` | Subfield |
| `make_time(bigint, bigint, double)` | Time from hour, minute, second |

Only `epoch`, `hours`, `minutes`, `seconds`, `milliseconds` and `microseconds` are defined for times.

## Interval functions

```sql
SELECT INTERVAL 1 HOUR + INTERVAL 5 HOUR;                           -- 6 hours
SELECT TIMESTAMP '1992-03-22 01:02:03' + INTERVAL 5 DAY;            -- 1992-03-27 01:02:03
```

| Function | Description |
| --- | --- |
| `date_part(part, interval)` (`datepart`, `extract`) | Component (see the interval rules on the types page) |
| `epoch(interval)` | Total seconds as `DOUBLE` |
| `normalized_interval(interval)` | Carry overflowing units into larger units |
| `to_microseconds`, `to_milliseconds`, `to_seconds`, `to_minutes`, `to_hours`, `to_days`, `to_weeks`, `to_months`, `to_quarters`, `to_years`, `to_decades`, `to_centuries`, `to_millennia` | Construct an interval from an integer |

## Date part specifiers

Used by `date_part`, `date_trunc`, `date_diff`, `extract`, etc. Examples are for `2021-08-03 11:59:44.123456`. All parts are integers except `julian` and `epoch` (`DOUBLE`); infinite timestamps yield `NULL`.

**Usable in date parts and intervals:**

| Specifier | Synonyms | Example |
| --- | --- | --- |
| `century` | `cent`, `centuries`, `c` | `21` |
| `decade` | `dec`, `decades`, `decs` | `202` |
| `millennium` | `mil`, `millenniums`, `millennia`, `mils`, `millenium` | `3` |
| `year` | `yr`, `y`, `years`, `yrs` | `2021` |
| `quarter` | `quarters` | `3` |
| `month` | `mon`, `months`, `mons` | `8` |
| `day` | `days`, `d`, `dayofmonth` | `3` |
| `hour` | `hr`, `hours`, `hrs`, `h` | `11` |
| `minute` | `min`, `minutes`, `mins`, `m` | `59` |
| `second` | `sec`, `seconds`, `secs`, `s` | `44` |
| `milliseconds` | `millisecond`, `ms`, `msec`, `msecs`, `msecond`, `mseconds` | `44123` (sub-minute) |
| `microseconds` | `microsecond`, `us`, `usec`, `usecs`, `usecond`, `useconds` | `44123456` (sub-minute) |

**Date parts only:** `dayofweek` (`weekday`, `dow`; Sunday = 0) `2`; `dayofyear` (`doy`) `215`; `epoch` `1627991984.123456`; `era` `1`; `isodow` (Monday = 1) `2`; `isoyear` `2021`; `julian` `2459430.4998162435`; `week` (`weeks`, `w`) `31`; `yearweek` (`YYYYWW`) `202131`; `timezone`, `timezone_hour`, `timezone_minute` (all `0` unless a time-zone extension like ICU supports `TIMESTAMPTZ`).

Dedicated part functions exist for each: `century`, `day`, `dayofmonth`, `dayofweek`, `dayofyear`, `decade`, `epoch`, `era`, `hour`, `isodow`, `isoyear`, `julian`, `microsecond`, `millennium`, `millisecond`, `minute`, `month`, `quarter`, `second`, `timezone`, `timezone_hour`, `timezone_minute`, `week`, `weekday`, `weekofyear`, `year`, `yearweek`. The list form `date_part(['year', 'month', 'day'], ts)` extracts several parts in one call.

## Date format functions: `strftime` and `strptime`

```sql
SELECT strftime(DATE '1992-03-02', '%d/%m/%Y');                                      -- 02/03/1992
SELECT strftime(TIMESTAMP '1992-03-02 20:32:45', '%A, %-d %B %Y - %I:%M:%S %p');   -- Monday, 2 March 1992 - 08:32:45 PM
SELECT strptime('02/03/1992', '%d/%m/%Y');                                           -- 1992-03-02 00:00:00
SELECT strptime('02/50/1992', '%d/%m/%Y') AS x;     -- Invalid Input Error: ... Month out of range
SELECT try_strptime('02/50/1992', '%d/%m/%Y') AS x; -- NULL
```

The same formats apply when parsing CSV files:

```sql
COPY dates FROM 'test.csv' (DATEFORMAT '%d/%m/%Y', TIMESTAMPFORMAT '%A, %-d %B %Y - %I:%M:%S %p');
SELECT * FROM read_csv('test.csv', dateformat = '%m/%d/%Y', timestampformat = '%A, %-d %B %Y - %I:%M:%S %p');
```

| Specifier | Meaning | Example |
| --- | --- | --- |
| `%a` / `%A` | Abbreviated / full weekday | `Sun` / `Sunday` |
| `%b` / `%B` | Abbreviated / full month | `Jan` / `January` |
| `%c`, `%x`, `%X` | ISO date-time / date / time | `1992-03-02 10:30:20` |
| `%d` / `%-d` | Day of month, zero-padded / not | `01` / `1` |
| `%H` / `%-H` | Hour (24h) | `00`…`23` |
| `%I` / `%-I` | Hour (12h) | `01`…`12` |
| `%p` | AM/PM | `PM` |
| `%M` / `%-M` | Minute | `00`…`59` |
| `%S` / `%-S` | Second | `00`…`59` |
| `%g`, `%f`, `%n` | Milli-, micro-, nanoseconds, zero-padded | `000`, `000000`, `000000000` |
| `%j` / `%-j` | Day of year | `001`…`366` |
| `%m` / `%-m` | Month | `01`…`12` |
| `%y` / `%-y` | Two-digit year (00–68 → 2000–2068, 69–99 → 1969–1999) | `92` |
| `%Y` | Four-digit year | `2019` |
| `%G`, `%V`, `%u` | ISO year, ISO week (week 01 contains Jan 4; use with `%G`, not `%Y`), ISO weekday (Monday = 1) | |
| `%U` / `%W` | Week number starting Sunday / Monday (week 00 possible; not ISO) | |
| `%w` | Weekday (Sunday = 0) | |
| `%z` / `%Z` | UTC offset (`±HH:MM`, `±HHMM`, `±HH`) / time zone name | `-0700` / `Europe/Amsterdam` |
| `%%` | Literal `%` | |
