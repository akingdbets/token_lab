---
type: reference
title: Data Types Overview, Casting, Literals, NULLs and Booleans
description: The list of DuckDB's general-purpose and nested data types with aliases, implicit vs explicit casting and the casting matrix, combination casting, lossy casts and overflows, struct/list casting rules, literal types (integer, string, E-strings, dollar quotes, B'…'/X'…' new in 2.0, underscores), NULL semantics with functions and aggregates, and BOOLEAN three-valued logic.
tags:
  - data-types
  - casting
  - typecasting
  - literals
  - boolean
  - implicit-cast
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-934e25f945b4f988230cb6c5
    resource: repo://docs/2.0/sql/data_types/boolean.md
  - id: openwiki-source-54e5d46598c57ce4e8fbe28a
    resource: repo://docs/2.0/sql/data_types/literal_types.md
  - id: openwiki-source-69fec0b3cc9fd319cf0b16b0
    resource: repo://docs/2.0/sql/data_types/nulls.md
  - id: openwiki-source-87e42d85612a8877220a3625
    resource: repo://docs/2.0/sql/data_types/overview.md
  - id: openwiki-source-87c6eebe907ef4e99084f0dc
    resource: repo://docs/2.0/sql/data_types/typecasting.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Data Types Overview, Casting, Literals, NULLs and Booleans

Details of individual types: [Numeric, Text, BLOB and BITSTRING](numeric-text-and-binary.md), [DATE, TIME, TIMESTAMP and INTERVAL](date-and-time.md), [Nested Types](nested-types.md), [VARIANT and GEOMETRY](variant-and-geometry.md). Cast syntax (`CAST`, `::`, `TRY_CAST`) is on [Expressions](../expressions.md).

## General-purpose types

Aliases are not SQL standard and may not work in other engines.

| Name | Aliases | Description |
| --- | --- | --- |
| `BIGINT` | `INT8`, `LONG` | Signed 8-byte integer |
| `BIT` | `BITSTRING` | String of 1s and 0s |
| `BLOB` | `BYTEA`, `BINARY`, `VARBINARY` | Variable-length binary |
| `BIGNUM` | | Variable-length integer |
| `BOOLEAN` | `BOOL`, `LOGICAL` | `true` / `false` |
| `DATE` | | Calendar date |
| `DECIMAL(prec, scale)` | `NUMERIC(prec, scale)` | Fixed precision; defaults `prec = 18`, `scale = 3` |
| `DOUBLE` | `FLOAT8` | 8-byte float |
| `FLOAT` | `FLOAT4`, `REAL` | 4-byte float |
| `GEOMETRY` | | Geospatial entity |
| `HUGEINT` | | Signed 16-byte integer |
| `INTEGER` | `INT4`, `INT`, `SIGNED` | Signed 4-byte integer |
| `INTERVAL` | | Date/time delta |
| `JSON` | | JSON (via the `json` extension) |
| `SMALLINT` | `INT2`, `SHORT` | Signed 2-byte integer |
| `TIME` | | Time of day |
| `TIMESTAMP WITH TIME ZONE` | `TIMESTAMPTZ` | Timestamp using the current time zone |
| `TIMESTAMP` | `DATETIME` | Date and time |
| `TINYINT` | `INT1` | Signed 1-byte integer |
| `UBIGINT`, `UHUGEINT`, `UINTEGER`, `USMALLINT`, `UTINYINT` | | Unsigned integers |
| `UUID` | | UUID |
| `VARCHAR` | `CHAR`, `BPCHAR`, `TEXT`, `STRING` | Variable-length string |

**Nested types:** `ARRAY` (`INTEGER[3]`), `LIST` (`INTEGER[]`), `MAP` (`MAP(INTEGER, VARCHAR)`), `STRUCT` (`STRUCT(i INTEGER, j VARCHAR)`), `TUPLE` (`TUPLE(INTEGER, VARCHAR)`), `UNION`, and `VARIANT`. They nest to any depth:

```sql
SELECT {'birds': ['duck', 'goose', 'heron'], 'aliens': NULL, 'amphibians': ['frog', 'toad']};
SELECT {'test': [MAP([1, 5], [42.1, 45]), MAP([1, 5], [42.1, 45])]};
SELECT [union_value(num := 2), union_value(str := 'ABC')::UNION(str VARCHAR, num INTEGER)];
```

`MAP` keys are case-sensitive; `STRUCT` and `UNION` keys are case-insensitive. Updating nested values is a delete + insert, which can trigger unexpected constraint violations with ART indexes. Type choice strongly affects performance (see [Schema Design](../../performance/schema-indexes-and-joins.md)).

## Casting

**Explicit:** `CAST(col AS VARCHAR)` or `col::VARCHAR`. **Implicit:** added by the system only where the cast cannot fail — e.g. `sin(1)` casts `INTEGER` → `DOUBLE`, but `DOUBLE` → `INTEGER` is never implicit. Check with `can_cast_implicitly`.

**Combination casting** picks a common parent type for comparisons, set operations (`UNION`/`EXCEPT`/`INTERSECT`) and nested constructors (`list_value`, `[...]`, `MAP`); it can be more lenient — `list_value(1::INT64, 1::UINT64)` is `INT128[]`.

Casting matrix highlights (I = implicit, E = explicit only):

| From → To | Rule |
| --- | --- |
| Integers → wider integers, `FLOAT`, `DOUBLE`, `DECIMAL` | I (narrowing is E) |
| Unsigned → wider signed/unsigned | I |
| `FLOAT` → `DOUBLE` | I; to integers/`DECIMAL` E |
| `DECIMAL(18,3)` → `FLOAT`/`DOUBLE` | I (may lose precision) |
| Anything → `VARCHAR` | E (universal target) |
| `VARCHAR` → anything | E (may fail when parsing) |
| `BLOB` ↔ `BIT`/`UUID` | E |
| `DATE` → `TIMESTAMP`, `TIMESTAMPTZ` | I |
| `TIMESTAMP` → `TIMESTAMPTZ` | I; to `DATE`/`TIME`/`TIMETZ` E |
| `TIME` → `TIMETZ` | E |

Implicit casts are lossless (safe to reverse) except wide integers/`DECIMAL` → `FLOAT`/`DOUBLE`. `NULL` casts to any type. Since 0.10.0, values are **no longer implicitly cast to `VARCHAR`** during function binding (the deprecated `old_implicit_casting` restores it).

**Lossy casts** round: `CAST(3.5 AS INTEGER)` → 4, `CAST(-1.7 AS INTEGER)` → −2 (see rounding rules on the numeric page). **Overflows** error:

```sql
SELECT CAST(999 AS TINYINT);
-- Conversion Error: Type INT32 with value 999 can't be cast because the value is out of range for the destination type INT8
```

Use `TRY_CAST` to get `NULL` instead. Casting to `VARCHAR` is lossless and reversible: `SELECT CAST(CAST([1, 2, 3] AS VARCHAR) AS INTEGER[]);`.

**Nested casts:** lists cast element-wise (`CAST([1, 2, 3] AS VARCHAR[])`); arrays follow list rules and implicitly cast to lists. Structs cast if they share **at least one field**: missing target fields become `NULL`, source-only fields are dropped, and fields are matched by name in any order. In combination casting, struct fields become the superset (recursively):

```sql
SELECT CAST({'a': 42} AS STRUCT(a VARCHAR, b VARCHAR));
SELECT CAST({'a': 42, 'b': 84} AS STRUCT(b VARCHAR, a VARCHAR));
SELECT [{'a': 42}, {'b': 84}];
```

## Literal types

Since 0.10.0, literals have their own types with special binding rules.

- **`NULL`** converts implicitly to any type.
- **Integer literals** (`INTEGER_LITERAL`) convert implicitly to any integer type the value fits. Hex/binary literals are not supported directly, but strings cast: `'0xFF'::INT = 255`, `'0b101'::INT = 5`.
- **Other numeric literals:** `1.5`, `.50`, `2.`, E notation `1e2`, `6.02214e23`, `1e-10`.
- **Underscores** as separators in integer, decimal, hex and binary notation — not first/last, not doubled, not next to `.` or the exponent: `100_000_000`, `'0xFF_FF'::INTEGER`, `1_2.1_2E0_1` (121.2).
- **String literals** use single quotes (double quotes are identifiers) and are `STRING_LITERAL`s, which implicitly convert to **any** type: `WHERE d > '1992-01-01'` works for a `DATE`, but `d > '1992-01-01'::VARCHAR` fails (`Cannot compare values of type DATE and type VARCHAR`).
- Adjacent single-quoted literals separated by whitespace **containing a newline** are concatenated (`'Hello'` newline `' '` newline `'World'`); without a newline it is a syntax error.
- Escape `'` as `''`. `E'...'` enables `\b`, `\f`, `\n`, `\r`, `\t`: `SELECT e'Hello\nworld';`.
- **Dollar quoting:** `$$The price is $9.95$$`, or tagged `$tag$ ... $tag$` to embed `$$`.
- **Bit/hex string literals (new in 2.0):** `B'0101'` is a `BITSTRING` (only 0/1), `X'CAFE'` a `BLOB` (even hex digits). Earlier versions parsed them as `VARCHAR` `'b0101'`/`'xCAFE'`.

## NULL values

`NULL` means "unknown" and can go in any column without `NOT NULL`.

- **Any comparison with `NULL` is `NULL`**, including `NULL = NULL`. Use `IS NOT DISTINCT FROM` for NULL-safe equality and `IS [NOT] NULL` to test.
- Functions **usually** return `NULL` on `NULL` input (`cos(NULL)`). `coalesce(...)` returns the first non-`NULL` argument; `ifnull(a, b)` is the two-argument form.
- Most aggregates ignore `NULL`s (`min`, `max`, `sum`, …); `first`, `last`, `list` and `array_agg` do not — use `list(x) FILTER (WHERE x IS NOT NULL)`.
- `IN` / `NOT IN` with `NULL`s behaves specially (see [Expressions](../expressions.md)).

```sql
SELECT NULL = NULL;                       -- NULL
SELECT NULL IS NOT DISTINCT FROM NULL;    -- true
SELECT coalesce(NULL, NULL, 1);           -- 1
SELECT ifnull(NULL, 'default_string');    -- default_string
```

## BOOLEAN

`BOOLEAN` (`BOOL`) holds `true`, `false`, or `NULL` ("unknown"). Rows where a `WHERE` predicate is `false` **or** `NULL` are filtered out: with `i` values 5, 15, `NULL`, `WHERE i > 10` returns only 15.

| `X` | `X AND true` | `X AND false` | `X AND NULL` | `X OR true` | `X OR false` | `X OR NULL` |
| --- | --- | --- | --- | --- | --- | --- |
| true | true | false | NULL | true | true | true |
| false | false | false | false | true | false | NULL |
| NULL | NULL | false | NULL | true | NULL | NULL |
