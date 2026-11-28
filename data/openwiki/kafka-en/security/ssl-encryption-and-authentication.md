---
type: security-guide
title: Encryption and Authentication with SSL/TLS
description: Setting up TLS for Kafka — generating broker keypairs and CSRs with keytool (PKCS12), hostname verification and SAN fields, creating your own CA with openssl, building trust stores and signing certificates, PEM-format keys in configuration, production pitfalls (extended key usage, intermediate CAs, missing SANs), broker and client SSL configs including ssl.client.auth, and verifying the setup.
tags: [security, ssl, tls, certificates, keystore, mtls, configuration]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-fbbc17e7aea2c678c3c8a51a
    resource: repo://docs/security/encryption-and-authentication-using-ssl.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Encryption and Authentication with SSL/TLS

Kafka can use SSL/TLS to **encrypt** traffic and to **authenticate** clients (mTLS). It is disabled by default. Note: when TLS is enabled the broker can't use zero-copy `sendfile`, so expect some CPU/throughput cost ([Storage](../concepts/storage-and-retention.md#efficiency-batching-and-zero-copy)). Listener setup: [Security overview](listeners-and-security-overview.md).

## 1. Generate a key and certificate request per broker

Kafka keeps keys and certificates in **keystores**, managed with Java's `keytool`. `jks` is deprecated; **PKCS12** (default since Java 9) is used explicitly below.

```bash
$ keytool -keystore {keystorefile} -alias localhost -validity {validity} -genkey -keyalg RSA -storetype pkcs12
```

- `keystorefile` holds this broker's private and public key — keep it safe; ideally generate it on the broker itself so the key never leaves the host.
- `validity` is the **key's** validity in days (distinct from the certificate's validity set when signing; one long-lived key can back many certificates over time).

Generate the keypair with hostname info (SAN) for the signing request:

```bash
$ keytool -keystore server.keystore.jks -alias localhost -validity {validity} -genkey -keyalg RSA -destkeystoretype pkcs12 -ext SAN=DNS:{FQDN},IP:{IPADDRESS1}
```

## 2. Hostname verification

Hostname verification checks the server certificate against the host you connect to, preventing man-in-the-middle attacks. **Since Kafka 2.0.0 it is enabled by default** for client and inter-broker connections (`ssl.endpoint.identification.algorithm=https`).

- Clients check the server's FQDN or IP against the certificate's **Common Name (CN)** or **Subject Alternative Name (SAN)**. CN-based checking has been deprecated since 2000 — prefer **SAN**, which supports multiple DNS and IP entries and frees CN for authorization purposes.
- SANs must be in the **signed certificate**, so specify them in the CSR (`-ext SAN=DNS:{FQDN},IP:{IPADDRESS}`); adding them only to the keypair doesn't copy them into the CSR.
- To disable (not recommended — it's much harder to fix later): set `ssl.endpoint.identification.algorithm` to an empty string, or for a dynamic listener:

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9093 --entity-type brokers --entity-name 0 --alter --add-config "listener.name.internal.ssl.endpoint.identification.algorithm="
```

## 3. Create your own CA (dev/test)

A CA signs certificates so they're hard to forge; trusting the CA means trusting everything it signs (chain of trust). In production you'd normally use your corporate CA (see pitfalls below).

Because of an OpenSSL bug, the `x509` module doesn't copy requested extensions (SANs) from CSRs, so use the **`ca` module** with a config file `openssl-ca.cnf`:

```ini
HOME            = .
RANDFILE        = $ENV::HOME/.rnd

[ ca ]
default_ca    = CA_default

[ CA_default ]
base_dir      = .
certificate   = $base_dir/cacert.pem
private_key   = $base_dir/cakey.pem
new_certs_dir = $base_dir
database      = $base_dir/index.txt
serial        = $base_dir/serial.txt
default_days     = 1000
default_crl_days = 30
default_md       = sha256
preserve         = no
x509_extensions = ca_extensions
email_in_dn     = no
copy_extensions = copy          # Required to copy SANs from CSR to cert

[ req ]
default_bits       = 4096
default_keyfile    = cakey.pem
distinguished_name = ca_distinguished_name
x509_extensions    = ca_extensions
string_mask        = utf8only

[ ca_distinguished_name ]
countryName         = Country Name (2 letter code)
countryName_default = DE
# ... stateOrProvinceName, localityName, organizationName, organizationalUnitName, commonName, emailAddress ...

[ ca_extensions ]
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid:always, issuer
basicConstraints       = critical, CA:true
keyUsage               = keyCertSign, cRLSign

[ signing_policy ]
countryName            = optional
stateOrProvinceName    = optional
localityName           = optional
organizationName       = optional
organizationalUnitName = optional
commonName             = supplied
emailAddress           = optional

[ signing_req ]
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer
basicConstraints       = CA:FALSE
keyUsage               = digitalSignature, keyEncipherment
```

```bash
$ echo 01 > serial.txt
$ touch index.txt
$ openssl req -x509 -config openssl-ca.cnf -newkey rsa:4096 -sha256 -nodes -out cacert.pem -outform PEM
```

**Protect the CA key**: anyone holding it can mint certificates trusted by your whole infrastructure.

### Trust stores

```bash
# clients trust the CA
$ keytool -keystore client.truststore.jks -alias CARoot -import -file ca-cert

# brokers need a truststore too if they authenticate clients (ssl.client.auth=requested|required)
$ keytool -keystore server.truststore.jks -alias CARoot -import -file ca-cert
```

A keystore holds a machine's own identity; a truststore holds what it trusts. The truststore contains no secrets and can be shared by all clients and brokers.

## 4. Sign and import certificates

```bash
$ openssl ca -config openssl-ca.cnf -policy signing_policy -extensions signing_req -out {server certificate} -infiles {certificate signing request}

$ keytool -keystore {keystore} -alias CARoot -import -file {CA certificate}
$ keytool -keystore {keystore} -alias localhost -import -file cert-signed
```

Result: one shared truststore and one `server.keystore.jks` per node (its key, signed certificate and the CA certificate). Tools such as easyRSA can script these steps.

## PEM keys and certificates in configuration (2.7.0+)

Key and trust stores can be given **directly in the config in PEM format** (or PEM files as a store type alongside JKS and PKCS12):

| Config | Content |
| --- | --- |
| `ssl.keystore.key` | Private key (PKCS#8 PEM) |
| `ssl.keystore.certificate.chain` | Certificate chain (X.509 PEM) |
| `ssl.truststore.certificates` | Trusted certificates (e.g. the CA) |
| `ssl.key.password` | Only if the private key is encrypted |

`ssl.keystore.password` and `ssl.truststore.password` are **not used** with PEM. Multi-line PEM values use backslash line continuations. Unencrypted keys in config should be protected/externalized (e.g. [config providers](../configuration/config-providers-and-system-properties.md)). The default SSL engine factory has limited support for decrypting externally encrypted keys; integrate libraries like BouncyCastle via a custom `SslEngineFactory` (`ssl.engine.factory.class`) if needed.

```properties
ssl.keystore.type=PEM
ssl.keystore.certificate.chain=-----BEGIN CERTIFICATE----- \
MIIC... \
-----END CERTIFICATE-----
ssl.keystore.key=-----BEGIN PRIVATE KEY----- \
MIIE... \
-----END PRIVATE KEY-----
ssl.truststore.type=PEM
ssl.truststore.certificates=-----BEGIN CERTIFICATE----- \
MIIC... \
-----END CERTIFICATE-----
```

## Common pitfalls in production

Enterprises usually sign CSRs with a corporate CA. Watch for:

1. **Extended Key Usage:** if present it is enforced. Brokers act as **both client and server** to each other, so certificates need **both `clientAuth` and `serverAuth`**; a webserver-only profile (just `serverAuth`) breaks the SSL handshake.
2. **Intermediate certificates:** when signed by an intermediate CA, import the **full chain** up to the root (concatenate the certificate files and import with keytool).
3. **Extension fields not copied:** CAs often don't copy requested SANs. Check the signed certificate:

```bash
$ openssl x509 -in certificate.crt -text -noout
```

## Configuring brokers

If SSL isn't used for inter-broker traffic, keep both ports:

```properties
listeners=PLAINTEXT://host.name:port,SSL://host.name:port

ssl.keystore.location=/var/private/ssl/server.keystore.jks
ssl.keystore.password=test1234
ssl.key.password=test1234
ssl.truststore.location=/var/private/ssl/server.truststore.jks
ssl.truststore.password=test1234
```

`ssl.truststore.password` is optional but strongly recommended — without it the truststore is usable but integrity checking is disabled.

Optional settings:

| Setting | Notes |
| --- | --- |
| `ssl.client.auth` | `none` (default), `requested` (cert optional — **discouraged**, false sense of security), `required` (mTLS). |
| `ssl.cipher.suites` | Default empty list (JVM defaults). |
| `ssl.enabled.protocols` | Protocols accepted from clients; client default is `TLSv1.2,TLSv1.3`. Don't use SSL (pre-TLS) protocols in production. |
| `ssl.keystore.type` / `ssl.truststore.type` | `JKS` default; `PKCS12`, `PEM`. |
| `ssl.secure.random.implementation` | E.g. `SHA1PRNG` — the Linux default `NativePRNG` uses a global lock that can hurt SSL performance. |

Inter-broker SSL (defaults to `PLAINTEXT`):

```properties
security.inter.broker.protocol=SSL
```

For stronger algorithms on some Oracle JDKs (e.g. AES-256) you may need the JCE Unlimited Strength policy files.

### Verifying

`server.log` shows the endpoints:

```text
with addresses: PLAINTEXT -> EndPoint(192.168.64.1,9092,PLAINTEXT),SSL -> EndPoint(192.168.64.1,9093,SSL)
```

```bash
$ openssl s_client -debug -connect localhost:9093 -tls1
```

(the protocol you test must be in `ssl.enabled.protocols`). You should see the server certificate (`-----BEGIN CERTIFICATE-----` … plus `subject=` and `issuer=` lines); otherwise the keystore is misconfigured. Keystores and truststores can be rotated without restart via dynamic listener configs ([Broker configuration](../configuration/broker-configuration.md#what-can-be-changed-dynamically)).

## Configuring clients

SSL works with the Java producer and consumer (same configs for both). Without client authentication:

```properties
security.protocol=SSL
ssl.truststore.location=/var/private/ssl/client.truststore.jks
ssl.truststore.password=test1234
```

With client authentication (`ssl.client.auth=required` on the broker), also create a client keystore and add:

```properties
ssl.keystore.location=/var/private/ssl/client.keystore.jks
ssl.keystore.password=test1234
ssl.key.password=test1234
```

Other optional client settings: `ssl.provider` (default: JVM's provider), `ssl.cipher.suites`, `ssl.enabled.protocols` (must include at least one broker-enabled protocol), `ssl.truststore.type=JKS`, `ssl.keystore.type=JKS`.

Console tools:

```bash
$ bin/kafka-console-producer.sh --bootstrap-server localhost:9093 --topic test --command-config client-ssl.properties
$ bin/kafka-console-consumer.sh --bootstrap-server localhost:9093 --topic test --command-config client-ssl.properties
```

The authenticated mTLS principal is the certificate DN, mappable via `ssl.principal.mapping.rules` ([Authorization](authorization-and-acls.md#ssl)).

## Related pages

- [Security overview and listeners](listeners-and-security-overview.md)
- [SASL authentication](sasl-authentication.md) (SASL_SSL combines both)
- [Client configuration](../configuration/client-configuration.md) (`ssl.*` defaults)
