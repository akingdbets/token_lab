---
type: reference
title: VARIANT and GEOMETRY Types
description: The VARIANT type for self-describing semi-structured values (storage shredding new in 2.0, Parquet shredding and the SHREDDING option) with its variant_* functions, and the built-in GEOMETRY type (Simple Features, WKT, Z/M dimensions, shredding, statistics and the && operator, coordinate reference systems with ST_SetCRS/ST_Transform) with its built-in ST_ functions.
tags: [data-types, variant, semi-structured, geometry, spatial, crs, wkt, shredding]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-94f91ab5c90e10a35ed08522
    resource: repo://docs/2.0/sql/data_types/geometry.md
  - id: openwiki-source-4c510fd9cd8347568c91d8e7
    resource: repo://docs/2.0/sql/data_types/variant.md
  - id: openwiki-source-67c5b8a947dc403f19725301
    resource: repo://docs/2.0/sql/functions/variant.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# VARIANT and GEOMETRY Types

Two specialized types: `VARIANT` for semi-structured data (an alternative to the text-based [JSON type](../../data/json/json-type-and-functions.md)) and `GEOMETRY` for spatial data. Other nested types are on [Nested Types](nested-types.md).

## `VARIANT`

`VARIANT` stores typed **binary** data where each value carries its own type information, unlike `JSON` which is stored as text — giving better compression and query performance. It is inspired by Snowflake's `VARIANT`, exists in Parquet since 2025, and each row can hold a different type.

```sql
CREATE TABLE events (id INTEGER, data VARIANT);
INSERT INTO events VALUES
    (1, 42::VARIANT),
    (2, 'hello world'::VARIANT),
    (3, [1, 2, 3]::VARIANT),
    (4, {'name': 'Alice', 'age': 30}::VARIANT);

SELECT id, data, variant_typeof(data) AS vtype FROM events;
SELECT data.name FROM events WHERE id = 4;                         -- dot notation
SELECT variant_extract(data, 'name') AS name FROM events WHERE id = 4;
```

Object keys are **sorted**: `{'name': 'Alice', 'age': 30}::VARIANT` displays as `{'age': 30, 'name': Alice}`.

### Storage and Parquet

- **Shredding in DuckDB storage (new in 2.0):** DuckDB detects common structure and stores fields sharing a type as separate typed columns, which compress and scan well. It applies to row groups with at least `variant_minimum_shredding_size` rows (default **30,000**, about a quarter of a row group); `SET variant_minimum_shredding_size = -1;` disables it.
- **Parquet:** DuckDB reads and writes `VARIANT`, auto-shredding based on the first row group (enabling predicate pushdown). Provide an explicit schema with `SHREDDING`. Shredded `VARIANT` Parquet files written by Snowflake are reconstructed automatically.

```sql
COPY events TO 'events.parquet' (
    FORMAT parquet,
    SHREDDING {'data': 'STRUCT(name VARCHAR, age INTEGER)'}
);
```

### Variant functions

Most `variant_*` functions are **new in DuckDB 2.0**; `variant_extract`, `variant_normalize` and `variant_typeof` existed in 1.5. A `path` is a field name (`''` = the value itself) or a list of paths.

| Function | Description |
| --- | --- |
| `variant_typeof(v)` | Detailed type, e.g. `OBJECT(a, b, c)` (sorted keys), `ARRAY(3)`, `INT32`, `DECIMAL(18, 6)` |
| `variant_type(v[, path])` | Top-level category: `OBJECT`, `ARRAY`, `VARCHAR`, `INT32`, … |
| `variant_keys(v[, path])` | Object keys (sorted); empty list for arrays/primitives |
| `variant_extract(v, field)` | Field or **1-based** list element as `VARIANT` (index 0 errors); chainable |
| `variant_extract_string(v, path)` | Value as `VARCHAR` (objects/arrays rendered as JSON) |
| `variant_array_length(v[, path])` | Array length (`0` for objects) |
| `variant_exists(v, path)` | Whether the path exists |
| `variant_contains(haystack, needle)` | Containment at any depth, ignoring key/element order |
| `variant_comparator(v)` | Sort key equal for logically equal values (key order, int vs decimal, float vs double) |
| `variant_normalize(v)` | Normalized representation |
| `variant_group_object(key, value)` | Aggregate into an object (`NULL` or duplicate keys error); new in 2.0 |
| `variant_group_array(x)` | Aggregate into an array, keeping types and `NULL`s; also a window function; new in 2.0 |

```sql
SELECT variant_extract(['A', 'B']::VARIANT, 1);                                         -- A
SELECT variant_contains('[1, 2, 3]'::JSON::VARIANT, '[3, 1]'::JSON::VARIANT);           -- true
SELECT variant_group_object(k, v) FROM (VALUES ('duck', 'goose'::VARIANT), ('pond', 26::VARIANT)) t(k, v);
SELECT * FROM events WHERE variant_contains(payload, {'user': {'id': 42}}::VARIANT);
SELECT i FROM range(-2, 2) t(i) ORDER BY i::VARIANT;   -- VARIANTs sort by logical value
```

## `GEOMETRY`

`GEOMETRY` stores points, lines and polygons. It moved from the `spatial` extension into the core as a **built-in type in DuckDB 1.5**; storage optimizations and statistics need storage version v1.5+ (the default in 2.0). It follows the **Simple Features** model with seven shape types — `POINT`, `LINESTRING`, `POLYGON` (shell plus interior hole rings), `MULTIPOINT`, `MULTILINESTRING`, `MULTIPOLYGON`, `GEOMETRYCOLLECTION` — and casts to/from **WKT** strings:

```sql
CREATE TABLE geometries (id INTEGER, geom GEOMETRY);
INSERT INTO geometries VALUES
    (1, 'POINT (30 10)'),
    (2, 'LINESTRING (30 10, 10 30, 40 40)'),
    (3, 'POLYGON ((30 10, 40 40, 20 40, 10 20, 30 10))'),
    (7, 'GEOMETRYCOLLECTION (POINT(40 10), LINESTRING(10 10,20 20,10 40), POLYGON((40 40,20 45,45 30,40 40)))');
```

- **Dimensions:** besides X/Y, vertices may carry `Z` (elevation) and/or `M` (measure): `'POINT Z (30 10 5)'`, `'POINT ZM (30 10 5 1)'`. Dimensions must be consistent within a geometry (`Geometry has inconsistent Z/M dimensions`). Most functions ignore Z/M.
- **Empty geometries** (`POINT EMPTY`, …) are valid.
- **Storage:** bytes like `BLOB`, based on little-endian WKB (format not yet stable).
- **Shredding:** row groups where all values share one geometry type and dimensions are split into compressible `STRUCT(X DOUBLE, Y DOUBLE)` / list segments (not for collections, `EMPTY` geometries or mixed types). Threshold `geometry_minimum_shredding_size` defaults to ~30,000 rows; `0` always shreds, `-1` disables.
- **Statistics:** per-row-group bounding box, geometry types and dimensions (inspect with `stats(geom)`, which returns a `VARIANT`). Currently only the bounding-box intersection operator `&&` in `WHERE` uses them to skip row groups.

### Coordinate reference systems

The engine treats coordinates as Cartesian; a CRS (like a "time zone for geodata") can be attached to the column type, e.g. `GEOMETRY('OGC:CRS84')` (longitude/latitude). Requirements and rules:

- Columns with a CRS need storage version v1.5.0+.
- Only **known** CRSs are accepted (`Binder Error: Encountered unrecognized coordinate system 'DUCK:1337' ...`); list them with `SELECT * FROM duckdb_coordinate_systems();`. The `spatial` extension registers 7000+ EPSG systems. `SET ignore_unknown_crs = true;` drops unknown CRSs instead; a full WKT/PROJJSON definition may be given.
- Functions with multiple geometries check that CRSs match.

```sql
LOAD spatial;
SET geometry_always_xy = true;   -- required in DuckDB 2.0: assume [longitude, latitude] order
SELECT ST_Transform('POINT(4.897070 52.377956)'::GEOMETRY('OGC:CRS84'), 'EPSG:3857') AS transformed;
SELECT ST_SetCRS('POINT(4.897070 52.377956)'::GEOMETRY, 'OGC:CRS84') AS with_crs;
SELECT 'POINT(4.897070 52.377956)'::GEOMETRY('OGC:CRS84')::GEOMETRY AS no_crs;   -- or ST_SetCRS(g, '')
SELECT ST_CRS('POINT(4.897070 52.377956)'::GEOMETRY('OGC:CRS84')) AS crs;
```

### Built-in geometry functions

| Function | Description |
| --- | --- |
| `ST_GeomFromWKB` | Geometry from Well-Known Binary |
| `ST_AsWKB` | Geometry to WKB |
| `ST_AsWKT` | Geometry to WKT |
| `ST_Intersects_Extent` | Whether bounding boxes intersect (also the `&&` operator) |
| `ST_CRS` / `ST_SetCRS` | Get / set the CRS identifier |

The `spatial` extension adds many more (areas, distances, intersections, `ST_Transform`, GeoJSON via `st_asgeojson`/`st_geomfromgeojson`, R-tree indexes). GeoJSON file I/O is covered in [Loading and Writing JSON Files](../../data/json/loading-and-writing-json.md).
