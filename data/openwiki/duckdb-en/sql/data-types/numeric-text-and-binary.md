---
type: reference
title: Numeric, Text, BLOB and BITSTRING Types
description: DuckDB's integer types and aliases, BIGNUM, DECIMAL(WIDTH, SCALE) rules (bare DECIMAL = DECIMAL(18,3)), FLOAT/DOUBLE and special values, UUID (v4/v7), rounding rules for casts, VARCHAR (length has no effect, USING COMPRESSION), BLOB with X'…' literals and blob functions, and BITSTRING with B'…' literals, bitwise operators and functions.
tags: [data-types, integer, decimal, float, uuid, varchar, blob, bitstring]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-878f49b75b50b846c4cca75d
    resource: repo://docs/2.0/sql/data_types/bitstring.md
  - id: openwiki-source-00c246b033da20dfef5341a4
    resource: repo://docs/2.0/sql/data_types/blob.md
  - id: openwiki-source-8b54b68ab9e25edaf2a09660
    resource: repo://docs/2.0/sql/data_types/numeric.md
  - id: openwiki-source-cb5ccde54b498d87ad0fa297
    resource: repo://docs/2.0/sql/data_types/text.md
  - id: openwiki-source-ca8f7ce52e545cb35ca73cff
    resource: repo://docs/2.0/sql/functions/bitstring.md
  - id: openwiki-source-5c3bdb74972be679f5e7f1a9
    resource: repo://docs/2.0/sql/functions/blob.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Numeric, Text, BLOB and BITSTRING Types

Numeric functions are on [Function Basics, Numeric and Utility Functions](../functions/overview-numeric-and-utility.md); string functions on [Text Functions, Pattern Matching](../functions/text-and-pattern-matching.md). Type overview and casting rules: [Data Types Overview and Casting](overview-and-casting.md).

## Integer types

Out-of-range values (and negative values for unsigned types) raise an error.

| Name | Aliases | Range | Bytes |
| --- | --- | --- | --- |
| `TINYINT` | `INT1` | −2^7 … 2^7−1 | 1 |
| `SMALLINT` | `INT2`, `INT16`, `SHORT` | −2^15 … 2^15−1 | 2 |
| `INTEGER` | `INT4`, `INT32`, `INT`, `SIGNED` | −2^31 … 2^31−1 | 4 |
| `BIGINT` | `INT8`, `INT64`, `LONG` | −2^63 … 2^63−1 | 8 |
| `HUGEINT` | `INT128` | −2^127 … 2^127−1 | 16 |
| `UTINYINT` | `UINT8` | 0 … 2^8−1 | 1 |
| `USMALLINT` | `UINT16` | 0 … 2^16−1 | 2 |
| `UINTEGER` | `UINT32` | 0 … 2^32−1 | 4 |
| `UBIGINT` | `UINT64` | 0 … 2^64−1 | 8 |
| `UHUGEINT` | `UINT128` | 0 … 2^128−1 | 16 |

> `INT8` is a **64-bit** integer (PostgreSQL aliases count bytes), not the signed counterpart of `UINT8` (which counts bits).

`INTEGER` is the usual choice; `SMALLINT` only when disk space is at a premium; `BIGINT`/`HUGEINT` when the range is insufficient. **`BIGNUM`** stores arbitrarily large integers (three extra bytes for size and sign), up to about `±4.27e20201778` (20,201,779 digits, 8 MB per value).

## `DECIMAL(WIDTH, SCALE)` / `NUMERIC`

Exact fixed-point numbers: `WIDTH` total digits, `SCALE` digits after the point.

```sql
SELECT typeof(1.5::DECIMAL), typeof(1.5::DECIMAL()), typeof(1.5::DECIMAL(10)), typeof(1.5::DECIMAL(10,));
-- DECIMAL(18,3)  DECIMAL(18,3)  DECIMAL(10,0)  DECIMAL(10,0)
```

- A bare `DECIMAL` is **not unconstrained** (unlike PostgreSQL/Oracle): it is `DECIMAL(18, 3)`, rounding to 3 fractional digits with at most 15 integer digits.
- `WIDTH` must be 1–38; `SCALE` 0–38 and ≤ `WIDTH`; violations are binder errors (`DECIMAL type width must be between 1 and 38`, `DECIMAL type scale cannot be greater than width`). Negative scale is not supported.
- `+`, `-`, `*` return an exact decimal of sufficient width (error if more than 38 is needed). **Division of decimals uses floating point** and returns a floating-point type.
- Storage by width: 1–4 → `INT16`, 5–9 → `INT32`, 10–18 → `INT64`, 19–38 → `INT128`. Widths above 18/19 are much slower — prefer `WIDTH` ≤ 18.

Use `DECIMAL` for exact values such as money; floating point for fast or complex calculations.

## `FLOAT` and `DOUBLE`

| Name | Aliases | Description |
| --- | --- | --- |
| `FLOAT` | `FLOAT4`, `REAL` | Single precision (4 bytes), ≥ 6 digits, range ~1E-37…1E+37 |
| `DOUBLE` | `FLOAT8` | Double precision (8 bytes), ≥ 15 digits, range ~1E-307…1E+308 |

IEEE 754 approximations: `+`, `-`, `*` are inexact. Special values `Infinity` (`Inf`), `-Infinity` and `NaN` must be quoted and are case-insensitive. **Exception to IEEE 754:** `NaN` equals `NaN` and is greater than all other floating-point values.

```sql
SELECT sqrt(2) > '-inf', 'nan' > sqrt(2);   -- true, true
```

## `UUID`

128-bit identifiers stored as `HUGEINT`, printed as 36 lowercase hex characters with dashes, e.g. `4ac7a9e9-607c-4c8a-84f3-843f0191e3fd`. Generate v4 with `uuid()` (aliases `uuidv4()`, `gen_random_uuid()`) and time-ordered v7 with `uuidv7()`; inspect with `uuid_extract_version` and `uuid_extract_timestamp`:

```sql
SELECT uuid_extract_timestamp(uuidv7()) AS ts;
```

## Rounding when casting to integers

- `FLOAT`/`DOUBLE` → integer: round half to **even** (banker's rounding): `SELECT 2.5::FLOAT::INTEGER;` → 2.
- `DECIMAL` → integer: round half **away from zero**: `SELECT 2.5::DECIMAL::INTEGER;` → 3. Number literals are `DECIMAL`s, so `SELECT 2.5::INTEGER;` → 3.
- For other behavior use `ceil`, `floor`, `round`, `round_even`.

## Text: `VARCHAR`

| Name | Aliases |
| --- | --- |
| `VARCHAR` | `CHAR`, `BPCHAR`, `STRING`, `TEXT` |
| `VARCHAR(n)` | `CHAR(n)`, `BPCHAR(n)`, `STRING(n)`, `TEXT(n)` |

Strings are Unicode, stored as UTF-8. The length `n` **has no effect** (no performance or storage benefit, only compatibility). Enforce a maximum length with a `CHECK` constraint; choose a compression method with `USING COMPRESSION`:

```sql
CREATE TABLE strings (val VARCHAR CHECK (length(val) <= 10));
CREATE TABLE tbl (s VARCHAR USING COMPRESSION zstd);
SELECT 'Hello' || chr(10) || 'world' AS msg;   -- special characters; also E'...' and $$...$$ literals
```

## `BLOB`

| Name | Aliases |
| --- | --- |
| `BLOB` | `BYTEA`, `BINARY`, `VARBINARY` |

Arbitrary binary data, opaque to the database; up to 4 GB, though storing very large objects in the database is not recommended.

```sql
SELECT '\xAA'::BLOB;            -- one byte (170)
SELECT '\xAA\xAB\xAC'::BLOB;    -- three bytes
SELECT 'AB'::BLOB;              -- two bytes (65, 66)
SELECT X'CAFE';                 -- hex literal (even digit count)
```

**Changed in 2.0:** `X'…'` literals are `BLOB`s; earlier, `X'CAFE'` parsed as the `VARCHAR` `'xCAFE'`.

| Blob function | Description |
| --- | --- |
| `blob1 \|\| blob2` | Concatenation (`NULL` input → `NULL`) |
| `decode(blob[, on_error])` | `BLOB` → `VARCHAR`; `on_error` `'strict'` (default), `'replace'` (`?`), `'ignore'` |
| `encode(string)` | `VARCHAR` → `BLOB` |
| `to_base64(blob)` (`base64`) / `from_base64(string)` | Base64 conversion |
| `hex(blob)` (`to_hex`) / `unhex(value)` (`from_hex`) | Hex conversion |
| `unbin(value)` (`from_binary`) | Binary-digit string → blob |
| `md5(blob)`, `md5_number(blob)`, `sha1(blob)`, `sha256(blob)` | Hashes (`md5_number` returns `UHUGEINT`) |
| `octet_length(blob)` | Number of bytes |
| `repeat(blob, count)` | Repeat |
| `read_blob(source)` | Read files as `BLOB` (see [File Access](../../data/overview-and-file-access.md)) |

```sql
SELECT decode('\xC3\xBC'::BLOB), decode('\xAA'::BLOB, 'replace'), hex('\xAA\xBB'::BLOB), to_base64('A'::BLOB);
```

## `BITSTRING` (`BIT`)

Variable-length strings of 1s and 0s (1 byte per 8 bits plus metadata, not zero-padded by default, same size limits as `BLOB`).

```sql
SELECT '101010'::BITSTRING AS b;
SELECT B'101010' AS b;                    -- bit literal; changed in 2.0 (was VARCHAR 'b101010')
SELECT bitstring('0101011', 12) AS b;     -- 000000101011 (left-padded)
SELECT 123::BITSTRING AS b;               -- 32-bit representation of an INTEGER
```

Bitwise `AND`, `OR` and `XOR` need equal-length operands; shifts keep the original length.

| Operator | Example | Result |
| --- | --- | --- |
| `&` | `'10101'::BITSTRING & '10001'::BITSTRING` | `10001` |
| `\|` | `'1011'::BITSTRING \| '0001'::BITSTRING` | `1011` |
| `xor` | `xor('101'::BITSTRING, '001'::BITSTRING)` | `100` |
| `~` | `~('101'::BITSTRING)` | `010` |
| `<<` / `>>` | `'1001011'::BITSTRING << 3` / `>> 3` | `1011000` / `0001001` |

Functions: `bit_count`, `bit_length` (`length`), `octet_length`, `bit_position(substring, bitstring)` (1-based, 0 if absent), `bitstring(bitstring, length)`, `get_bit(bitstring, index)` and `set_bit(bitstring, index, new_value)` (**0-based**). Aggregates: `bit_and`, `bit_or`, `bit_xor`, `bitstring_agg(arg[, min, max])` — a bit per distinct integer value (values outside `[min, max]` raise `Out of Range Error`). `bit_count(bitstring_agg(x))` can replace `count(DISTINCT x)` for dense, low-cardinality values.
