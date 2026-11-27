---
type: concept
title: SQL Introduction, Dialect and PostgreSQL Compatibility
description: DuckDB's SQL dialect basics — a quick SQL tour, identifier rules (double quotes and backticks new in 2.0, deduplication), case-insensitive identifiers that preserve case and preserve_identifier_case, differences from PostgreSQL (float division, implicit casts, regex operators, functional dependencies), SQL quirks, order preservation guarantees, and the PEG parser that became the default in DuckDB 2.0.
tags: [sql, dialect, postgresql, identifiers, case-sensitivity, order-preservation, peg-parser, quirks]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-ffab8640e9930fd28ab43593
    resource: repo://docs/2.0/sql/dialect/keywords_and_identifiers.md
  - id: openwiki-source-5412d365d54104d1400dd3e7
    resource: repo://docs/2.0/sql/dialect/order_preservation.md
  - id: openwiki-source-f3c6531d648ac7ea442eddf6
    resource: repo://docs/2.0/sql/dialect/overview.md
  - id: openwiki-source-0ea750e56483271ea0991022
    resource: repo://docs/2.0/sql/dialect/postgresql_compatibility.md
  - id: openwiki-source-45ceeac4f8547619529d1258
    resource: repo://docs/2.0/sql/dialect/sql_quirks.md
  - id: openwiki-source-f5da1a4393f189aed23e4dd8
    resource: repo://docs/2.0/sql/peg_parser.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# SQL Introduction, Dialect and PostgreSQL Compatibility

DuckDB's SQL dialect is based on **PostgreSQL** and tries to match its semantics closely; deviations exist where needed — e.g. **order preservation of inserts** by default, for interchangeability with data frame libraries. Conveniences beyond PostgreSQL are on [Friendly SQL](friendly-sql.md).

## A quick SQL tour

```sql
CREATE TABLE weather (city VARCHAR, temp_lo INTEGER, temp_hi INTEGER, prcp FLOAT, date DATE);
INSERT INTO weather VALUES ('San Francisco', 46, 50, 0.25, '1994-11-27');
SELECT city, (temp_hi + temp_lo) / 2 AS temp_avg, date FROM weather WHERE city = 'San Francisco' ORDER BY date;
SELECT city, max(temp_lo) FROM weather GROUP BY city HAVING max(temp_lo) < 40;
UPDATE weather SET temp_hi = temp_hi - 2, temp_lo = temp_lo - 2 WHERE date > '1994-11-28';
DELETE FROM weather WHERE city = 'Hayward';
```

Query clauses are detailed under [SELECT, FROM, WHERE …](../query-syntax/select-from-where.md), joins under [FROM Clause and Joins](../query-syntax/joins.md), and DML under [INSERT, UPDATE, DELETE, MERGE INTO](../statements/modifying-data.md).

## Identifiers

- Unquoted identifiers must not be reserved keywords (`CREATE TABLE select (i INTEGER)` fails; see `duckdb_keywords()`), must not start with a digit or special character (`SELECT 123 AS 1col` is invalid), and cannot contain whitespace.
- Quote with double quotes for anything else: `"SELECT"`, `" § 🦆 ¶ "`; escape `"` by doubling (`"IDENTIFIER ""X"""`).
- **New in 2.0:** backticks quote identifiers with the same rules (`` `a``b` `` is ``a`b``); backtick-quoted identifiers are never case-folded.
- Fully qualified column names are `database.schema.table.column`; leading parts may be omitted when unambiguous, otherwise resolution uses `schema` / `search_path` (see [ATTACH, DETACH, USE](../../connect/attach-and-multiple-databases.md)).
- Avoid the internal database names `system` and `temp` — a file `temp.db` gets that name, so attach with an alias: `ATTACH 'temp.db' AS temp2;`.
- **Duplicate column names** are renamed `name_1`, `name_2`, …:

```sql
SELECT * FROM (SELECT unnest({'a': 42, 'b': {'a': 88, 'b': 99}}, recursive := true));   -- a | a_1 | b
```

## Case sensitivity

- Keywords and function names are case-insensitive (`select COS(Pi())` = `SELECT cos(pi())`).
- **Identifiers are always case-insensitive — even quoted ones** (unlike PostgreSQL), using ASCII comparison (`col_A` = `col_a`, but `col_á` differs).
- DuckDB **preserves the case** as written: `CREATE TABLE tbl AS SELECT cos(pi()) AS CosineOfPi; SELECT cosineofpi FROM tbl;` returns a column named `CosineOfPi`.
- `MAP` keys are case-sensitive; `STRUCT` and `UNION` keys are case-insensitive. If the same identifier appears with different cases (e.g. in a `NATURAL JOIN`), one spelling is chosen arbitrarily.
- `preserve_identifier_case` (a `VARCHAR` since 2.0, previously `BOOLEAN`): `'preserve_case'` (default), `'lowercase'`, `'uppercase'`; `true`/`false` map to `'preserve_case'`/`'lowercase'`. It applies to statements parsed after the `SET`. Case-insensitive matching itself cannot be turned off.

```sql
SET preserve_identifier_case = 'lowercase';
CREATE TABLE MyTaBLe (x INTEGER);
SELECT table_name FROM duckdb_tables();   -- mytable
```

## Differences from PostgreSQL

| Topic | PostgreSQL | DuckDB |
| --- | --- | --- |
| `1.0 / 0.0`, `0.0 / 0.0`, `-1.0 / 0.0` | error | `Infinity`, `NaN`, `-Infinity` (IEEE 754) |
| `1 / 2` | `0` (integer division) | `0.5` (use `1 // 2` for `0`) |
| `SELECT true AS x UNION SELECT 2` | error | enforced cast → 1, 2 |
| `'1.1' = 1`, `true = 1` | error | `true` (implicit casts in equality) |
| `"MyTaBLe"` vs `MyTaBLe` | case-sensitive mismatch errors | works (case-insensitive, case-preserving) |
| `1 == 1` | error | `true` (`==` allowed, but not portable) |
| `VACUUM` | garbage collects and analyzes | only rebuilds statistics |
| `SELECT ARRAY['''']` | `{'}` | `['\'']` (escaping in nested values since 1.3.0) |
| `regexp_extract` / `regexp_substr` no match | `NULL` | empty string |
| `to_date` | supported | not supported — use `strptime` |
| `date_part` on infinite timestamps | | `NULL` (integer parts) |
| `pg_size_pretty(1024)` | `1024 bytes` | `1.0 KiB` (IEC units; alias of `format_bytes`) |
| Type names in `CREATE TABLE myschema.t (v mytype)` | resolved in search path only | also resolved in the table's schema |
| `SELECT j FROM tbl GROUP BY i` with `PRIMARY KEY (i)` | works (functional dependency) | Binder Error — add columns or use `GROUP BY ALL` / `any_value(j)` |

Regex operators match PostgreSQL by default in 2.0: `~` (partial, case-sensitive, = `regexp_matches`), `~*` (case-insensitive), `!~`, `!~*`. The deprecated `regex_match_operator_semantics = 'full'` restores the old full-match behavior.

## SQL quirks

| Expression | Result | Note |
| --- | --- | --- |
| `-2^2` | `4.0` | Unary minus binds tighter (PostgreSQL); use `-(2^2)` or `-pow(2, 2)` |
| `'t' = true`, `1 = ' 01 '` | `true` | PostgreSQL-compatible |
| `1 = true`, `1 = '1.1'` | `true` | Not PostgreSQL-compatible |
| `1 IN (0, NULL)` | `NULL` | `NULL` as unknown |
| `1 IN [0, NULL]` | `false` | List membership |
| `concat('abc', NULL)` | `abc` | while `'abc' \|\| NULL` is `NULL` |

- `sum`, `list` and `string_agg` on **empty groups return `NULL`** (not `0`, `[]`, `''`), per the SQL standard.
- One-based indexing almost everywhere (strings, lists, `row_number`), zero-based for JSON.
- `UINT8` is `UTINYINT` (bits) but `INT8` is `BIGINT` (bytes).
- `NaN = NaN` and `NaN > 3` are true (a total order for floats).
- `age(x)` is `current_date - x`.
- `list_extract`/`map_extract_value` return `NULL` for missing keys; `struct_extract` errors.
- Duplicate `SELECT` names: the first occurrence shadows others (`SELECT a FROM (SELECT *, 2 AS a FROM tbl)` returns 1).
- `USING SAMPLE` is written after `WHERE`/`GROUP BY` but **applied before** them.
- Bare identifiers as table-function arguments (`glob(no_such_file.csv)`) are **deprecated in 2.0**: converted with a warning by default; `table_function_identifier_conversion` = `DEFAULT`, `ENABLE_IMPLICIT_STRING` or `DISABLE_IMPLICIT_STRING`.

## Order preservation

Like data frame libraries, DuckDB keeps row order for many operations: `SELECT * FROM tbl WHERE x % 2 == 1` returns rows in table order.

- **Preserve order:** `COPY`, `FROM` with a single table, `LIMIT`, `OFFSET`, `SELECT`, `UNION ALL`, `WHERE`, window functions with an empty `OVER ()`, and CTEs/subqueries built only from these.
- **Do not guarantee order:** `FROM` with multiple tables/subqueries, `JOIN`, `UNION`, `USING SAMPLE`, whole-table aggregation input order, `GROUP BY`, `ORDER BY` (not necessarily stable), scalar subqueries.
- `row_number() OVER ()` (or `rowid` on tables) turns the original order into a column.
- CSV, JSON and Parquet readers preserve insertion order. `preserve_insertion_order` (default `true`) governs whether order is kept into sinks (`COPY ... TO`, `INSERT`, CTAS, client results); `SET preserve_insertion_order = false;` lets DuckDB reorder unordered results (saving memory). See [Troubleshooting: non-determinism](../../operations/troubleshooting.md).

## The PEG parser (default since 2.0)

DuckDB 2.0 replaced the PostgreSQL-derived parser with a **PEG-based parser** (introduced in 1.2 for autocomplete, experimental in 1.5; `enable_peg_parser()` is no longer needed or available). The dialect and the rest of the pipeline are unchanged; benefits are better suggestions (Tab cycling in the CLI), precise error locations, and a grammar extensions can extend. Packrat parsing costs a few milliseconds and some memory.

- `check_peg_parser('SELECT 42')` (from `autocomplete`) is a testing utility but does not reliably report failures in 2.0.0; use `SELECT json_serialize_sql('SELEC 42')::JSON->>'error' AS parse_error;` instead.
- **Legacy parser (new in 2.0):** `SET enable_legacy_parser = true;` autoloads `legacy_parser` as a bridge. It keeps 1.5 quirks: full-match `~`/`!~`, `2 * 3!` = 720, qualified built-ins like `main.struct_pack` in view SQL, `ORDER BY true` accepted, column constraints on `ALTER TABLE ... ADD COLUMN` rejected, `preserve_identifier_case = 'uppercase'` treated as `'preserve_case'`; newer syntax such as `INSTALL AND LOAD` is rejected.

Other 2.0 parser-related behavior changes are listed in [Installation, Migration and Footprint](../../operations/installation-migration-and-footprint.md).
