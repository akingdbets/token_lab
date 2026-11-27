---
type: reference
title: Text Functions, Pattern Matching and Regular Expressions
description: DuckDB string functions and operators (slicing, concat vs ||, substring, split_part, string_split, trim, lpad, replace, translate, parse_path, grapheme functions, overlay new in 2.0), text similarity (levenshtein, jaro_winkler), format() and printf() formatters, LIKE/ILIKE with ESCAPE, SIMILAR TO, GLOB, the ~ operators (partial match since 2.0), and RE2 regexp_* functions with options and capture groups.
tags: [sql, functions, text, string, like, glob, regex, regexp-extract, format, printf]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-5bf2eb8c5bdff1262cf15ddf
    resource: repo://docs/2.0/sql/functions/pattern_matching.md
  - id: openwiki-source-5fd41f4bc47744e57aea9de5
    resource: repo://docs/2.0/sql/functions/regular_expressions.md
  - id: openwiki-source-7a79e43b4994ae4378ab1ee5
    resource: repo://docs/2.0/sql/functions/text.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Text Functions, Pattern Matching and Regular Expressions

String values are `VARCHAR` (UTF-8); see [Numeric, Text, BLOB and BITSTRING Types](../data-types/numeric-text-and-binary.md). Collation-aware comparisons are on [Expressions](../expressions.md).

## Text functions and operators

| Function (aliases) | Description |
| --- | --- |
| `string[index]`, `string[begin:end]` | 1-based character / Python-like slice (`array_extract`, `array_slice`) |
| `s1 \|\| s2` | Concatenate; any `NULL` → `NULL` |
| `concat(value, ...)`, `concat_ws(sep, ...)` | Concatenate, skipping `NULL`s |
| `length(s)` (`len`, `char_length`, `character_length`), `strlen(s)` (bytes), `bit_length(s)`, `length_grapheme(s)` | Lengths |
| `lower` (`lcase`), `upper` (`ucase`) | Case conversion |
| `substring(s, start[, length])` (`substr`), `left(s, n)`, `right(s, n)`, `*_grapheme` variants | Substrings (characters or grapheme clusters) |
| `instr(s, search)` (`strpos`, `position(s, search)`, `position(search IN s)`) | 1-based position, 0 if absent |
| `contains(s, search)`, `starts_with(s, search)` (`prefix`, `^@`), `ends_with` (`suffix`) | Containment (no collation support) |
| `replace(s, source, target)`, `translate(s, from, to)`, `reverse(s)`, `repeat(s, n)` | Edits |
| `trim(s[, chars])`, `ltrim`, `rtrim` | Remove characters (default: Unicode spaces) |
| `lpad(s, count, char)`, `rpad(...)` | Pad (also truncate to `count`) |
| `split_part(s, sep, index)` | 1-based part (empty string if out of range) |
| `string_split(s, sep)` (`split`, `str_split`, `string_to_array`) | Split into a list |
| `string_split_regex(s, regex[, options])` (`regexp_split_to_array`, `str_split_regex`) | Split by regex |
| `ascii(s)`, `unicode(s)` (`ord`), `chr(code_point)` | Code points |
| `strip_accents(s)`, `nfc_normalize(s)` | Normalization |
| `greatest(...)`, `least(...)` | Lexicographic max/min (lowercase > uppercase) |
| `format_bytes(n)` (`pg_size_pretty`; KiB…), `formatReadableDecimalSize(n)` (KB…) | Human-readable sizes |
| `to_base(number, radix[, min_length])`, `bin`/`to_binary`, `hex`/`to_hex`, `unbin`, `unhex` | Base conversion |
| `md5`, `sha1`, `sha256`, `hash` | Hashes (`hash` is not cryptographic) |
| `url_encode(s)`, `url_decode(s)` | Percent-encoding |
| `parse_path(path[, sep])`, `parse_dirname`, `parse_dirpath`, `parse_filename(path[, trim_extension][, sep])` | Path parsing; separator `system`, `both_slash` (default), `forward_slash`, `backslash` |
| `bar(x, min, max[, width])` | Text bar chart (`width` default 80) |
| `like_escape`, `ilike_escape`, `not_like_escape`, `not_ilike_escape` | Function forms of `LIKE ... ESCAPE` |

**`overlay` (new in DuckDB 2.0)** replaces part of a string, in SQL-standard or function syntax:

```sql
SELECT overlay('Txxxxas' PLACING 'hom' FROM 2 FOR 4) AS result;     -- Thomas
SELECT overlay('Txxxxas', 'hom', 2, 4) AS a,
       overlay('hello' PLACING 'xyz' FROM 2) AS b,
       overlay('abc' PLACING 'XY' FROM 2 FOR 0) AS c;
```

### Text similarity

`levenshtein(s1, s2)` (`editdist3`), `damerau_levenshtein(s1, s2)` (adds transpositions), `hamming(s1, s2)` (`mismatches`, equal lengths), `jaccard(s1, s2)`, `jaro_similarity(s1, s2[, score_cutoff])`, `jaro_winkler_similarity(s1, s2[, score_cutoff])`. All are case-sensitive.

## Formatters

`format(format, ...)` follows the {fmt} library; `printf(format, ...)` follows C `printf`.

```sql
SELECT format('The answer is {}', 42);
SELECT format('I''d rather be {1} than {0}.', 'right', 'happy');   -- positional
SELECT format('{:04d}', 33);                                       -- 0033
SELECT format('{:x}', 123_456_789);                                -- 75bcd15
SELECT format('{:,}', 123_456_789);                                -- 123,456,789
SELECT format('{:t.}', 123_456_789);                               -- 123.456.789
SELECT format('{:,.2f}', 123456.789);                              -- 123,456.79
SELECT printf('The answer to %s is %d', 'life', 42);
SELECT printf('I''d rather be %2$s than %1$s.', 'right', 'happy');
SELECT printf('%02d:%02d:%02d %s', 12, 3, 16, 'AM');               -- 12:03:16 AM
SELECT printf('%,.2f', 123456.789);                                -- 123,456.79
```

`format` specifiers: `{:d}`, `{:E}`, `{:f}`, `{:o}`, `{:s}`, `{:x}`, `{:b}`, `{:tX}` (thousands separator `X`); padding cannot be combined with a thousands separator. `printf` specifiers: `%c`, `%d`, `%Xd` (separator from `,`, `.`, `''`, `_`), `%E`, `%f`, `%o`, `%s`, `%x`, `%b`.

## Pattern matching

### `LIKE` and `ILIKE`

`_` matches one character, `%` any sequence; the pattern must match the **whole** string. `ILIKE` is case-insensitive. Use `ESCAPE` to match literal wildcards.

```sql
SELECT 'abc' LIKE 'a%';                       -- true
SELECT 'abc' LIKE '_b_';                      -- true
SELECT 'abc' LIKE 'c';                        -- false
SELECT 'abc' ILIKE '%C';                      -- true
SELECT 'a%c' LIKE 'a$%c' ESCAPE '$';          -- true
SELECT 'A%c' ILIKE 'a$%c' ESCAPE '$';         -- true
```

PostgreSQL-style operators: `~~` (`LIKE`), `!~~` (`NOT LIKE`), `~~*` (`ILIKE`), `!~~*` (`NOT ILIKE`).

### `SIMILAR TO`

Like `LIKE` but with a regular expression, and it must match the **entire** string:

```sql
SELECT 'abc' SIMILAR TO '.*(b|d).*';   -- true
SELECT 'abc' SIMILAR TO '(b|c).*';     -- false
```

### `GLOB`

`?` = one character, `*` = any sequence, `[...]` = a set or range (case-sensitive), `[!...]` = negated set; `~~~` is the symbolic form.

```sql
SELECT 'best.txt' GLOB '*.txt';            -- true
SELECT 'best.txt' GLOB '????.txt';         -- true
SELECT 'Best.txt' GLOB '[a-z]est.txt';     -- false
SELECT 'Best.txt' GLOB '[!a-zA-Z]est.txt'; -- false
SELECT NOT 'best.txt' GLOB '*.txt';        -- false
SELECT * FROM glob('**/README.md');        -- ** also matches the top-level directory
```

### Regex operators

| Operator | Equivalent |
| --- | --- |
| `~` | `regexp_matches` (partial, case-sensitive) |
| `!~` | `NOT regexp_matches` |
| `~*` / `!~*` | Case-insensitive variants |

**Changed in 2.0:** `~`/`!~` perform **partial** matching (PostgreSQL semantics) and `~*`/`!~*` are supported; earlier, `~` did full matching. The deprecated `SET regex_match_operator_semantics = 'full';` restores full matching via `regexp_full_match`.

## Regular expression functions

DuckDB uses the **RE2** engine. All functions accept optional `options`.

| Function | Example | Result |
| --- | --- | --- |
| `regexp_matches(s, pattern[, options])` | `regexp_matches('anabanana', '(an)*')` | `true` (contains) |
| `regexp_full_match(s, regex[, options])` | `regexp_full_match('anabanana', '(an)*')` | `false` (entire string) |
| `regexp_extract(s, pattern[, group = 0][, options])` | `regexp_extract('abc', '([a-z])(b)', 1)` | `a` (empty string if no match) |
| `regexp_extract(s, pattern, name_list[, options])` | `regexp_extract('2023-04-15', '(\d+)-(\d+)-(\d+)', ['y', 'm', 'd'])` | `{'y': 2023, 'm': 04, 'd': 15}` |
| `regexp_extract_all(s, regex[, group][, options])` | `regexp_extract_all('Peter: 33, Paul:14', '(\w+):\s*(\d+)', 2)` | `[33, 14]` |
| `regexp_extract_all(s, regex, name_list[, options])` | … `['name', 'age']` | list of structs |
| `regexp_replace(s, pattern, replacement[, options])` | `regexp_replace('hello', '[lo]', '-')` | `he-lo` (first match only) |
| `regexp_split_to_array(s, regex[, options])` | `regexp_split_to_array('hello world; 42', ';? ')` | `['hello', 'world', '42']` |
| `regexp_split_to_table(s, regex[, options])` | same | three rows |
| `regexp_escape(s)` | escape special characters (like Python `re.escape`) | |

| Option | Meaning |
| --- | --- |
| `'c'` | Case-sensitive |
| `'i'` | Case-insensitive |
| `'l'` | Match literals, not regex tokens |
| `'m'`, `'n'`, `'p'` | Newline-sensitive (`.` does not match newline) |
| `'s'` | Non-newline-sensitive |
| `'g'` | Global replace (`regexp_replace` only) |

```sql
SELECT regexp_matches('abc', '^a$');                          -- false
SELECT regexp_matches('abc', 'A', 'i');                       -- true (also '(?i)A')
SELECT regexp_matches(E'hello\nworld', 'hello.world', 's');   -- true
SELECT regexp_replace('abc', '(b|c)', 'X', 'g');              -- aXX
SELECT regexp_replace('abc', '(a)(b)', '\2\1');               -- bac
SELECT regexp_extract('ABC', 'abc', 'i');                     -- ABC (options without group: new in 2.0)
```

- `regexp_matches` is optimized to `LIKE`, `prefix` or `suffix` when possible — pass `'c'` for best performance (e.g. `regexp_matches(s, '^hello', 'c')` → `prefix(s, 'hello')`).
- `regexp_extract` with `name_list`: fewer names than groups returns the first groups; more names raises `Binder Error: Not enough capturing groups (3) for provided names (4)`.
- Only 9 capture groups (`\1`–`\9`) are supported in replacements.
- Unlike PostgreSQL's `regexp_substr`, `regexp_extract` returns an empty string (not `NULL`) when nothing matches.
