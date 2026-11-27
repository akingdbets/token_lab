---
type: reference
title: PIVOT and UNPIVOT
description: DuckDB's PIVOT (PIVOT_WIDER) and UNPIVOT (PIVOT_LONGER) statements — the simplified syntax with ON, USING, GROUP BY and IN filters, dynamic column detection, multiple ON/USING/GROUP BY expressions and generated column names, pivots in CTEs and subqueries, expressions in USING, the SQL-standard PIVOT (... FOR ... IN ...) and UNPIVOT [INCLUDE NULLS] forms, COLUMNS-based dynamic unpivoting and unpivoting into multiple value columns.
tags: [sql, pivot, unpivot, pivot-wider, pivot-longer, reshaping, columns-expression]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-8386d6431afcd21313dcced3
    resource: repo://docs/2.0/sql/statements/pivot.md
  - id: openwiki-source-12f72f1ed814ee49d76f3b5d
    resource: repo://docs/2.0/sql/statements/unpivot.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# PIVOT and UNPIVOT

`PIVOT` spreads the distinct values of a column into separate columns, aggregating the matching rows; `UNPIVOT` stacks columns back into name/value rows. They are inverses. DuckDB supports a **simplified** syntax (with automatic detection of the columns to create) and the **SQL-standard** syntax. `PIVOT_WIDER` and `PIVOT_LONGER` are synonyms for `PIVOT` and `UNPIVOT`. For static pivots with a fixed column list, aggregates with `FILTER` also work (see [GROUP BY … FILTER](../query-syntax/grouping-and-filtering.md)).

## Simplified `PIVOT`

```sql
PIVOT ⟨dataset⟩
ON ⟨columns⟩                       -- spreadsheet "columns"
USING ⟨values⟩                     -- spreadsheet "values"
GROUP BY ⟨rows⟩                    -- spreadsheet "rows"
ORDER BY ⟨columns_with_order_directions⟩
LIMIT ⟨number_of_rows⟩;
```

`ON`, `USING` and `GROUP BY` are each optional, but not all may be omitted. Example data:

```sql
CREATE TABLE cities (country VARCHAR, name VARCHAR, year INTEGER, population INTEGER);
INSERT INTO cities VALUES
    ('NL', 'Amsterdam', 2000, 1005), ('NL', 'Amsterdam', 2010, 1065), ('NL', 'Amsterdam', 2020, 1158),
    ('US', 'Seattle', 2000, 564), ('US', 'Seattle', 2010, 608), ('US', 'Seattle', 2020, 738),
    ('US', 'New York City', 2000, 8015), ('US', 'New York City', 2010, 8175), ('US', 'New York City', 2020, 8772);
```

```sql
PIVOT cities ON year USING sum(population);
```

| country | name | 2000 | 2010 | 2020 |
| --- | --- | ---: | ---: | ---: |
| NL | Amsterdam | 1005 | 1065 | 1158 |
| US | Seattle | 564 | 608 | 738 |
| US | New York City | 8015 | 8175 | 8772 |

- **`USING`** defaults to `count(*)`. To reorient without aggregating, use `first(...)` — it also pivots text columns. `FILTER` clauses on `USING` aggregates are currently **silently ignored**.
- **`GROUP BY`**: by default all columns not in `ON`/`USING` are kept; `GROUP BY` keeps only the listed columns and aggregates further. Use column names (not positions); expressions are not supported in `GROUP BY`.
- **`IN` filter**: create columns only for specific values.

```sql
PIVOT cities ON year USING sum(population) GROUP BY country;
PIVOT cities ON year IN (2000, 2010) USING sum(population) GROUP BY country;
PIVOT cities ON year USING sum(population) GROUP BY country, name;
PIVOT cities ON year USING sum(population) * 1000;        -- expressions over aggregates
```

### Multiple expressions

- **Several `ON` columns** create a column for every combination of their distinct values (Cartesian product); combinations absent from the data are filled with `NULL`. To pivot only combinations that exist, use an expression instead: `ON country || '_' || name`.
- **Several `USING` expressions** with aliases produce columns named `⟨value⟩_⟨alias⟩`:

```sql
PIVOT cities ON country, name USING sum(population);
PIVOT cities ON country || '_' || name USING sum(population);

PIVOT cities
ON year
USING sum(population) AS total, max(population) AS max
GROUP BY country;
-- columns: country, 2000_total, 2000_max, 2010_total, 2010_max, 2020_total, 2020_max
```

### `PIVOT` inside queries

A simplified `PIVOT` acts like a `SELECT` node: use it as a CTE body (no `SELECT` needed) or a parenthesized subquery, and join several pivots:

```sql
WITH pivot_alias AS (
    PIVOT cities ON year USING sum(population) GROUP BY country
)
SELECT * FROM pivot_alias;

SELECT *
FROM (PIVOT cities ON year USING sum(population) GROUP BY country) year_pivot
JOIN (PIVOT cities ON name USING sum(population) GROUP BY country) name_pivot
USING (country);

-- post-process all pivoted columns at once
SELECT country, name, 1000 * COLUMNS(* EXCLUDE (country, name))
FROM (PIVOT cities ON year USING sum(population));
```

## SQL-standard `PIVOT`

```sql
SELECT *
FROM ⟨dataset⟩
PIVOT (
    ⟨values⟩
    FOR
        ⟨column_1⟩ IN (⟨in_list⟩)
        ⟨column_2⟩ IN (⟨in_list⟩)
    GROUP BY ⟨rows⟩
);
```

An `IN` list is **required** for every pivoted column, so for dynamic pivoting prefer the simplified syntax. `FOR` expressions are **not** comma-separated, but value and `GROUP BY` expressions are.

```sql
SELECT *
FROM cities
PIVOT (sum(population) FOR year IN (2000, 2010, 2020) GROUP BY country);

SELECT *
FROM cities
PIVOT (
    sum(population) AS total,
    count(population) AS count
    FOR
        year IN (2000, 2010)
        country IN ('NL', 'US')
);
```

## Simplified `UNPIVOT`

```sql
UNPIVOT ⟨dataset⟩
ON ⟨column(s)⟩
INTO
    NAME ⟨name_column_name⟩
    VALUE ⟨value_column_name(s)⟩
ORDER BY ⟨column(s)_with_order_direction(s)⟩
LIMIT ⟨number_of_rows⟩;
```

By default the result has a `name` column (source column name) and a `value` column.

```sql
CREATE OR REPLACE TABLE monthly_sales
    (empid INTEGER, dept TEXT, Jan INTEGER, Feb INTEGER, Mar INTEGER, Apr INTEGER, May INTEGER, Jun INTEGER);
INSERT INTO monthly_sales VALUES
    (1, 'electronics', 1, 2, 3, 4, 5, 6),
    (2, 'clothes', 10, 20, 30, 40, 50, 60),
    (3, 'cars', 100, 200, 300, 400, 500, 600);

UNPIVOT monthly_sales
ON jan, feb, mar, apr, may, jun
INTO NAME month VALUE sales;

-- dynamic: works however many month columns exist
UNPIVOT monthly_sales
ON COLUMNS(* EXCLUDE (empid, dept))
INTO NAME month VALUE sales;

-- multiple value columns: one row per quarter
UNPIVOT monthly_sales
    ON (jan, feb, mar) AS q1, (apr, may, jun) AS q2
    INTO NAME quarter VALUE month_1_sales, month_2_sales, month_3_sales;
```

- Each column set in `ON` must have as many columns as the `VALUE` clause; the set aliases (`q1`, `q2`) are optional.
- Like `PIVOT`, a simplified `UNPIVOT` can be a CTE body or a parenthesized subquery.
- Expressions are allowed if each involves a single column, e.g. for casts:

```sql
UNPIVOT (SELECT 42 AS col1, 'woot' AS col2)
ON (col1 * 2)::VARCHAR, col2;
-- name | value: (col1, 84), (col2, woot)
```

## SQL-standard `UNPIVOT`

```sql
FROM [dataset]
UNPIVOT [INCLUDE NULLS] (
    [value-column-name(s)]
    FOR [name-column-name] IN [column(s)]
);
```

Only one name column is allowed. Examples:

```sql
FROM monthly_sales UNPIVOT (sales FOR month IN (jan, feb, mar, apr, may, jun));
FROM monthly_sales UNPIVOT (sales FOR month IN (columns(* EXCLUDE (empid, dept))));

FROM monthly_sales
UNPIVOT (
    (month_1_sales, month_2_sales, month_3_sales)
    FOR quarter IN ((jan, feb, mar) AS q1, (apr, may, jun) AS q2)
);
```

A reusable `stack` table macro built on `UNPIVOT` via `query()` is shown on [CTEs, Recursive Queries, Set Operations, UNNEST and query()](../query-syntax/ctes-set-operations-unnest.md).
