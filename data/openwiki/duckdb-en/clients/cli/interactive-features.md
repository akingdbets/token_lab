---
type: guide
title: "CLI Interactive Features: Editing, Autocomplete, Highlighting, Friendly CLI, Agent and Safe Mode"
description: How to use the DuckDB CLI interactively — linenoise key bindings, the external editor, Tab autocomplete, syntax and error highlighting colors, dark/light mode, the `_` last-result table, agent mode for AI coding agents (new in 2.0), safe mode, and known CLI issues.
tags: [cli, editing, autocomplete, syntax-highlighting, agent-mode, safe-mode, friendly-cli]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-9ffc8acf97aa47234aa9e6fb
    resource: repo://docs/2.0/clients/cli/agent_mode.md
  - id: openwiki-source-cd9d1ee2303dceeddc5a7c94
    resource: repo://docs/2.0/clients/cli/autocomplete.md
  - id: openwiki-source-b5bddbafb2ebf4be7f6a4d94
    resource: repo://docs/2.0/clients/cli/editing.md
  - id: openwiki-source-c7dd34819fd146cbb21caa33
    resource: repo://docs/2.0/clients/cli/friendly_cli.md
  - id: openwiki-source-dde8e653d9887a8d2738fce0
    resource: repo://docs/2.0/clients/cli/known_issues.md
  - id: openwiki-source-41c51d7bfc03756b3ccfc4a0
    resource: repo://docs/2.0/clients/cli/safe_mode.md
  - id: openwiki-source-74248f51ee8536f6fda217b0
    resource: repo://docs/2.0/clients/cli/syntax_highlighting.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# CLI Interactive Features

The DuckDB CLI is a full interactive shell. This page covers editing, completion, highlighting, convenience features, and the two special modes: **agent mode** and **safe mode**. For starting the CLI and its command-line flags see [CLI Client: Installation, Usage and Command-Line Arguments](overview-and-arguments.md); for the complete dot-command list see [CLI Dot Commands and Output Formats](dot-commands-and-output-formats.md).

## Line editing

The editor is based on [linenoise](https://github.com/antirez/linenoise) with shortcuts modeled on the Emacs mode of readline, available on macOS, Linux and Windows. `.help shortcuts` prints the list inside the CLI.

| Group | Key | Action |
| --- | --- | --- |
| Moving | `Home` / `End` | Beginning / end of buffer |
| | `Ctrl`+`A` / `Ctrl`+`E` | Beginning / end of line |
| | `Ctrl`+`Left` / `Ctrl`+`Right` (or `Alt`+`Left`/`Right`) | Back / forward a word |
| | `Up` / `Down` | Move a line; on first/last line move through history |
| History | `Ctrl`+`P` / `Ctrl`+`N` | Previous / next history entry |
| | `Ctrl`+`R` / `Ctrl`+`S` | Reverse / forward search |
| | `Ctrl`+`Up` / `Ctrl`+`Down` | First / last history entry |
| Changing text | `Ctrl`+`K` | Delete everything after the cursor |
| | `Ctrl`+`U`, `Alt`+`R` | Delete all text |
| | `Ctrl`+`W`, `Alt`+`Backspace` | Delete previous word |
| | `Ctrl`+`D` | Delete next character; on empty buffer end editing |
| | `Alt`+`C` / `Alt`+`L` / `Alt`+`U` | Next word to titlecase / lowercase / uppercase |
| | `Ctrl`+`T` / `Alt`+`T` | Swap characters / words |
| Completing | `Tab`, `Shift`+`Tab`, `Esc`+`Esc` | Complete / cycle forward, cycle back, revert |
| Misc | `Enter`, `Ctrl`+`J` | Execute; if incomplete, insert a newline |
| | `Ctrl`+`G` | Execute; if incomplete, terminate with `;` and execute |
| | `Ctrl`+`C` | Cancel editing or interrupt the running query |
| | `Ctrl`+`O` | Cancel editing of current query |
| | `Ctrl`+`X` | Insert a newline after the cursor |
| | `Ctrl`+`L` | Clear screen |
| | `Ctrl`+`Q`, then click | Move cursor to mouse position |
| | `Ctrl`+`Z` | Suspend CLI (`fg` resumes) |

### External editor

`.edit` or `\e` opens a query in an external editor: alone it edits the previous command, inside a multi-line command it edits the current one. The editor is the first set variable among `DUCKDB_EDITOR`, `EDITOR`, `VISUAL` (in that order), falling back to `vi`.

To use real readline instead, wrap the shell with `rlwrap` (then `Shift`+`Enter` inserts a newline):

```batch
rlwrap --substitute-prompt="D " duckdb -batch
```

## Autocomplete

Context-aware completion comes from the `autocomplete` extension and is triggered with `Tab`; repeat `Tab` to cycle forward, `Shift`+`Tab` to cycle back, `Esc` twice to revert. It completes four groups depending on the cursor position: keywords; table names and table functions; column names and scalar functions; file names.

```sql
SELECT s                          -- completes to student_id
SELECT student_id F               -- completes to FROM
SELECT student_id FROM g          -- completes to grades
SELECT student_id FROM 'data/     -- completes to 'data/grades.csv
```

## Syntax highlighting

Queries are highlighted automatically (macOS, Linux, Windows). Configure colors with `.highlight_colors COMPONENT COLOR [INTENSITY]`, or disable with `.highlight off`.

| Type | Component | Default color |
| --- | --- | --- |
| Keywords | `keyword` | `green` |
| Numeric constants | `numeric_constant` | `yellow` |
| String constants | `string_constant` | `yellow` |
| Comments | `comment` | `gray` |
| Errors | `error` | `red` |
| Continuation | `continuation` | `gray` |
| Continuation (selected) | `continuation_selected` | `green` |

Basic colors supported by all terminals: `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `brightgray`, `gray`, `brightred`, `brightgreen`, `brightyellow`, `brightblue`, `brightmagenta`, `brightcyan`, `white`. Since DuckDB 1.5, 8-bit Xterm colors are also supported; `.display_colors` lists their names. Intensity is `standard`, `bold`, `underline` or `bold_underline`.

```text
.highlight_colors keyword brightred bold
.highlight_colors comment cyan
.highlight_colors continuation_selected brightblue
```

Put such commands in `~/.duckdbrc` to apply them at every start-up.

**Error highlighting:** mismatched brackets and unclosed quotes are highlighted in red. It is disabled automatically for large queries and manually with `.render_errors off`.

## Friendly CLI features

- **Dark/light mode.** The CLI detects the terminal background. Override with `.highlight_mode dark`, `.highlight_mode light` or `.highlight_mode mixed`, or at launch with `duckdb -dark-mode` / `duckdb -light-mode`.
- **Dynamic prompt.** The default prompt is
  `{max_length:50}{highlight_element:prompt_connect}{setting:connect_name_prefix}{highlight_element:prompt}{setting:current_database_and_schema}{color:reset} D `.
  While connected to a remote database with `CONNECT`, `{setting:connect_name_prefix}` shows its name or URI (for example `quack:localhost`); otherwise it is empty. Change it with `.prompt`.
- **Last result as `_`.** The `_` table returns the result of the previous query:

```sql
SELECT 42 AS x;
FROM _;
```

If the last statement returned no result (for example an `UPDATE`), querying `_` fails with `Binder Error: Failed to query last result "_": no result available`.

## Agent mode (new in DuckDB 2.0)

Agent mode renders output for AI coding agents: compact Markdown tables with explicit result limits, machine-readable errors, and progress on `stderr`.

**Activation.** It turns on automatically when all hold: a known AI agent environment variable (such as `AI_AGENT`) is set, stdout is not a terminal, and no output-mode flag (such as `-csv` or `-json`) was passed. Force it with the `-agent` / `-no-agent` arguments or the `DUCKDB_AGENT_MODE` environment variable (`1` on, `0` off); flags take precedence over the variable. `.startup_text none` as the first line of `~/.duckdbrc` hides the startup announcement.

```batch
duckdb -agent -c "SELECT 42 AS answer;"
duckdb -no-agent -c "SELECT 42 AS answer;"
```

**Output.** Results are compact Markdown tables with a footer giving the row count and, when the whole result was read, an order-independent hash. Errors are JSON on `stderr`; query plans and cost estimates are compact; queries reading more than 1,000,000 rows print an estimate line and progress on `stderr`.

**Limits.** By default a result of up to 1,000 rows and 10,000 bytes is rendered whole; larger results show the first and last rows plus the total row count. Cells are truncated at 500 characters. Adjust with:

| Dot command | Meaning |
| --- | --- |
| `.maxrows count` | Rows rendered whole (`-1` for all) |
| `.maxbytes count` | Bytes of rows rendered whole (`0` for all) |
| `.maxcellwidth count` | Characters per cell (`0` for all) |

Without installing anything, `uvx duckdb-cli -c "SELECT 42 AS answer;"` runs the current release where `uv` is present. `.help agent` summarizes agent mode. Useful practices: `SET max_execution_time = milliseconds` to bound runtime, `DESCRIBE query` to get result columns without running it, `SUMMARIZE table`, `.tables`, and `duckdb_functions()` for function docs.

## Safe mode

Enable with `duckdb -safe` or the `.safe_mode` dot command. The CLI may then access only the database file it was originally connected to and may not interact with the host file system:

- Disabled dot commands: `.cd`, `.excel`, `.import`, `.log`, `.once`, `.open`, `.output`, `.read`, `.sh`, `.system` (and `.web`).
- Autocomplete no longer scans the file system.
- The `getenv` function is disabled.
- `enable_external_access` is set to `false`, so `ATTACH` cannot attach a database file, `COPY` cannot read or write files, and `read_csv`, `read_parquet`, `read_json`, etc. cannot read external sources.

Safe mode **cannot be deactivated** within the same session. See [Securing DuckDB](../../operations/security.md) for broader hardening.

## Known issues

On WSL 2 (for example Ubuntu 20.04 and 24.04) and older distributions such as RHEL 8, `max_memory` and `memory_limit` in `duckdb_settings()` may show inaccurate values larger than 1000 PiB (for example `1638.3 PiB`):

```sql
FROM duckdb_settings() WHERE name LIKE '%mem%';
```

In that case set `memory_limit` explicitly (see [Configuration Options, SET and PRAGMA](../../configuration/settings-and-pragmas.md)).
