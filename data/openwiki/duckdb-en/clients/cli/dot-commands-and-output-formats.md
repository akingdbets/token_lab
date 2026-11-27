---
type: reference
title: CLI Dot Commands and Output Formats
description: Reference for DuckDB CLI dot commands (.mode, .output, .once, .tables, .schema, .dump, .import, .manual, .history, .timer, .pager and more) and the available output modes such as duckbox, csv, markdown and json.
tags: [cli, dot-commands, output-formats, duckbox, pager, import, schema]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-da190d4323368399268d272d
    resource: repo://docs/2.0/clients/cli/dot_commands.md
  - id: openwiki-source-97edfabb97c7068a11bff91c
    resource: repo://docs/2.0/clients/cli/output_formats.md
  - id: openwiki-source-0043b9550ae92a50a707f219
    resource: repo://docs/2.0/guides/snippets/importing_duckbox_tables.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# CLI Dot Commands and Output Formats

Dot commands are shell-only commands of the DuckDB CLI client. Start the line with a period immediately followed by the command name; arguments are space separated and may be wrapped in single or double quotes if they contain spaces. Dot commands:

- must be entered on a single line,
- must not have whitespace before the period,
- need no trailing semicolon.

Use `.help` to list them. `.help` accepts a filter string (`.help m`), `-all`, and `.help shortcuts` shows keyboard shortcuts. For how to start the CLI, see [CLI Client: Installation, Usage and Command-Line Arguments](overview-and-arguments.md); for editing and highlighting, see [CLI Interactive Features](interactive-features.md).

## Frequently used dot commands

| Command | Description |
| --- | --- |
| `.about` | Version, description and license information |
| `.auto_format on/off` | Format SQL before execution. Default: `off` |
| `.bail on/off` | Stop after hitting an error. Default: `off` |
| `.cd DIRECTORY` | Change working directory |
| `.changes on/off` | Show number of rows changed by SQL |
| `.columns` / `.rows` | Column-wise / row-wise (default) rendering of results |
| `.databases` | List names and files of attached databases |
| `.decimal_sep SEP`, `.thousand_sep SEP` | Number separators (duckbox mode only) |
| `.dump TABLE` | Render database content as SQL; `TABLE` is a `LIKE` pattern |
| `.echo on/off` | Command echo |
| `.edit` (alias `\e`) | Edit the query in an external editor |
| `.excel` | Show the next result in a spreadsheet; equivalent to `.once -x` |
| `.exit CODE`, `.quit` | Exit (with return code) |
| `.headers on/off` | Header display; does not apply to duckbox mode |
| `.history N` | Show command history (last `N` entries) |
| `.import FILE TABLE` | Import a file into a table; supports `-csv`, `-json`, `-parquet` |
| `.indexes TABLE` | Show index names |
| `.large_number_rendering all/footer/off` | Readable large numbers (duckbox only, default `footer`) |
| `.last` | Re-render the last result without truncation |
| `.log FILE/off` | Logging; `FILE` can be `stderr` / `stdout` |
| `.manual FUNCTION` | Manual page for a SQL function |
| `.maxrows COUNT` | Max rows displayed (default `40`, `-1` = all); duckbox and agent mode |
| `.maxwidth COUNT` | Max width in characters, `0` = terminal width; duckbox only |
| `.maxbytes COUNT`, `.maxcellwidth COUNT` | Limits for agent mode only (`0` = all) |
| `.mode MODE TABLE` | Set the output mode |
| `.multiline` / `.singleline` | Multi-line mode (default) / single-line mode |
| `.nullvalue STRING` | Text used for `NULL`. Default: `NULL` |
| `.once OPTIONS FILE` | Send only the next result to `FILE` |
| `.open OPTIONS FILE` | Close the database and open `FILE`; options `-new`, `-nofollow`, `-readonly`, `-sql` |
| `.output FILE` | Send output to `FILE`, or stdout if omitted |
| `.pager OPTIONS` | Control pager usage |
| `.print STRING...` | Print a literal string |
| `.progress_bar COMPONENT` | Configure progress bar components |
| `.prompt MAIN CONTINUE` | Replace the standard prompts |
| `.read FILE` | Read input (SQL script) from `FILE` |
| `.safe_mode` | Activate safe mode |
| `.schema OPTIONS PATTERN` | Show matching `CREATE` statements |
| `.separator COL ROW` | Change column and row separators |
| `.shell CMD ARGS...` / `.system CMD ARGS...` | Run a command in a system shell |
| `.show` | Show current values of various settings |
| `.startup_text none/version/all` | Start-up text; set it as the first line of `~/.duckdbrc` |
| `.tables TABLE` | List tables (with columns, types, row counts) matching a `LIKE` pattern |
| `.timer on/off DIGITS` | SQL timer with `DIGITS` decimals (default: 3) |
| `.ui_command COMMAND` | Command for the `-ui` argument; default `CALL start_ui()` |
| `.version` | DuckDB version |
| `.web` | Open the query graph of the previous query in a browser; equivalent to `EXPLAIN ANALYZE (FORMAT WEB)`; disabled in safe mode |
| `.width NUM1 NUM2 ...` | Minimum column widths for columnar output |

With `.timer`, statements separated by `;` but not by a newline are measured together. `.connect_command` and `.serve_command` set the commands used by the `-connect` and `-serve` arguments.

**Shorthands:** once a prefix unambiguously identifies a command or argument, the CLI completes it silently, so `.mo ma` equals `.mode markdown`. Avoid shorthands in scripts.

## Writing results to files: `.output` and `.once`

`.output FILE` redirects all subsequent results to the file (each result overwrites the file); `.output` with no argument returns to stdout. `.once` redirects only the next result.

```sql
.mode markdown
.output my_results.md
SELECT 'taking flight' AS output_column;
.output
SELECT 'back to the terminal' AS displayed_column;
```

```sql
.mode csv
.once my_output_file.csv
SELECT 1 AS col_1, 2 AS col_2
UNION ALL
SELECT 10 AS col1, 20 AS col_2;
```

`.once -e` writes to a temporary text file opened in the default editor; `.once -x` writes a CSV opened in the default spreadsheet program. On macOS, `.once |pbcopy` copies results to the clipboard. For SQL-level exports prefer [`COPY ... TO`](../../sql/statements/copy-and-export.md).

## Inspecting the schema

`.tables` lists tables grouped by database and schema, optionally filtered with a `LIKE` pattern:

```sql
CREATE TABLE swimmers AS SELECT 'duck' AS animal;
CREATE TABLE fliers AS SELECT 'duck' AS animal;
CREATE TABLE walkers AS SELECT 'duck' AS animal;
.tables %l%
```

`.schema` prints the `CREATE` statements. **New in DuckDB 2.0:** `.schema` pretty-prints and highlights by default. Use `-no-indent` (alias `-no-format`) for the stored single-line form; `-indent` (alias `-format`) forces pretty-printing.

```sql
.schema -no-indent
```

`.dump` renders schema and data as SQL (for backups or migration). It accepts one or more `LIKE` patterns, and `-newlines` allows unescaped newlines:

```sql
.dump %swim%
```

## History and function manual (new in 2.0)

`.history` and the `shell_history()` table function were introduced in DuckDB 2.0. `shell_history()` returns an `id` and a `sql` column, and is only populated in interactive use:

```sql
.history 10
FROM shell_history();
```

`.manual` (and the `-manual` command-line argument, also new in 2.0) shows signatures, descriptions and examples taken from `duckdb_functions()`. Names may be qualified as `database.schema.function`; each part is a case-insensitive `LIKE` pattern. If nothing matches, similar names are suggested.

```sql
.manual map
.manual list_%
```

```batch
duckdb -manual regexp_extract
```

## Importing data with `.import`

`.import` uses `read_csv`, `read_json` or `read_parquet` with schema auto-detection and creates the target table if it does not exist. The format is given by `-csv`, `-json` or `-parquet`, or inferred from the extension. Extra reader parameters are passed as `-parameter value`:

```sql
.import data.csv my_table
.import data.csv my_table -delimiter "|" -header false
.import data.json my_table -json
```

## Progress bar

The progress bar is controlled by the settings `enable_progress_bar` and `progress_bar_time` (minimum query duration in milliseconds before it appears). `.progress_bar -add` stacks components (calls are additive) and `.progress_bar -clear` removes them:

```sql
SET progress_bar_time = 100;
.progress_bar -add "{align:right}{min_size:20}{color:red}Time: {sql:select (current_time::varchar).split('.')[1]}{color:reset} "
.progress_bar -clear
```

## Highlighting commands

`.highlight on/off` toggles query highlighting; `.highlight_colors COMPONENT COLOR` sets colors for query components (`keyword`, `numeric_constant`, `string_constant`, …) and result components (`layout`, `column_type`, `column_name`, `numeric_value`, `temporal_value`, `string_value`, `footer`). By default results bold column names and grey out `NULL`s and layout; `.highlight_results off` disables result highlighting.

```sql
.highlight_colors keyword red
.highlight_colors column_name yellow bold_underline
```

## Output formats (`.mode`)

`.mode` without arguments prints the current mode (`current output mode: duckbox`).

| Mode | Description |
| --- | --- |
| `ascii` | Columns/rows delimited by 0x1F and 0x1E |
| `box` | Unicode box-drawing tables |
| `csv` | Comma-separated values |
| `column` | Columns (see `.width`) |
| `duckbox` | Feature-rich tables (**default**) |
| `html` | HTML `<table>` |
| `insert TABLE` | SQL `INSERT` statements for `TABLE` |
| `json` / `jsonlines` | JSON array / NDJSON |
| `latex` | LaTeX tabular |
| `line` | One value per line |
| `list` | Values delimited by `\|` |
| `markdown` | Markdown table |
| `quote` | Escaped as for SQL |
| `table` | ASCII-art table |
| `tabs` | Tab-separated |
| `tcl` | TCL list elements |
| `trash` | No output |

Changing the mode resets the separator (`.mode csv` sets `,`); change it afterwards with `.separator "|"`.

### duckbox large-number rendering

`.large_number_rendering` has three levels: `off`, `footer` (default; adds a human-readable line, single-row results only) and `all` (replaces numbers):

```sql
.large_number_rendering footer
SELECT pi() * 1_000_000_000 AS x;   -- shows 3141592653.589793 and (3.14 billion)
```

### Paging

`.pager` has three modes: `automatic` (default, triggered when the result exceeds row/column thresholds), `on` and `off`. Thresholds and the pager command are configurable; the default command can also come from the `DUCKDB_PAGER` or `PAGER` environment variables.

```sql
.pager set_row_threshold 50
.pager set_column_threshold 5
.pager less -RS
```

On Windows Terminal the default `more` utility has incomplete Unicode support; the docs suggest Git for Windows' `less`:

```sql
.pager '"C:\Program Files\Git\usr\bin\less.exe" -R'
```

## Loading duckbox tables back into DuckDB

Duckbox output is not directly importable, but it can be converted to a file separated by `│` (U+2502 "Box Drawings Light Vertical", not `|`) with `sed` (Linux, macOS, WSL) and read with the CSV reader:

```bash
echo -n > duckbox-cleaned.csv
sed -n "2s/^│ *//;s/ *│$//;s/ *│ */│/p;2q" duckbox.csv >> duckbox-cleaned.csv
sed "1,4d;\$d;s/^│ *//;s/ *│$//;s/ *│ */│/g" duckbox.csv >> duckbox-cleaned.csv
```

```sql
FROM read_csv('duckbox-cleaned.csv', delim = '│');
```

The `shellfs` community extension can run the same pipeline inside `read_csv` (and a table macro `read_duckbox(path)` can wrap it), but it comes without support or guarantees and its inputs must be sanitized. Limitations: cells must not contain `│`, cell spaces are trimmed, and only types supported by the CSV sniffer are parsed (nested values become `VARCHAR`).
