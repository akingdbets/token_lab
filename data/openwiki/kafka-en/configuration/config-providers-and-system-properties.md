---
type: configuration-reference
title: Configuration Providers and System Properties
description: Externalizing secrets and settings with Kafka ConfigProviders (DirectoryConfigProvider, EnvVarConfigProvider, FileConfigProvider, custom providers) using config.providers and ${alias:path:key} placeholders, plus the security-related JVM system properties Kafka supports and their defaults and version notes.
tags: [configuration, config-providers, secrets, system-properties, security, connect]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-aa7637464d865f25a8f05ff0
    resource: repo://docs/configuration/configuration-providers.md
  - id: openwiki-source-e1050d0522ed02f820eba9fc
    resource: repo://docs/configuration/system-properties.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Configuration Providers and System Properties

## Configuration providers

Configuration providers load configuration values — typically **passwords, API keys and other credentials** — from external sources instead of writing them into properties files. They work in any Kafka component that accepts `config.providers`: brokers, producers, consumers, admin clients, Kafka Connect workers and connectors, and Streams applications.

Options:

- **Built-in providers** (package `org.apache.kafka.common.config.provider`): `DirectoryConfigProvider`, `EnvVarConfigProvider`, `FileConfigProvider`.
- **Custom provider:** implement the `ConfigProvider` interface, package it as a JAR, put it on the classpath and reference its class.

### Declaring providers

```properties
config.providers=provider1,provider2
config.providers.provider1.class=com.example.Provider1
config.providers.provider2.class=com.example.Provider2

# provider parameters
config.providers.<provider_alias>.param.<name>=<value>
```

Example custom provider:

```properties
config.providers=customProvider
config.providers.customProvider.class=com.example.customProvider
config.providers.customProvider.param.param1=value1
config.providers.customProvider.param.param2=value2
```

### DirectoryConfigProvider

Reads values from files in a directory: **each file is a key and its content is the value** — handy for mounted secret directories (e.g. Kubernetes secrets). Restrict access with `allowed.paths` (comma-separated; all paths allowed if unset).

```properties
config.providers=dirProvider
config.providers.dirProvider.class=org.apache.kafka.common.config.provider.DirectoryConfigProvider
config.providers.dirProvider.param.allowed.paths=/path/to/dir1,/path/to/dir2
```

Placeholder: `${dirProvider:<path_to_file>:<file_name>}`

### EnvVarConfigProvider

Reads values from **environment variables** — useful in containers to load certificates or JAAS configuration mapped from secrets. No parameters are required; restrict which variables may be read with `allowlist.pattern` (a regular expression).

```properties
config.providers=envVarProvider
config.providers.envVarProvider.class=org.apache.kafka.common.config.provider.EnvVarConfigProvider
config.providers.envVarProvider.param.allowlist.pattern=^MY_ENVAR1_.*
```

Placeholder: `${envVarProvider:<enVar_name>}`

### FileConfigProvider

Reads values from a **single properties file**, e.g. a mounted file. Restrict paths with `allowed.paths`.

```properties
config.providers=fileProvider
config.providers.fileProvider.class=org.apache.kafka.common.config.provider.FileConfigProvider
config.providers.fileProvider.param.allowed.paths=/path/to/config1,/path/to/config2
```

Placeholder: `${fileProvider:<path_and_filename>:<property>}`

### Example: database credentials for a Connect connector

`connector-credentials.properties`:

```properties
dbUsername=my-username
dbPassword=my-password
```

Worker configuration:

```properties
config.providers=fileProvider
config.providers.fileProvider.class=org.apache.kafka.common.config.provider.FileConfigProvider
```

Connector configuration:

```properties
database.user=${fileProvider:/path/to/connector-credentials.properties:dbUsername}
database.password=${fileProvider:/path/to/connector-credentials.properties:dbPassword}
```

At runtime the provider reads and substitutes the values, so the secrets never appear in the connector config stored by Connect. The Connect security model recommends exactly this for secrets in configuration (see [Security model](../security/listeners-and-security-overview.md)).

## JVM system properties

Some behaviour is controlled by Java system properties, set with `-D` on the JVM running the Kafka component (for the `bin/*.sh` scripts, typically via `KAFKA_OPTS`):

```bash
export KAFKA_OPTS="-Dorg.apache.kafka.automatic.config.providers=none"
bin/kafka-server-start.sh config/server.properties
```

| Property | Since | Default | Purpose |
| --- | --- | --- | --- |
| `org.apache.kafka.sasl.oauthbearer.allowed.files` | 4.1.0 | empty list | Files the SASL OAUTHBEARER plugin may read (e.g. token or private key files). |
| `org.apache.kafka.sasl.oauthbearer.allowed.urls` | 4.0.0 | empty list | URLs allowed as OAUTHBEARER token or JWKS endpoints. |
| `org.apache.kafka.disallowed.login.modules` | 3.4.0 (deprecated 4.2.0) | `com.sun.security.auth.module.JndiLoginModule,com.sun.security.auth.module.LdapLoginModule` | Login modules forbidden in SASL JAAS configs. |
| `org.apache.kafka.allowed.login.modules` | 4.2.0 | (none) | Allow-list of login modules for JAAS; takes precedence over the disallow list. |
| `org.apache.kafka.automatic.config.providers` | 3.8.0 | all built-in providers enabled | Which `ConfigProvider` classes may be loaded automatically. |

Examples:

```bash
# OAUTHBEARER: allow specific files and URLs
-Dorg.apache.kafka.sasl.oauthbearer.allowed.files=/tmp/token,/tmp/private_key.pem
-Dorg.apache.kafka.sasl.oauthbearer.allowed.urls=https://www.example.com,file:///tmp/token

# re-enable JNDI/LDAP login modules (validate configs; see CVE-2023-25194)
-Dorg.apache.kafka.disallowed.login.modules=

# disallow more modules — keep JndiLoginModule in the list
-Dorg.apache.kafka.disallowed.login.modules=com.sun.security.auth.module.JndiLoginModule,com.ibm.security.auth.module.LdapLoginModule,com.ibm.security.auth.module.Krb5LoginModule

# disable all automatic config providers (recommended with untrusted config sources; CVE-2024-31141)
-Dorg.apache.kafka.automatic.config.providers=none

# allow only selected providers
-Dorg.apache.kafka.automatic.config.providers=org.apache.kafka.common.config.provider.FileConfigProvider,org.apache.kafka.common.config.provider.EnvVarConfigProvider
```

Notes:

- `org.apache.kafka.disallowed.login.modules` is **deprecated** and will be removed; prefer the stricter allow-list `org.apache.kafka.allowed.login.modules`. If both are set, the allow-list wins.
- Because OAUTHBEARER file and URL allow-lists default to empty, configurations that point at token files or JWKS endpoints must set the matching system property (see [SASL/OAUTHBEARER](../security/sasl-authentication.md)).

## Related pages

- [Client configuration](client-configuration.md) (`config.providers` on clients)
- [Kafka Connect: running workers](../connect/overview-and-running.md)
- [SASL authentication](../security/sasl-authentication.md)
- [Security overview](../security/listeners-and-security-overview.md)
