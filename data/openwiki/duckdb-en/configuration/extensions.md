---
type: reference
title: "Extensions: INSTALL, LOAD, Updates and External Resources"
description: How to install and load DuckDB extensions (INSTALL, LOAD, the new INSTALL AND LOAD), install from the community or custom repositories, keep them current with UPDATE EXTENSIONS, rely on backup extension repositories, manage external resources (CREATE/REGISTER/DESTROY EXTERNAL RESOURCE, new in 2.0), and use the fts full-text search extension.
tags: [extensions, install, load, update-extensions, community-extensions, external-resources, full-text-search, fts]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-fc0cd81337af40257f576533
    resource: repo://docs/2.0/guides/sql_features/full_text_search.md
  - id: openwiki-source-fd4f3d7712afd819e4eea51c
    resource: repo://docs/2.0/operations_manual/backup_extension_repositories.md
  - id: openwiki-source-2112bf50d29d3630ec416254
    resource: repo://docs/2.0/sql/statements/create_external_resource.md
  - id: openwiki-source-ac9784f24fca01b75eeeb14c
    resource: repo://docs/2.0/sql/statements/destroy_external_resource.md
  - id: openwiki-source-daadf50f58fd72e49f6fa9a4
    resource: repo://docs/2.0/sql/statements/load_and_install.md
  - id: openwiki-source-dc77727f5b92dd0c34c999ad
    resource: repo://docs/2.0/sql/statements/register_external_resource.md
  - id: openwiki-source-7798bdd3ad66c48ab1ae7471
    resource: repo://docs/2.0/sql/statements/update_extensions.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Extensions: INSTALL, LOAD, Updates and External Resources

Much of DuckDB's functionality (remote file systems, spatial, full-text search, …) ships as extensions. This page covers the SQL statements for managing them. Security implications (signatures, unsigned extensions, `-unsigned`) are on [Securing DuckDB and Embedding It Safely](../operations/security.md).

## `INSTALL`

`INSTALL` downloads an extension so it can be loaded.

```sql
INSTALL httpfs;
INSTALL h3 FROM community;
```

## `LOAD`

`LOAD` loads an **installed** extension into the current session. It does not install: if the extension is missing, `LOAD` fails and asks you to run `INSTALL` first. (When a query uses a function or feature of a known core extension, **autoloading** installs and loads it automatically.)

```sql
LOAD httpfs;
LOAD spatial;
LOAD my_ext FROM my_repo;     -- installed from a custom extension repository
```

## `INSTALL AND LOAD` (new in DuckDB 2.0)

Installs and loads in one step, equivalent to `INSTALL` followed by `LOAD`; the install step is skipped if already installed, and the load step if already loaded. It accepts the same clauses as `INSTALL`: a `FORCE` prefix, a `FROM` repository clause, and a `VERSION` clause.

```sql
INSTALL AND LOAD spatial;
INSTALL AND LOAD h3 FROM community;
FORCE INSTALL AND LOAD httpfs FROM core_nightly;
```

From clients: the CLI runs these as ordinary SQL; the Python client also offers `con.install_extension("h3", repository="community")` and `con.load_extension("h3")` (see [Python Client: Getting Started](../clients/python/getting-started.md)). The CLI pip package installs extensions as extras: `pip install "duckdb-cli[httpfs]"`.

## `UPDATE EXTENSIONS`

Synchronizes locally installed extensions with the repository that published them — the recommended way to get extension fixes and features.

```sql
UPDATE EXTENSIONS;                          -- all extensions for this DuckDB version
UPDATE EXTENSIONS (name_a, name_b, name_c); -- selected extensions
```

The result lists each extension, its repository and the update result.

- Extensions **cannot be reloaded at runtime**; restart the process to use updated versions.
- Statically linked extensions (in official builds: `json`, `parquet`, `icu`) are not updated.
- **Since DuckDB v2.0.1**, `UPDATE EXTENSIONS;` also checks extensions installed from custom repositories; if one extension is installed from several repositories, each copy is checked against its own.
- A **named** update searches only the default extension directory; to update a copy from a custom repository run `FORCE INSTALL ⟨extension_name⟩ FROM ⟨repository_name⟩;`.

How it works: DuckDB stores the ETag and sends a conditional GET, so repeated calls are cheap when nothing changed. Changed extensions are reinstalled, e.g. `UPDATE EXTENSIONS (name_a, name_b, name_c)` with `name_a` and `name_c` changed runs `FORCE INSTALL name_a; FORCE INSTALL name_c;`.

## Backup extension repositories

| Repository | Primary server | Backup server |
| --- | --- | --- |
| `core` | `http://extensions.duckdb.org` | `http://extensions.duckdb-backup.org` |
| `community` | `http://community-extensions.duckdb.org` | `http://community-extensions.duckdb-backup.org` |

Backups serve byte-identical binaries, so signature checks are unaffected. Fallback is **automatic**: if the primary is unreachable or returns a 5xx error, `INSTALL` retries from the backup with no configuration. A 4xx error (e.g. a non-existent extension) is reported directly. Fallback only applies to the built-in `core` and `community` repositories — repositories set via `custom_extension_repository` or `INSTALL ... FROM '⟨url⟩'` are used as-is — and the recorded origin stays `core` or `community`. To always use the backup for core extensions:

```sql
SET custom_extension_repository = 'http://extensions.duckdb-backup.org';
```

## External resources (new in DuckDB 2.0.0)

External resources let DuckDB provision, adopt and tear down underlying resources (such as a database server) of a registered **external resource type**, tracked as named **resource registrations**. All three statements are refused when `enable_external_access` is `false` (`Permission Error: External resources are disabled through configuration`).

```sql
CREATE EXTERNAL RESOURCE ⟨type⟩ AS ⟨name⟩ [(⟨option⟩ [⟨value⟩], ...)];
REGISTER EXTERNAL RESOURCE ⟨type⟩ AS ⟨name⟩ FROM ⟨handle⟩;
DESTROY EXTERNAL RESOURCE ⟨name⟩;
```

- `CREATE` calls the type's create callback, then its status callback until it reports `ready`, and records the reported handle and endpoint. Options are passed as a `MAP(VARCHAR, VARCHAR)` with lowercase names.
- `REGISTER` adopts an existing resource by its handle (a `MAP(VARCHAR, VARCHAR)`) without calling the create callback; it is torn down like a created one.
- `DESTROY` calls the type's destroy callback and removes the registration.
- Related: `ATTACH TO EXTERNAL RESOURCE` / `CONNECT TO EXTERNAL RESOURCE` use the endpoint ([ATTACH](../connect/attach-and-multiple-databases.md), [CONNECT](../connect/connecting-and-concurrency.md)), and `SHOW EXTERNAL RESOURCES` lists registrations.

```sql
CREATE MACRO dt_create(p) AS TABLE SELECT MAP {'id': 'd1'} AS handle;
CREATE MACRO dt_status(h) AS TABLE
    SELECT 'ready' AS state, MAP {'uri': ':memory:', 'attached_db_type': 'duckdb'} AS result;
CREATE MACRO dt_destroy(h) AS TABLE SELECT 'gone' AS status;
CALL register_external_resource_type(
    'test.dotted.type',
    kind := 'catalog',
    create_function := 'dt_create',
    status_function := 'dt_status',
    destroy_function := 'dt_destroy'
);
CREATE EXTERNAL RESOURCE test.dotted.type AS created;
SELECT name, type FROM (SHOW EXTERNAL RESOURCES);
DESTROY EXTERNAL RESOURCE created;
```

Rules and errors:

| Situation | Result |
| --- | --- |
| Missing `AS name` | `Binder Error: EXTERNAL RESOURCE requires a name (AS <name>)` |
| Unquoted type names | Folded to lowercase; unregistered → `unknown resource type` |
| Characters other than letters, digits, `_`, `.`, `-` | Must be a string literal, e.g. `'mem@local'` (else parser error) |
| Duplicate registration name | `external resource "r" is already registered` (names are unique per instance) |
| Type without status callback | Cannot provision (`has no status function`) |
| `catalog` type whose status result lacks `uri` | Error (`missing 'uri' in its status result`) |
| `DESTROY` of an unknown name | `not registered` error |

## Example extension: full-text search (`fts`)

The `fts` extension builds a full-text index for fast word search with Okapi BM25 ranking.

```sql
CREATE TABLE corpus AS
    SELECT * FROM 'https://blobs.duckdb.org/data/shakespeare.parquet';

PRAGMA create_fts_index('corpus', 'line_id', 'text_entry');   -- table, unique id column, indexed column(s)

SELECT *
FROM (
    SELECT
        fts_main_corpus.match_bm25(line_id, 'butter') AS score,
        line_id, play_name, speaker, text_entry
    FROM corpus
) sq
WHERE score IS NOT NULL
ORDER BY score DESC;
```

Rows with no match get a `NULL` score. The table needs a unique key column. Unlike ordinary indexes, full-text indexes **do not auto-update** when data changes: run `PRAGMA drop_fts_index('corpus')` and recreate the index. For ordinary ART indexes see [Schema Design, Indexes and Join Performance](../performance/schema-indexes-and-joins.md).
