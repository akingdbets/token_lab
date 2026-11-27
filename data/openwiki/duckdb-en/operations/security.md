---
type: guide
title: Securing DuckDB and Embedding It Safely
description: DuckDB's security model and hardening settings — treating SQL and API inputs as code, sandboxing, restricting file access (enable_external_access, disabled_filesystems, allowed_directories, allowed_paths), locking configuration, secret redaction, extension signature levels and repositories, Quack servers, prepared statements against SQL injection, resource limits, and why not to embed the CLI.
tags: [security, enable-external-access, allowed-directories, lock-configuration, extensions, sql-injection, sandboxing, embedding]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-081ceda7a8b69a4ba9453c75
    resource: repo://docs/2.0/operations_manual/securing_duckdb/embedding_duckdb.md
  - id: openwiki-source-cdac8c466541064d3f6bc465
    resource: repo://docs/2.0/operations_manual/securing_duckdb/overview.md
  - id: openwiki-source-fae2bcd4f0ba2312f1af2fef
    resource: repo://docs/2.0/operations_manual/securing_duckdb/securing_extensions.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Securing DuckDB and Embedding It Safely

DuckDB can read and write files, access the network, load extensions and use system resources with the **full privileges of the user running it**. The right configuration depends on your threat model. All settings below are **defense-in-depth**, not a substitute for sandboxing.

## Untrusted input

**Untrusted SQL:** treat SQL like Bash or Python code — never execute SQL from untrusted sources without sandboxing. Options: duckdb-wasm, an isolated container with restricted capabilities, a VM or minimal-privilege process, OS-level sandboxing, network isolation (to prevent exfiltration), and application-level query timeouts. Sandboxing also protects against denial of service: malicious inputs can exhaust memory, disk, CPU or network.

**Untrusted non-SQL input:** APIs such as the Python relational API take file paths, table/column names and filter expressions. A controlled path in `duckdb.read_csv(path)` can read `/etc/passwd` or remote URLs; filter expressions may contain subqueries with arbitrary SQL. Validate and sanitize inputs and apply the same sandboxing.

**SQL injection:** when you control the query structure but accept untrusted values, use [prepared statements](../sql/query-syntax/select-from-where.md) instead of string concatenation:

```python
import duckdb
# avoid:
duckdb.execute("SELECT * FROM (VALUES (32, 'a'), (42, 'b')) t(x) WHERE x = " + str(42)).fetchall()
# use:
duckdb.execute("SELECT * FROM (VALUES (32, 'a'), (42, 'b')) t(x) WHERE x = ?", [42]).fetchall()
```

## Restricting file access

DuckDB can list directories and read arbitrary files, e.g. `SELECT * FROM read_csv('/etc/passwd', sep = ':');`.

**Disable specific file systems:**

```sql
SET disabled_filesystems = 'LocalFileSystem';
```

Only settable with `SET` on a running database (not as a startup option); it cannot be undone until restart.

**Disable all external access:**

```sql
SET enable_external_access = false;
```

Then `ATTACH` cannot attach database files, `COPY` cannot read/write files, and `read_csv`, `read_parquet`, `read_json`, etc. cannot read external sources (external-resource statements and `getenv` are refused too).

**Allow-lists:** `allowed_directories` and `allowed_paths` remain accessible even with external access disabled — for **both reading and writing** (they are not read-only):

```sql
SET allowed_directories = ['/tmp'];
SET enable_external_access = false;
FROM read_csv('test.csv');
-- Permission Error: Cannot access file "test.csv" - file system operations are disabled by configuration
```

Entries can be remote URLs (`s3://⟨bucket⟩/⟨prefix⟩/`, `https://⟨host⟩/⟨file⟩`), but the file system for the scheme must already be registered. **Order matters and cannot be changed later:** after `enable_external_access = false`, the allow-lists are frozen (`Cannot change allowed_directories when enable_external_access is disabled`), and after `LocalFileSystem` is disabled no extension can be loaded. A working sequence for an instance restricted to one S3 prefix:

```sql
LOAD httpfs;
SET allowed_directories = ['s3://⟨bucket⟩/⟨prefix⟩/'];
SET enable_external_access = false;
SET disabled_filesystems = 'LocalFileSystem';
SET lock_configuration = true;
```

For HTTPS, `httpfs` reads its CA bundle from the local file system; once local access is restricted this fails with `Cannot read a CA certificate bundle ...` unless the bundle was loaded before.

**CLI safe mode:** `duckdb -safe` or `.safe_mode` blocks access to files other than the opened database (see [CLI Interactive Features](../clients/cli/interactive-features.md#safe-mode)).

## Locking configuration

Security-related settings **lock themselves**: you can restrict but not re-enable without a restart, e.g. `SET allow_community_extensions = true` after disabling fails with `Cannot change allow_community_extensions setting while database is running`. Other settings (like resource limits) do not, so lock everything after setup:

```sql
SET allowed_configs = ['memory_limit', 'threads'];   -- optionally keep some settings changeable
SET lock_configuration = true;
```

## Secrets

`duckdb_secrets()` redacts sensitive values by default. `allow_unredacted_secrets` can only be set at instantiation (startup config, or CLI `-unredacted`); `SET` at runtime fails. Queries can use any secret in the Secrets Manager — e.g. a secret with write access to an S3 bucket lets queries write there. Persistent secrets are stored unencrypted with mode `600`. The secret directory (default `~/.duckdb/stored_secrets`) is opened on **first use** of secrets, not at open time; if that happens after `enable_external_access = false`, reading persistent secrets fails. See [Secrets Manager](../configuration/secrets-manager.md).

## Extensions

Extensions run with the DuckDB process's privileges. Every load checks the binary's signature. Categories: signed with a `core` key (vetted by the DuckDB team), signed with a `community` key (Community Extensions repository), signed with a key pinned by a custom extension repository (trusted only for that repository), or unsigned.

| Usable extensions | Configuration |
| --- | --- |
| `core` only | `SET allow_community_extensions = false` |
| `core` and `community` | **Default** |
| Any, including unsigned | `allow_unsigned_extensions = true` **at startup** (CLI `-unsigned`); cannot change at runtime |

- Community extensions are not reviewed (source must be available; DuckDB builds, signs and distributes them) — they execute third-party code. For services running untrusted SQL, disable them.
- **Custom extension repositories (new in 2.0.0):** DuckDB checks only that extensions are signed with the keys pinned at `CREATE EXTENSION REPOSITORY`. `allow_extension_repositories` controls which repositories can be added/trusted (`'hosts'` default, `'allowed'`, `'hosts_only'`, `'forbidden'`); `extension_repository_directory` is the trust anchor and, while signatures are checked, can only be set at startup.
- Disable automatic installation/loading of known extensions:

```sql
SET autoinstall_known_extensions = false;
SET autoload_known_extensions = false;
SET allow_extension_repositories = 'forbidden';   -- only DuckDB-signed extensions
SET lock_configuration = true;
```

Extension management statements are on [Extensions: INSTALL, LOAD, Updates](../configuration/extensions.md).

## Serving DuckDB over the network

With the `quack` extension (`CALL quack_serve(...)` or `duckdb -serve`), a server exposes the instance's full SQL surface — read and write access to every visible table — to any client holding the token. It binds to `localhost` by default; protect remote access accordingly (see [Connecting, Persistence and Concurrency](../connect/connecting-and-concurrency.md)).

## Constraining resources and privileges

```sql
SET threads = 4;
SET memory_limit = '4GB';
SET max_temp_directory_size = '4GB';
SET max_execution_time = 5000;   -- new in 2.0, milliseconds
```

Never run DuckDB as root (e.g. via `sudo`). Report vulnerabilities confidentially via GitHub security advisories.

## Embedding DuckDB

The CLI is meant for interactive use and has features that can be abused — for example `.sh ls` runs arbitrary shell commands (only in the CLI). **Do not embed DuckDB by shelling out to the CLI**; use a client library such as Python, R or Java instead (see [Python Client](../clients/python/getting-started.md)).
