---
type: security-guide
title: Authentication with SASL and Delegation Tokens
description: Configuring SASL authentication in Kafka — JAAS for brokers and clients (sasl.jaas.config, KafkaServer/KafkaClient sections, precedence), SASL_PLAINTEXT vs SASL_SSL, GSSAPI/Kerberos, PLAIN, SCRAM-SHA-256/512 credential management, OAUTHBEARER for development and production (JWKS validation, client_credentials with secret or assertion, jwt-bearer), token refresh, enabling multiple mechanisms, switching mechanisms in a running cluster, and delegation tokens.
tags: [security, sasl, kerberos, scram, oauthbearer, jaas, delegation-tokens]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-6811d2a96926ebbec76502d6
    resource: repo://docs/security/authentication-using-sasl.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Authentication with SASL and Delegation Tokens

SASL runs over plaintext or TLS: listeners use `SASL_PLAINTEXT` or `SASL_SSL` (the latter also requires [SSL configuration](ssl-encryption-and-authentication.md)). Mechanisms: **GSSAPI (Kerberos)**, **PLAIN**, **SCRAM-SHA-256**, **SCRAM-SHA-512**, **OAUTHBEARER**. Listener basics: [Security overview](listeners-and-security-overview.md).

## JAAS configuration

Kafka uses JAAS for SASL.

### Brokers

- Static JAAS file section **`KafkaServer`** — covers broker SASL settings including the client side of inter-broker connections. With several SASL listeners, prefix with the lower-case listener name, e.g. `sasl_ssl.KafkaServer`.
- Or the broker property **`listener.name.{listenerName}.{saslMechanism}.sasl.jaas.config`** (one login module per value; one property per mechanism):

```properties
listener.name.sasl_ssl.scram-sha-256.sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
    username="admin" \
    password="admin-secret";
listener.name.sasl_ssl.plain.sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required \
    username="admin" \
    password="admin-secret" \
    user_admin="admin-secret" \
    user_alice="alice-secret";
```

Precedence: (1) `listener.name.{listenerName}.{saslMechanism}.sasl.jaas.config`, (2) `{listenerName}.KafkaServer` section, (3) `KafkaServer` section.

Pass a static file with `-Djava.security.auth.login.config=/etc/kafka/kafka_server_jaas.conf`.

### Clients

- **Preferred:** the client property `sasl.jaas.config` — no file needed, and different producers/consumers in one JVM can use different credentials. It wins over `java.security.auth.login.config` if both are set.
- **Static file:** a `KafkaClient` section passed via `-Djava.security.auth.login.config=/etc/kafka/kafka_client_jaas.conf` (one user for all connections in the JVM):

```text
KafkaClient {
    com.sun.security.auth.module.Krb5LoginModule required
    useKeyTab=true
    storeKey=true
    keyTab="/etc/security/keytabs/kafka_client.keytab"
    principal="kafka-client-1@EXAMPLE.COM";
};
```

SASL is supported by the Java producer/consumer (not the old API). **Use FQDNs** in `bootstrap.servers` and brokers' `advertised.listeners`: clients may do reverse DNS lookups, which can make SASL handshakes slow otherwise.

### Broker basics

```properties
listeners=SASL_PLAINTEXT://host.name:port
# if brokers also authenticate each other with SASL
security.inter.broker.protocol=SASL_PLAINTEXT   # or SASL_SSL
```

## SASL/GSSAPI (Kerberos)

**Prerequisites:** a Kerberos server (reuse your organization's, e.g. Active Directory); a principal per broker and per OS user/client; FQDN-resolvable hosts. With your own KDC:

```bash
$ sudo /usr/sbin/kadmin.local -q 'addprinc -randkey kafka/{hostname}@{REALM}'
$ sudo /usr/sbin/kadmin.local -q "ktadd -k /etc/security/keytabs/{keytabname}.keytab kafka/{hostname}@{REALM}"
```

**Broker** (`kafka_server_jaas.conf`, one keytab per broker, readable by the Kafka OS user):

```text
KafkaServer {
    com.sun.security.auth.module.Krb5LoginModule required
    useKeyTab=true
    storeKey=true
    keyTab="/etc/security/keytabs/kafka_server.keytab"
    principal="kafka/kafka1.hostname.com@EXAMPLE.COM";
};
```

```text
-Djava.security.krb5.conf=/etc/kafka/krb5.conf
-Djava.security.auth.login.config=/etc/kafka/kafka_server_jaas.conf
```

```properties
listeners=SASL_PLAINTEXT://host.name:port
security.inter.broker.protocol=SASL_PLAINTEXT
sasl.mechanism.inter.broker.protocol=GSSAPI
sasl.enabled.mechanisms=GSSAPI
sasl.kerberos.service.name=kafka   # matches the broker principal's primary
```

**Client:**

```properties
sasl.jaas.config=com.sun.security.auth.module.Krb5LoginModule required \
    useKeyTab=true \
    storeKey=true \
    keyTab="/etc/security/keytabs/kafka_client.keytab" \
    principal="kafka-client-1@EXAMPLE.COM";
security.protocol=SASL_PLAINTEXT   # or SASL_SSL
sasl.mechanism=GSSAPI
sasl.kerberos.service.name=kafka
```

For CLI tools after `kinit`: `sasl.jaas.config=com.sun.security.auth.module.Krb5LoginModule required useTicketCache=true;`. Optionally pass `-Djava.security.krb5.conf=/etc/kafka/krb5.conf`. Principal names map to short names via `sasl.kerberos.principal.to.local.rules` ([ACLs](authorization-and-acls.md#saslkerberos)).

## SASL/PLAIN

Simple username/password, normally used **with TLS**. The username is the principal.

**Broker:**

```text
KafkaServer {
    org.apache.kafka.common.security.plain.PlainLoginModule required
    username="admin"
    password="admin-secret"
    user_admin="admin-secret"
    user_alice="alice-secret";
};
```

`username`/`password` are what this broker uses to connect to other brokers (here `admin`); `user_<userName>` entries define the passwords the broker accepts.

```properties
listeners=SASL_SSL://host.name:port
security.inter.broker.protocol=SASL_SSL
sasl.mechanism.inter.broker.protocol=PLAIN
sasl.enabled.mechanisms=PLAIN
```

**Client:**

```properties
sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required \
    username="alice" \
    password="alice-secret";
security.protocol=SASL_SSL
sasl.mechanism=PLAIN
```

**Production:** use PLAIN **only with SSL** (passwords are sent in clear). Since 2.0, avoid passwords on disk with `sasl.server.callback.handler.class` / `sasl.client.callback.handler.class`, and verify against external servers with a custom `sasl.server.callback.handler.class`.

## SASL/SCRAM (SHA-256 / SHA-512)

SCRAM (RFC 5802) avoids the weaknesses of PLAIN/DIGEST-MD5. Credentials live in the **KRaft metadata log**; the username is the principal.

### Managing credentials

Inter-broker credentials must exist **before brokers start** — create them when formatting:

```bash
$ bin/kafka-storage.sh format -t $(bin/kafka-storage.sh random-uuid) \
    -c config/server.properties \
    --add-scram 'SCRAM-SHA-256=[name="admin",password="admin-secret"]'
```

Client credentials can be created/updated dynamically (applies to new connections):

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter \
    --add-config 'SCRAM-SHA-256=[iterations=8192,password=alice-secret]' \
    --entity-type users --entity-name alice --command-config client.properties

$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --describe \
    --entity-type users --entity-name alice --command-config client.properties

$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter \
    --delete-config 'SCRAM-SHA-256' --entity-type users --entity-name alice \
    --command-config client.properties
```

Default iteration count is **4096**; a random salt is generated if unspecified. Stored: salt, iterations, StoredKey, ServerKey.

**Broker:**

```text
KafkaServer {
    org.apache.kafka.common.security.scram.ScramLoginModule required
    username="admin"
    password="admin-secret";
};
```

```properties
listeners=SASL_SSL://host.name:port
security.inter.broker.protocol=SASL_SSL
sasl.mechanism.inter.broker.protocol=SCRAM-SHA-256
sasl.enabled.mechanisms=SCRAM-SHA-256
```

**Client:**

```properties
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
    username="alice" \
    password="alice-secret";
security.protocol=SASL_SSL
sasl.mechanism=SCRAM-SHA-256
```

**Security considerations:** the metadata-log store suits installations where KRaft controllers are secure and on a private network; only SHA-256/SHA-512 with ≥ 4096 iterations are supported; use SCRAM **only with TLS**; with insecure controllers, override the store with `sasl.server.callback.handler.class` (since 2.0).

## SASL/OAUTHBEARER

OAuth 2 bearer tokens in SASL (RFC 7628). The token's `principalName` is the principal. The default implementation depends on **jackson-databind** — add it to your build (optional dependency).

### Non-production (unsecured JWTs)

The default implementation creates and validates **unsecured JWTs** — handy for dev/test only.

```text
KafkaServer {
    org.apache.kafka.common.security.oauthbearer.OAuthBearerLoginModule required
    unsecuredLoginStringClaim_sub="admin";
};
```

```properties
listeners=SASL_SSL://host.name:port          # or SASL_PLAINTEXT if non-production
security.inter.broker.protocol=SASL_SSL       # or SASL_PLAINTEXT if non-production
sasl.mechanism.inter.broker.protocol=OAUTHBEARER
sasl.enabled.mechanisms=OAUTHBEARER
```

```properties
# client
sasl.jaas.config=org.apache.kafka.common.security.oauthbearer.OAuthBearerLoginModule required \
    unsecuredLoginStringClaim_sub="alice";
security.protocol=SASL_SSL
sasl.mechanism=OAUTHBEARER
```

Validation options (broker): `unsecuredValidatorPrincipalClaimName` (default checks `sub`), `unsecuredValidatorScopeClaimName` (default `scope`), `unsecuredValidatorRequiredScope`, `unsecuredValidatorAllowableClockSkewMs` (default 0). Token creation options (client, or broker for inter-broker): `unsecuredLoginStringClaim_<name>`, `unsecuredLoginNumberClaim_<name>`, `unsecuredLoginListClaim_<name>` (first char is the delimiter, e.g. `"|value1|value2"`), `unsecuredLoginExtension_<name>` (`auth` reserved), `unsecuredLoginPrincipalClaimName`, `unsecuredLoginLifetimeSeconds` (default 3600), `unsecuredLoginScopeClaimName`. `iat`/`exp` are generated.

### Production brokers (JWKS validation)

```text
KafkaServer {
    org.apache.kafka.common.security.oauthbearer.OAuthBearerLoginModule required ;
};
```

```properties
listeners=SASL_SSL://host.name:port
security.inter.broker.protocol=SASL_SSL
sasl.mechanism.inter.broker.protocol=OAUTHBEARER
sasl.enabled.mechanisms=OAUTHBEARER
listener.name.<listener name>.oauthbearer.sasl.server.callback.handler.class=org.apache.kafka.common.security.oauthbearer.OAuthBearerValidatorCallbackHandler
listener.name.<listener name>.oauthbearer.sasl.oauthbearer.jwks.endpoint.url=https://example.com/oauth2/v1/keys
```

Broker settings: `sasl.oauthbearer.clock.skew.seconds` (30), `sasl.oauthbearer.expected.audience`, `sasl.oauthbearer.expected.issuer`, `sasl.oauthbearer.jwks.endpoint.refresh.ms` (3600000), `sasl.oauthbearer.jwks.endpoint.retry.backoff.ms` / `.max.ms` (100 / 10000), `sasl.oauthbearer.jwks.endpoint.url`, `sasl.oauthbearer.scope.claim.name` (`scope`), `sasl.oauthbearer.sub.claim.name` (`sub`). By default the broker requires expected audience and issuer when a JWKS endpoint is set, unless `sasl.oauthbearer.allow.unverified.audience` / `.issuer` are `true`. JWKS/token URLs and token files must be allowed with the `org.apache.kafka.sasl.oauthbearer.allowed.urls` / `.allowed.files` system properties ([system properties](../configuration/config-providers-and-system-properties.md#jvm-system-properties)).

### Production clients

```properties
sasl.jaas.config=org.apache.kafka.common.security.oauthbearer.OAuthBearerLoginModule required ;
```

`sasl.oauthbearer.jwt.retriever.class` defaults to `DefaultJwtRetriever`, which delegates to `ClientCredentialsJwtRetriever` for HTTP(S) token URLs and `FileJwtRetriever` for `file://` URLs.

**client_credentials with a secret:**

```properties
security.protocol=SASL_SSL
sasl.mechanism=OAUTHBEARER
sasl.oauthbearer.client.credentials.client.id=jdoe
sasl.oauthbearer.client.credentials.client.secret=$3cr3+
sasl.oauthbearer.scope=my-application-scope
sasl.oauthbearer.token.endpoint.url=https://example.com/oauth2/v1/token
```

**client_credentials with a client assertion** (RFC 7523, KIP-1258 — private keys never leave the client):

```properties
security.protocol=SASL_SSL
sasl.mechanism=OAUTHBEARER
sasl.oauthbearer.token.endpoint.url=https://example.com/oauth2/v1/token
sasl.oauthbearer.assertion.private.key.file=/path/to/private-key.pem
sasl.oauthbearer.assertion.algorithm=RS256
sasl.oauthbearer.assertion.claim.iss=my-kafka-client
sasl.oauthbearer.assertion.claim.sub=my-service-account
sasl.oauthbearer.assertion.claim.aud=https://example.com
sasl.oauthbearer.assertion.claim.exp.seconds=300
sasl.oauthbearer.assertion.claim.jti.include=true
sasl.oauthbearer.scope=my-application-scope
```

Or a pre-generated assertion: `sasl.oauthbearer.assertion.file=/path/to/assertion.jwt`. Extra static claims for generated assertions: `sasl.oauthbearer.assertion.template.file` (JSON with `header` and `payload`, e.g. `{"header": {"kid": "my-key-id"}, "payload": {"iss": "...", "sub": "...", "aud": "..."}}`).

If several methods are configured, `ClientCredentialsJwtRetriever` picks — at configuration time, for the client's lifetime, with no runtime fallback — (1) `sasl.oauthbearer.assertion.file`, (2) a locally generated assertion (`assertion.claim.iss` + private key), (3) the client secret.

**jwt-bearer grant** — configure the retriever explicitly:

```properties
security.protocol=SASL_SSL
sasl.mechanism=OAUTHBEARER
sasl.oauthbearer.jwt.retriever.class=org.apache.kafka.common.security.oauthbearer.JwtBearerJwtRetriever
sasl.oauthbearer.assertion.private.key.file=/path/to/private.key
sasl.oauthbearer.assertion.algorithm=RS256
sasl.oauthbearer.assertion.claim.exp.seconds=600
sasl.oauthbearer.assertion.template.file=/path/to/template.json
sasl.oauthbearer.scope=my-application-scope
sasl.oauthbearer.token.endpoint.url=https://example.com/oauth2/v1/token
```

Client assertion defaults: `sasl.oauthbearer.assertion.algorithm=RS256` (or `ES256`), `assertion.claim.exp.seconds=300`, `assertion.claim.nbf.seconds=60`, `assertion.claim.jti.include=false`.

### Token refresh and security

Tokens are refreshed before expiry, governed by `sasl.login.refresh.window.factor` (0.8), `sasl.login.refresh.window.jitter` (0.05), `sasl.login.refresh.min.period.seconds` (60) and `sasl.login.refresh.buffer.seconds` (300).

- The default unsecured implementation is **non-production only** and **must be replaced** in production with the built-in retrievers/validator or custom `AuthenticateCallbackHandler`s (server side handling `OAuthBearerValidatorCallback`, set via `listener.name.sasl_ssl.oauthbearer.sasl.server.callback.handler.class`).
- Use OAUTHBEARER **only with TLS**.
- With client assertions, use short expirations (e.g. 300 s) and `jti` to prevent replay.

## Enabling multiple mechanisms

```text
KafkaServer {
    com.sun.security.auth.module.Krb5LoginModule required
    useKeyTab=true
    storeKey=true
    keyTab="/etc/security/keytabs/kafka_server.keytab"
    principal="kafka/kafka1.hostname.com@EXAMPLE.COM";

    org.apache.kafka.common.security.plain.PlainLoginModule required
    username="admin"
    password="admin-secret"
    user_admin="admin-secret"
    user_alice="alice-secret";
};
```

```properties
sasl.enabled.mechanisms=GSSAPI,PLAIN,SCRAM-SHA-256,SCRAM-SHA-512,OAUTHBEARER
security.inter.broker.protocol=SASL_PLAINTEXT   # or SASL_SSL
sasl.mechanism.inter.broker.protocol=GSSAPI     # or another enabled mechanism
```

## Changing the mechanism in a running cluster

1. Add the new mechanism to `sasl.enabled.mechanisms` and the JAAS file on every broker; rolling bounce.
2. Restart clients with the new mechanism.
3. If needed, set `sasl.mechanism.inter.broker.protocol` to the new mechanism; rolling bounce.
4. If needed, remove the old mechanism from `sasl.enabled.mechanisms` and JAAS; rolling bounce.

## Delegation tokens

Lightweight shared-secret authentication (KIP-48) that lets processing frameworks hand credentials to many workers without distributing Kerberos keytabs or keystores. The token **owner** is the principal.

Workflow: authenticate via SASL or SSL → obtain a token (Admin API or `kafka-delegation-tokens.sh`) → pass it securely to clients → owner/renewer renews or expires it.

### Server configuration

- `delegation.token.secret.key` — the same secret on **all brokers and controllers**; if unset/empty, token authentication and APIs fail. It is currently stored as plain text in `server.properties`.
- Token details live with the metadata on controllers — suitable when controllers are on a private network or broker↔controller traffic is encrypted.
- Lifetime: renew every **24 hours** for up to **7 days** by default — `delegation.token.expiry.time.ms`, `delegation.token.max.lifetime.ms`. Unrenewed or over-age tokens are deleted from broker caches; tokens can be cancelled explicitly.

### Managing tokens

Requests (create/renew/expire/describe) must use SASL or SSL authenticated channels — not a delegation-token connection.

```bash
# create
$ bin/kafka-delegation-tokens.sh --bootstrap-server localhost:9092 --create \
    --max-life-time-period -1 --command-config client.properties \
    --renewer-principal User:user1

# create for another owner
$ bin/kafka-delegation-tokens.sh --bootstrap-server localhost:9092 --create \
    --max-life-time-period -1 --command-config client.properties \
    --renewer-principal User:user1 --owner-principal User:owner1

# renew / expire
$ bin/kafka-delegation-tokens.sh --bootstrap-server localhost:9092 --renew \
    --renew-time-period -1 --command-config client.properties --hmac ABCDEFGHIJK
$ bin/kafka-delegation-tokens.sh --bootstrap-server localhost:9092 --expire \
    --expiry-time-period -1 --command-config client.properties --hmac ABCDEFGHIJK

# describe
$ bin/kafka-delegation-tokens.sh --bootstrap-server localhost:9092 --describe \
    --command-config client.properties --owner-principal User:user1
```

Owners/renewers can renew, expire and describe their tokens; describing others' tokens requires `DESCRIBE_TOKEN` on the owner's User resource, and creating tokens for others requires `CreateTokens` (see [ACLs](authorization-and-acls.md)).

### Authenticating with a token

Token auth piggybacks on **SASL/SCRAM**, which must be enabled:

```properties
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
    username="tokenID123" \
    password="lAYYSFmLs4bTjf+lTZ1LCHR/ZZFNA==" \
    tokenauth="true";
```

`username` = token ID, `password` = token HMAC, `tokenauth="true"` marks token authentication.

### Rotating the secret

Requires redeployment (existing connections keep working; new connections and renew/expire with old tokens may fail):

1. Expire all existing tokens.
2. Rotate the secret with a rolling upgrade.
3. Generate new tokens.

## Related pages

- [Security overview and listeners](listeners-and-security-overview.md)
- [SSL encryption and authentication](ssl-encryption-and-authentication.md)
- [Authorization and ACLs](authorization-and-acls.md)
