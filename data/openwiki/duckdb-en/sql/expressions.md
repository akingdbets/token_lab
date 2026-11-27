---
type: "Reference"
title: "Expressions: CASE, CAST, TRY, Operators, Subqueries and Collations"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-50881ea41728bb5c33338b45
    resource: repo://docs/2.0/sql/expressions/case.md
  - id: openwiki-source-a1da4530b48a28e3981fa7b7
    resource: repo://docs/2.0/sql/expressions/cast.md
  - id: openwiki-source-fd66d24a822d952e7edc6b81
    resource: repo://docs/2.0/sql/expressions/collations.md
  - id: openwiki-source-76d158312c52cf8af118a741
    resource: repo://docs/2.0/sql/expressions/comparison_operators.md
  - id: openwiki-source-4e9d7fc9180a98a6a96f4004
    resource: repo://docs/2.0/sql/expressions/in.md
  - id: openwiki-source-36790802019c4bfb707b3ba7
    resource: repo://docs/2.0/sql/expressions/subqueries.md
  - id: openwiki-source-99efdd7147191a9563c79396
    resource: repo://docs/2.0/sql/expressions/try.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---


# Expressions: CASE, CAST, TRY, Operators, Subqueries and Collations

An expression combines values, operators and functions and can appear in many parts of a statement. Type conversion rules are on [Data Types Overview, Casting](data-types/overview-and-casting.md); function lists are on the [function pages](functions/overview-numeric-and-utility.md).

## `CASE`, `IF` and `SWITCH`

```sql
CREATE OR REPLACE TABLE integers AS SELECT unnest([1, 2, 3]) AS i;
SELECT i, CASE WHEN i > 2 THEN 1 ELSE 0 END AS test FROM integers;
SELECT i, IF(i > 2, 1, 0) AS test FROM integers;                               -- same
SELECT i, CASE WHEN i = 1 THEN 10 WHEN i = 2 THEN 20 ELSE 0 END AS test FROM integers;
SELECT i, CASE WHEN i = 1 THEN 10 END AS test FROM integers;                    -- no ELSE → NULL
SELECT i, CASE i WHEN 1 THEN 10 WHEN 2 THEN 20 WHEN 3 THEN 30 END AS test FROM integers;   -- switch form
SELECT i, SWITCH(i, MAP {1: 'one', 2: 'two'}, 'other') AS test FROM integers;   -- MAP of value → result, optional default
```

The first matching `WHEN` wins; without `ELSE`, unmatched rows give `NULL`.

## Casting

```sql
SELECT CAST(i AS VARCHAR) AS i FROM generate_series(1, 3) tbl(i);
SELECT i::DOUBLE AS i FROM generate_series(1, 3) tbl(i);      -- PostgreSQL shorthand
SELECT CAST('hello' AS INTEGER);                               -- Conversion Error: Could not convert string 'hello' to INT32
SELECT TRY_CAST('hello' AS INTEGER) AS i;                      -- NULL, never errors
SELECT cast_to_type('42', NULL::INTEGER) AS result;            -- cast to the type of another expression
```

Not every cast exists (e.g. `INTEGER` → `DATE`), and numeric casts round. `cast_to_type` helps generic [macros](statements/views-macros-and-types.md) keep types:

```sql
CREATE MACRO conditional_add(col, nr) AS
    CASE
        WHEN typeof(col) == 'INTEGER' THEN cast_to_type(col::INTEGER + nr, col)
        ELSE col
    END;
SELECT conditional_add(COLUMNS(*), 100) FROM tbl;
```

## `TRY`

`TRY(expr)` turns errors caused by input rows into `NULL` for those rows:

```sql
SELECT TRY('abc'::INTEGER);       -- NULL
SELECT TRY(1 // 0);               -- NULL (integer division by zero errors by default in 2.0)
WITH cte AS (FROM (VALUES ('123'), ('test'), ('235')) t(a))
SELECT TRY(a::INTEGER) AS x FROM cte;    -- 123, NULL, 235
```

`TRY` cannot wrap volatile functions (`TRY(random())` → `Binder Error: TRY can not be used in combination with a volatile function`), aggregates, or scalar subqueries.

## Comparison operators

| Operator | Meaning | Example | Result |
| --- | --- | --- | --- |
| `<`, `>`, `<=`, `>=` | ordering | `4 >= NULL` | `NULL` |
| `=` or `==` | equal | `NULL = NULL` | `NULL` |
| `<>` or `!=` | not equal | `2 <> 2` | `false` |
| `IS DISTINCT FROM` | not equal, `NULL`-safe | `2 IS DISTINCT FROM NULL` | `true` |
| `IS NOT DISTINCT FROM` | equal, `NULL`-safe | `NULL IS NOT DISTINCT FROM NULL` | `true` |

Any `NULL` input to a standard comparison yields `NULL`. Comparing different types uses **combination casting**, so `1 = true` and `1 = '1.1'` are `true` (they fail in PostgreSQL); stricter checking is not configurable — use a macro with `typeof` if needed.

| Predicate | Meaning |
| --- | --- |
| `a BETWEEN x AND y` | `x <= a AND a <= y` (all inputs cast to one type; `x > y` is always `false`) |
| `a NOT BETWEEN x AND y` | `x > a OR a > y` |
| `expr IS NULL` / `ISNULL` | `NULL` test |
| `expr IS NOT NULL` / `NOTNULL` | not-`NULL` test |

An explicit collation on any `BETWEEN` input applies to the whole expression: `'B' NOT BETWEEN ('A' COLLATE NOCASE) AND 'a'` is `true`, while the separately written comparisons give `false`.

## Logical operators

`AND`, `OR`, `NOT` use three-valued logic; they are commutative.

| `a` | `b` | `a AND b` | `a OR b` |
| --- | --- | --- | --- |
| true | NULL | NULL | true |
| false | NULL | false | NULL |
| NULL | NULL | NULL | NULL |

`NOT NULL` is `NULL`.

## The `IN` operator

| Right-hand side | Semantics | Example |
| --- | --- | --- |
| Tuple `(v1, v2, ...)` | `true` if present; if absent, `NULL` when the tuple contains `NULL`, else `false` | `'English' IN ('CS', 'Math', NULL)` → `NULL` |
| List `[v1, v2, ...]` | Python semantics; `NULL`s do not matter | `'English' IN ['CS', 'Math', NULL]` → `false` |
| `MAP` | Checks **keys** | `'key1' IN MAP {'key1': 50, 'key2': 75}` → `true` |
| Subquery | Must return one column (else `Binder Error: Subquery returns 2 columns - expected 1`) | `42 IN (SELECT unnest([32, 42, 52]) AS x)` |
| String | Shorthand for `contains` | `'Hello' IN 'Hello World'` → `true` |

`x NOT IN y` equals `NOT (x IN y)`.

## Subqueries

Subqueries are parenthesized query expressions; besides `SELECT`, constructs like `PIVOT` can appear as subqueries.

```sql
CREATE TABLE grades (grade INTEGER, course VARCHAR);
INSERT INTO grades VALUES (7, 'Math'), (9, 'Math'), (8, 'CS');

SELECT course FROM grades WHERE grade = (SELECT min(grade) FROM grades);   -- scalar subquery
SELECT ARRAY(SELECT grade FROM grades) AS all_grades;                      -- [7, 9, 8]
SELECT 6 <= ALL (SELECT grade FROM grades) AS adequate;                     -- true
SELECT 5 >= ANY (SELECT grade FROM grades) AS fail;                         -- false (SOME = ANY)
SELECT EXISTS (FROM grades WHERE course = 'Math') AS math_grades_present;
SELECT 'Math' IN (SELECT course FROM grades) AS math_grades_present;
```

- A **scalar subquery** returning more than one row raises an error, unless the deprecated `scalar_subquery_error_on_multiple_rows` is `false` (then an arbitrary row is used).
- `EXISTS` / `NOT EXISTS` are most useful **correlated** (semi-/antijoins); DuckDB detects `NOT EXISTS` antijoins automatically, no `LEFT JOIN ... IS NULL` rewrite needed. `FROM`-first syntax lets you omit `SELECT *` inside them.

```sql
SELECT * FROM Person WHERE NOT EXISTS (FROM interest WHERE interest.PersonId = Person.id);
SELECT * FROM grades grades_parent
WHERE grade = (SELECT min(grade) FROM grades WHERE grades.course = grades_parent.course);   -- correlated
SELECT t FROM (SELECT unnest(generate_series(41, 43)) AS x, 'hello' AS y) t;                -- each row as a STRUCT
```

## Collations

The default collation is `BINARY` (aliases `C`, `POSIX`): byte-wise comparison. Built-in collations: `NOCASE`, `NOACCENT`, `NFC` (Unicode normalization). Chain with `.`; `NOCASE` combines with any other collation, most others cannot be combined.

```sql
SELECT 'hello' COLLATE NOCASE = 'hElLO';            -- true
SELECT 'hello' COLLATE NOACCENT = 'hëllo';          -- true
SELECT 'hello' COLLATE NOCASE.NOACCENT = 'hElLÖ';   -- true
SET default_collation = NOCASE;                     -- global default
CREATE TABLE names (name VARCHAR COLLATE NOACCENT); -- per column
```

Different collations cannot be combined in one comparison (`ERROR: Cannot combine types with different collation!`); override both sides, e.g. `names.name COLLATE NOACCENT.NOCASE = other_names.name COLLATE NOACCENT.NOCASE`. The `icu` extension adds language/region collations (list with `PRAGMA collations;` or `pragma_collations()`), e.g. `CREATE TABLE strings (s VARCHAR COLLATE DE);`. Collation support has known limitations.

Pattern matching (`LIKE`, `SIMILAR TO`, `GLOB`, `~`) is on [Text Functions, Pattern Matching](functions/text-and-pattern-matching.md); star and `COLUMNS` expressions on [Friendly SQL](dialect/friendly-sql.md).
