---
type: security-guide
title: Authorization and ACLs
description: Configuring Kafka authorization — StandardAuthorizer in KRaft, ACL structure, default deny and allow.everyone.if.no.acl.found, super.users, how brokers forward admin requests to controllers (KafkaPrincipalSerde), mapping SSL and Kerberos names to principals, every kafka-acls.sh option with examples (literal, wildcard, prefixed, match), the operations and resources model and which operation/resource each protocol API requires.
tags: [security, authorization, acls, kafka-acls, principals, standard-authorizer]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-98d64b9165a546dd98a91929
    resource: repo://docs/security/authorization-and-acls.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Authorization and ACLs

## Enabling the authorizer

Kafka's authorization is pluggable via `authorizer.class.name`; implementations extend `org.apache.kafka.server.authorizer.Authorizer`. The built-in implementation stores ACLs in the **KRaft metadata log**. On **all nodes** (brokers, controllers, combined):

```properties
authorizer.class.name=org.apache.kafka.metadata.authorizer.StandardAuthorizer
```

An ACL reads: *"Principal P is [Allowed|Denied] Operation O From Host H on any Resource R matching ResourcePattern RP"* (KIP-11; resource patterns KIP-290). Manage ACLs with `bin/kafka-acls.sh` or the Admin API (`createAcls`/`deleteAcls`, themselves gated by `Alter` on `Cluster`).

### Default behavior

- If **no ACL matches** a resource, access is **restricted to super users**.
- `allow.everyone.if.no.acl.found=true` makes resources with no ACLs accessible to everyone; resources **with** ACLs are still enforced normally. Since every resource without ACLs (including newly created topics) is then open, use it mainly for development, tests or phased rollouts; keep the default `false` in production unless every sensitive resource has explicit ACLs.
- Super users (semicolon-separated, because SSL names may contain commas; `User` is case-sensitive):

```properties
super.users=User:Bob;User:Alice
```

### KRaft principal forwarding

Clients send admin requests such as `CreateTopics` and `DeleteTopics` to brokers, which forward them to the active controller over the first listener in `controller.listener.names`, wrapped in an `Envelope` request carrying the client principal. The controller authorizes the `Envelope` with the **broker principal** and the inner request with the **forwarded client principal** — so authorization for these requests happens on the controller.

Therefore a custom `principal.builder.class` must also implement **`org.apache.kafka.common.security.auth.KafkaPrincipalSerde`** so principals can be serialized. The default `org.apache.kafka.common.security.authenticator.DefaultKafkaPrincipalBuilder` uses the RPC format in `clients/src/main/resources/common/message/DefaultPrincipalData.json`.

## Principal names

### SSL

By default the principal is the certificate's distinguished name, e.g. `CN=writeuser,OU=Unknown,O=Unknown,L=Unknown,ST=Unknown,C=Unknown`. Map DNs to short names with `ssl.principal.mapping.rules` — rules are tried in order and the **first match wins**; append `/L` or `/U` to force lower/upper case; `DEFAULT` keeps the full DN:

```text
RULE:pattern/replacement/
RULE:pattern/replacement/[LU]
```

```properties
ssl.principal.mapping.rules=RULE:^CN=(.*?),OU=ServiceUsers.*$/$1/,RULE:^CN=(.*?),OU=(.*?),O=(.*?),L=(.*?),ST=(.*?),C=(.*?)$/$1@$2/L,RULE:^.*[Cc][Nn]=([a-zA-Z0-9.]*).*$/$1/L,DEFAULT
```

These map `CN=serviceuser,OU=ServiceUsers,O=Unknown,…` → `serviceuser` and `CN=adminUser,OU=Admin,O=Unknown,…` → `adminuser@admin`. For anything more advanced, set `principal.builder.class=CustomizedPrincipalBuilderClass`.

### SASL/Kerberos

By default the principal is the **primary** part of the Kerberos principal. Customize with `sasl.kerberos.principal.to.local.rules` (same syntax as `auth_to_local` in `krb5.conf`, plus `/L` and `/U`):

```text
<!-- openwiki: broken internal link [regexp] file "regexp" does not exist. Fix the href or restore the target, then delete this comment. -->
RULE:[n:string](regexp)s/pattern/replacement/
<!-- openwiki: broken internal link [regexp] file "regexp" does not exist. Fix the href or restore the target, then delete this comment. -->
RULE:[n:string](regexp)s/pattern/replacement/g
<!-- openwiki: broken internal link [regexp] file "regexp" does not exist. Fix the href or restore the target, then delete this comment. -->
RULE:[n:string](regexp)s/pattern/replacement//L
<!-- openwiki: broken internal link [regexp] file "regexp" does not exist. Fix the href or restore the target, then delete this comment. -->
RULE:[n:string](regexp)s/pattern/replacement/g/L
<!-- openwiki: broken internal link [regexp] file "regexp" does not exist. Fix the href or restore the target, then delete this comment. -->
RULE:[n:string](regexp)s/pattern/replacement//U
<!-- openwiki: broken internal link [regexp] file "regexp" does not exist. Fix the href or restore the target, then delete this comment. -->
RULE:[n:string](regexp)s/pattern/replacement/g/U
```

```properties
<!-- openwiki: broken internal link [.*@MYDOMAIN.COM] file ".*@MYDOMAIN.COM" does not exist. Fix the href or restore the target, then delete this comment. -->
sasl.kerberos.principal.to.local.rules=RULE:[1:$1@$0](.*@MYDOMAIN.COM)s/@.*//,DEFAULT
```

(maps `user@MYDOMAIN.COM` → `user`). Other SASL mechanisms use the authenticated user name (see [SASL](sasl-authentication.md)).

## kafka-acls.sh options

| Option | Type | Meaning |
| --- | --- | --- |
| `--add` / `--remove` / `--list` | Action | Add, remove or list ACLs. |
| `--bootstrap-server` / `--bootstrap-controller` | Configuration | Connect via brokers or controllers (exactly one). |
| `--command-config` | Configuration | Admin client properties file (e.g. security settings). |
| `--cluster` | ResourcePattern | The cluster resource. |
| `--topic [name]` | ResourcePattern | Topic(s). |
| `--group [name]` | ResourcePattern | Consumer group(s). |
| `--transactional-id [id]` | ResourcePattern | Transactional ID(s); `*` = all. |
| `--delegation-token [token]` | ResourcePattern | Delegation token(s); `*` = all. |
| `--user-principal [principal]` | ResourcePattern | User resource (for delegation token create/describe on behalf of others). |
| `--resource-pattern-type [type]` | Configuration | Default **`literal`**. For `--add`: `literal` or `prefixed`. For `--list`/`--remove` filters: also `any` (any pattern type, exact name) or `match` (everything affecting the resource — **use `match` with `--remove` carefully**). |
| `--allow-principal` / `--deny-principal` | Principal | `PrincipalType:name` (default type `User`). |
| `--principal` | Principal | Filter for `--list`. |
| `--allow-host` / `--deny-host` | Host | **IP addresses only** (no hostnames); default `*` (all hosts) when a principal is given. |
| `--operation` | Operation | `Read`, `Write`, `Create`, `Delete`, `Alter`, `Describe`, `ClusterAction`, `DescribeConfigs`, `AlterConfigs`, `IdempotentWrite`, `CreateTokens`, `DescribeTokens`, `All` (default `All`). |
| `--producer` | Convenience | `Write`, `Describe`, `Create` on the topic. |
| `--consumer` | Convenience | `Read`, `Describe` on the topic and `Read` on the group (requires `--group`). |
| `--idempotent` | Convenience | With `--producer`; idempotence is implied if the producer is authorized for a transactional ID. |
| `--force` | Convenience | Don't prompt. |

## Examples

```bash
# Bob and Alice may Read and Write Test-topic from two IPs
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --add --allow-principal User:Bob --allow-principal User:Alice --allow-host 198.51.100.0 --allow-host 198.51.100.1 --operation Read --operation Write --topic Test-topic

# everyone may Read, except BadBob from 198.51.100.3
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --add --allow-principal User:'*' --allow-host '*' --deny-principal User:BadBob --deny-host 198.51.100.3 --operation Read --topic Test-topic

# Peter may produce to any topic (wildcard resource)
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --add --allow-principal User:Peter --allow-host 198.51.200.1 --producer --topic '*'

# Jane may produce to topics starting with "Test-" (prefixed)
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --add --allow-principal User:Jane --producer --topic Test- --resource-pattern-type prefixed

# remove
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --remove --allow-principal User:Bob --allow-principal User:Alice --allow-host 198.51.100.0 --allow-host 198.51.100.1 --operation Read --operation Write --topic Test-topic
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --remove --allow-principal User:Jane --producer --topic Test- --resource-pattern-type Prefixed

# list exact pattern, wildcard pattern, or everything that affects the topic
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --list --topic Test-topic
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --list --topic '*'
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --list --topic Test-topic --resource-pattern-type match

# producer / consumer roles
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --add --allow-principal User:Bob --producer --topic Test-topic
$ bin/kafka-acls.sh --bootstrap-server localhost:9092 --add --allow-principal User:Bob --consumer --topic Test-topic --group Group-1
```

Notes:

- Without an explicit allow, principals are denied; use deny ACLs only to carve exceptions out of broad allows.
- `literal` matches only the exact name (or any name for `*`). Plain `--list --topic X` doesn't show wildcard or prefixed ACLs that also apply — use `match`.
- Transactional producers additionally need `Write`/`Describe` on `--transactional-id`; exactly-once Connect/Streams have their own ACL lists ([Connect](../connect/rest-api-and-operations.md#acl-requirements), [Streams security](../streams/running-and-rebalancing.md)).

## Authorization model

### Operations

`Read`, `Write`, `Create`, `Delete`, `Alter`, `Describe`, `ClusterAction`, `DescribeConfigs`, `AlterConfigs`, `IdempotentWrite`, `CreateTokens`, `DescribeTokens`, `All`.

### Resources and error codes

| Resource | Represents | Error on denial |
| --- | --- | --- |
| **Topic** | A topic | `TOPIC_AUTHORIZATION_FAILED` (29) |
| **Group** | Consumer/share/streams groups | `GROUP_AUTHORIZATION_FAILED` (30) |
| **Cluster** | The cluster (e.g. controlled shutdown, ACL changes) | `CLUSTER_AUTHORIZATION_FAILED` (31) |
| **TransactionalId** | Transactional actions (e.g. commit) | `TRANSACTIONAL_ID_AUTHORIZATION_FAILED` (53) |
| **DelegationToken** | Delegation tokens (KIP-48) | — |
| **User** | `CreateTokens`/`DescribeTokens` for other users (KIP-373) | — |

### What common APIs require

| API (key) | Operation | Resource |
| --- | --- | --- |
| PRODUCE (0) | Write | Topic; plus Write on TransactionalId (transactional) or IdempotentWrite on Cluster (idempotent) |
| FETCH (1) | Read | Topic (consumers); ClusterAction on Cluster for followers |
| LIST_OFFSETS (2), METADATA (3) | Describe | Topic |
| METADATA (3) with auto-create | Create | Cluster, or Create on the Topic |
| OFFSET_COMMIT (8) | Read | Group **and** Topic |
| OFFSET_FETCH (9) | Describe | Group and Topic |
| FIND_COORDINATOR (10) | Describe | Group or TransactionalId |
| JOIN_GROUP / HEARTBEAT / LEAVE_GROUP / SYNC_GROUP (11–14) | Read | Group |
| DESCRIBE_GROUPS (15) | Describe | Group |
| LIST_GROUPS (16) | Describe | Cluster (else filtered by Describe on Group) |
| SASL_HANDSHAKE (17), API_VERSIONS (18), SASL_AUTHENTICATE (36) | — | part of the handshake, not authorized |
| CREATE_TOPICS (19) | Create | Cluster or Topic |
| DELETE_TOPICS (20), DELETE_RECORDS (21) | Delete | Topic |
| INIT_PRODUCER_ID (22) | Write / IdempotentWrite | TransactionalId / Cluster |
| ADD_PARTITIONS_TO_TXN (24) | Write | TransactionalId and Topic |
| ADD_OFFSETS_TO_TXN (25) | Write / Read | TransactionalId / Group |
| END_TXN (26) | Write | TransactionalId |
| TXN_OFFSET_COMMIT (28) | Write / Read / Read | TransactionalId / Group / Topic |
| DESCRIBE_ACLS (29) | Describe | Cluster |
| CREATE_ACLS (30), DELETE_ACLS (31) | Alter | Cluster |
| DESCRIBE_CONFIGS (32) | DescribeConfigs | Cluster (broker configs) or Topic |
| ALTER_CONFIGS (33), INCREMENTAL_ALTER_CONFIGS (44) | AlterConfigs | Cluster or Topic |
| CREATE_PARTITIONS (37) | Alter | Topic |
| CREATE_DELEGATION_TOKEN (38) | CreateTokens | User (for others) |
| DESCRIBE_DELEGATION_TOKEN (41) | Describe / DescribeTokens | DelegationToken / User |
| DELETE_GROUPS (42) | Delete | Group |
| ELECT_PREFERRED_LEADERS (43) | ClusterAction | Cluster |
| ALTER_PARTITION_REASSIGNMENTS (45) / LIST_PARTITION_REASSIGNMENTS (46) | Alter / Describe | Cluster |
| OFFSET_DELETE (47) | Delete / Read | Group / Topic |
| DESCRIBE_CLIENT_QUOTAS (48) / ALTER_CLIENT_QUOTAS (49) | DescribeConfigs / AlterConfigs | Cluster |
| DESCRIBE/ALTER_USER_SCRAM_CREDENTIALS (50/51) | Describe / Alter | Cluster |
| DESCRIBE_QUORUM (55), DESCRIBE_CLUSTER (60) | Describe | Cluster |
| UPDATE_FEATURES (57), UNREGISTER_BROKER (64), UNREGISTER_CONTROLLER (94) | Alter | Cluster |
| DESCRIBE_PRODUCERS (61) | Read | Topic |
| DESCRIBE_TRANSACTIONS (65), LIST_TRANSACTIONS (66) | Describe | TransactionalId |
| CONSUMER_GROUP_HEARTBEAT (68) / CONSUMER_GROUP_DESCRIBE (69) | Read / Describe | Group |
| GET_TELEMETRY_SUBSCRIPTIONS (71), PUSH_TELEMETRY (72) | — | no authorization check |
| DESCRIBE_TOPIC_PARTITIONS (75) | Describe | Topic |
| SHARE_GROUP_HEARTBEAT (76) / SHARE_GROUP_DESCRIBE (77) | Read / Describe | Group |
| SHARE_FETCH (78), SHARE_ACKNOWLEDGE (79) | Read | Group and Topic |
| STREAMS_GROUP_HEARTBEAT (88) | Read Group; Describe Topic (source + internal); Create Topic (internal, for auto-creation) | |
| STREAMS_GROUP_DESCRIBE (89) | Describe | Group and Topic |
| DESCRIBE/ALTER/DELETE_SHARE_GROUP_OFFSETS (90/91/92) | Describe / Read / Delete | Group (+ Describe/Read/Read Topic) |
| Inter-broker/controller APIs (LEADER_AND_ISR, VOTE, BEGIN/END_QUORUM_EPOCH, ALTER_PARTITION, ENVELOPE, FETCH_SNAPSHOT, BROKER_REGISTRATION, BROKER_HEARTBEAT, ALLOCATE_PRODUCER_IDS, CONTROLLER_REGISTRATION, WRITE_TXN_MARKERS, share-group state APIs, …) | ClusterAction | Cluster |

Broker and controller principals therefore need `ClusterAction` on `Cluster` (or be super users).

## Related pages

- [Security overview and listeners](listeners-and-security-overview.md)
- [SASL authentication](sasl-authentication.md), [SSL](ssl-encryption-and-authentication.md)
- [Multi-tenancy (prefixed ACLs)](../operations/quotas-and-multi-tenancy.md#multi-tenancy)
