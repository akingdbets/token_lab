---
type: reference
title: Secrets Manager and CREATE SECRET
description: Manage credentials for S3, GCS, R2, Azure, HTTP, Hugging Face, PostgreSQL, MySQL and other services with DuckDB's Secrets Manager — secret types and providers (CONFIG, credential_chain), temporary, persistent and connection-scoped secrets (new in 2.0), scopes and which_secret, listing with duckdb_secrets() and deleting with DROP SECRET.
tags: [secrets, create-secret, s3, credentials, persistent-secrets, scope, security]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-b1b2d7f3d344c758fe9898c9
    resource: repo://docs/2.0/configuration/secrets_manager.md
  - id: openwiki-source-e818cee0be686fbefad30419
    resource: repo://docs/2.0/sql/statements/create_secret.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Secrets Manager and CREATE SECRET

The **Secrets Manager** gives one interface for credentials across every backend that needs them. Secrets are **typed** (by service), can be **scoped** to storage prefixes (so one query can join data from different organizations with different credentials), and can be **persisted** so they need not be re-entered for every DuckDB session.

Typical use: create an `s3` secret, then read remote files as described in [Importing Data Overview, File Access](../data/overview-and-file-access.md).

## Secret types

Most types are registered by extensions, not built in:

| Secret type | Service / protocol | Extension |
| --- | --- | --- |
| `azure` | Azure Blob Storage | `azure` |
| `ducklake` | DuckLake | `ducklake` |
| `gcs` | Google Cloud Storage | `httpfs` |
| `http` | HTTP and HTTPS | `httpfs` |
| `huggingface` | Hugging Face | `httpfs` |
| `iceberg` | Iceberg REST Catalog | `httpfs`, `iceberg` |
| `mysql` | MySQL | `mysql` |
| `postgres` | PostgreSQL | `postgres` |
| `quack` | Quack | `quack` |
| `r2` | Cloudflare R2 | `httpfs` |
| `s3` | AWS S3 | `httpfs` |
| `aws` | AWS | `aws` |

## Secret providers

A **secret provider** is the mechanism that generates the secret. For `S3`, `GCS`, `R2` and `AZURE`, DuckDB supports two providers:

- `CONFIG` — you pass all configuration in `CREATE SECRET`. **This is the default** when no provider is given.
- `credential_chain` — DuckDB tries to fetch credentials automatically (e.g. from the environment).

## Creating secrets

### Temporary secrets (default)

Temporary secrets live in memory for the lifetime of the DuckDB instance.

```sql
CREATE SECRET my_secret (
    TYPE s3,
    KEY_ID 'my_secret_key',
    SECRET 'my_secret_value',
    REGION 'my_region'
);
```

This implicitly uses the `CONFIG` provider.

### Persistent secrets

```sql
CREATE PERSISTENT SECRET my_persistent_secret (
    TYPE s3,
    KEY_ID 'my_secret_key',
    SECRET 'my_secret_value'
);
```

- Written by default to `~/.duckdb/stored_secrets` and automatically loaded at startup.
- Stored in **unencrypted binary format**, protected by file permissions (mode `600`), similar to SSH private keys: only the user running DuckDB can read and write them.
- Change the directory with `SET secret_directory = 'path/to/my_secrets_dir';`. This setting applies only to the current instance and is **not persisted** — set it again in each new instance before creating or using secrets from that directory. Setting `home_directory` has **no effect** on where secrets are stored.

### Connection-scoped secrets (new in DuckDB 2.0)

A secret can be stored in connection-scoped storage so only queries on the same connection see it:

```sql
CREATE SECRET my_secret IN connection (
    TYPE s3,
    KEY_ID 'my_secret_key',
    SECRET 'my_secret_value'
);
```

Connection-scoped secrets are always temporary, which lets different connections hold secrets of the same type and scope without clashing.

> **Warning:** in the [CLI client](../clients/cli/overview-and-arguments.md), `CREATE SECRET` statements are stored in the DuckDB history (`~/.duckdb_history`) as plain text.

## Scopes: several secrets for one service

The optional `SCOPE` is a path prefix. When DuckDB needs a secret for a path, it compares scopes to the path and, if several match, **chooses the longest prefix**.

```sql
CREATE SECRET secret1 (
    TYPE s3,
    KEY_ID 'my_secret_key1',
    SECRET 'my_secret_value1',
    SCOPE 's3://⟨my-bucket⟩'
);

CREATE SECRET secret2 (
    TYPE s3,
    KEY_ID 'my_secret_key2',
    SECRET 'my_secret_value2',
    SCOPE 's3://⟨my-other-bucket⟩'
);
```

A query on `s3://⟨my-other-bucket⟩/something` uses `secret2` automatically. Check which secret applies with `which_secret(path, type)`:

```sql
FROM which_secret('s3://⟨my-other-bucket⟩/file.parquet', 's3');
```

## Listing and deleting secrets

```sql
FROM duckdb_secrets();                         -- sensitive values are redacted
DROP PERSISTENT SECRET my_persistent_secret;
```

`DROP SECRET` removes temporary secrets and `DROP PERSISTENT SECRET` removes persisted ones. Redaction can be disabled only deliberately: the CLI `-unredacted` flag sets `allow_unredacted_secrets = true` (see [CLI arguments](../clients/cli/overview-and-arguments.md)). Metadata functions such as `duckdb_secrets()` are covered in [DESCRIBE, SHOW, SUMMARIZE and Metadata Functions](../sql/statements/inspection-and-metadata.md).

## Related settings and security

- Secrets used with `ATTACH` for PostgreSQL/MySQL/Quack databases: see [ATTACH, DETACH, USE and Multiple Databases](../connect/attach-and-multiple-databases.md).
- Locking down secret access, `allowed_directories`, and `enable_external_access`: see [Securing DuckDB and Embedding It Safely](../operations/security.md).
