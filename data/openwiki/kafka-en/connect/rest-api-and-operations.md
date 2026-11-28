---
type: operations-guide
title: Connect REST API, Error Handling, Exactly-Once and Administration
description: Operating Kafka Connect — REST listeners and HTTPS, every REST endpoint (connectors, tasks, pause/stop/resume/restart, topics, KIP-875 offsets, plugins, admin loggers), connector/task states and incremental cooperative rebalancing, error tolerance and dead letter queues, exactly-once for sink and source connectors, security recommendations and the ACLs workers and connectors need.
tags: [connect, rest-api, error-handling, dlq, exactly-once, acls, administration]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-e22e9e0985854e1783097205
    resource: repo://docs/kafka-connect/administration.md
  - id: openwiki-source-0cfab4979b85f5c875d630fd
    resource: repo://docs/kafka-connect/user-guide.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Connect REST API, Error Handling, Exactly-Once and Administration

## REST API server

Connect runs as a service with a REST API in **both** standalone and distributed mode. Configure listeners with `listeners` (format `protocol://host:port,...`; `http` and `https`):

```properties
listeners=http://localhost:8080,https://localhost:8443
```

- Default: HTTP on port **8083** (`http://:8083`).
- HTTPS uses the worker's `ssl.*` settings, or a separate set prefixed with `listeners.https.` (then the unprefixed `ssl.*` are ignored): `ssl.keystore.location`, `ssl.keystore.password`, `ssl.keystore.type`, `ssl.key.password`, `ssl.truststore.location`, `ssl.truststore.password`, `ssl.truststore.type`, `ssl.enabled.protocols`, `ssl.provider`, `ssl.protocol`, `ssl.cipher.suites`, `ssl.keymanager.algorithm`, `ssl.secure.random.implementation`, `ssl.trustmanager.algorithm`, `ssl.endpoint.identification.algorithm`, `ssl.client.auth`.
- In distributed mode the REST API also carries **worker-to-worker** traffic: some requests on followers are forwarded to the leader. If the reachable URI differs from the bind URI, set `rest.advertised.host.name`, `rest.advertised.port`, `rest.advertised.listener` (the latter also picks HTTP vs HTTPS for inter-worker calls).
- `admin.listeners` serves the admin endpoints on separate listeners (default: the regular listeners; empty string disables them).

```properties
admin.listeners=http://localhost:8080,https://localhost:8443
```

## Endpoints

### Connectors

| Method & path | Purpose |
| --- | --- |
| `GET /connectors` | List active connectors. |
| `POST /connectors` | Create: JSON with `name`, `config`, optional `initial_state` (`STOPPED`, `PAUSED`, `RUNNING` — default). |
| `GET /connectors/{name}` | Connector info. |
| `GET /connectors/{name}/config` | Get config. |
| `PUT /connectors/{name}/config` | Replace config (create-or-update). |
| `PATCH /connectors/{name}/config` | Patch config; `null` values remove keys. |
| `GET /connectors/{name}/status` | State, worker, error trace and task states. |
| `GET /connectors/{name}/tasks` | Tasks and their configs. |
| `GET /connectors/{name}/tasks/{taskid}/status` | Task state. |
| `PUT /connectors/{name}/pause` | Pause connector and tasks; resources stay allocated (fast resume). |
| `PUT /connectors/{name}/stop` | Stop and shut down tasks, freeing resources (since 3.5.0). Required before modifying offsets. |
| `PUT /connectors/{name}/resume` | Resume a paused or stopped connector. |
| `POST /connectors/{name}/restart?includeTasks=<true\|false>&onlyFailed=<true\|false>` | Restart connector (and tasks with `includeTasks=true`; only FAILED instances with `onlyFailed=true`; both default `false`). |
| `POST /connectors/{name}/tasks/{taskId}/restart` | Restart one task. |
| `DELETE /connectors/{name}` | Delete connector, halting tasks and deleting config. |
| `GET /connectors/{name}/topics` | Topics the connector has used (since creation or last reset). |
| `PUT /connectors/{name}/topics/reset` | Empty the active-topics set. |

Example:

```bash
curl -X POST -H "Content-Type: application/json" http://localhost:8083/connectors -d '{
  "name": "local-file-source",
  "config": {
    "connector.class": "FileStreamSource",
    "tasks.max": "1",
    "file": "test.txt",
    "topic": "connect-test"
  }
}'
curl http://localhost:8083/connectors/local-file-source/status
```

### Offsets (KIP-875)

| Method & path | Purpose |
| --- | --- |
| `GET /connectors/{name}/offsets` | Current offsets. |
| `DELETE /connectors/{name}/offsets` | Reset offsets — connector must exist and be **stopped**. |
| `PATCH /connectors/{name}/offsets` | Alter offsets — connector must be **stopped**. |

`PATCH` body for `FileStreamSourceConnector` (source formats are connector-specific):

```json
{
  "offsets": [
    { "partition": { "filename": "test.txt" }, "offset": { "position": 30 } }
  ]
}
```

For any sink connector (common format); `"offset": null` resets a partition:

```json
{
  "offsets": [
    { "partition": { "kafka_topic": "test", "kafka_partition": 0 }, "offset": { "kafka_offset": 5 } },
    { "partition": { "kafka_topic": "test", "kafka_partition": 1 }, "offset": null }
  ]
}
```

### Plugins, cluster info and loggers

| Method & path | Purpose |
| --- | --- |
| `GET /connector-plugins` | Installed connector plugins — only on the worker handling the request (can be inconsistent during rolling upgrades). |
| `GET /connector-plugins/{plugin-type}/config` | Config definition of a plugin. |
| `PUT /connector-plugins/{connector-type}/config/validate` | Validate config; returns per-config errors and suggested values. |
| `GET /` | Worker version (incl. git commit) and Kafka cluster ID. |
| `GET /admin/loggers` | Loggers with explicitly set levels (KIP-495). |
| `GET /admin/loggers/{name}` | Level of one logger. |
| `PUT /admin/loggers/{name}` | Set a logger's level. |

The complete specification is the OpenAPI file `connect_rest.yaml`.

## Administration

### Rebalancing

Submitting a connector, changing task counts or configs, and adding/removing/failing workers all trigger a rebalance among workers.

- Before 2.3.0 workers rebalanced **everything** (still available with `connect.protocol=eager`).
- Since 2.3.0, **incremental cooperative rebalancing** moves only tasks that are new, removed or need to move; others keep running. It activates automatically once all workers run ≥ 2.3.0 with `connect.protocol=compatible` (the generated worker reference lists the current default as `sessioned`; values `eager`, `compatible`, `sessioned`).
- When a worker leaves, Connect waits `scheduled.rebalance.max.delay.ms` (default **5 minutes**, `300000`) before reassigning its tasks. If it returns in time it gets all its tasks back — but those tasks stay unassigned meanwhile.

### Status and states

Status updates go through `status.storage.topic`, consumed asynchronously by all workers, so state changes appear with a short delay. Example `GET /connectors/file-source/status`:

```json
{
    "name": "file-source",
    "connector": { "state": "RUNNING", "worker_id": "192.168.1.208:8083" },
    "tasks": [ { "id": 0, "state": "RUNNING", "worker_id": "192.168.1.209:8083" } ]
}
```

States: **UNASSIGNED**, **RUNNING**, **PAUSED**, **STOPPED** (connectors only; tasks of a stopped connector are shut down), **FAILED** (exception in status output), **RESTARTING**.

- Connect does **not** restart failed tasks automatically — use the restart endpoints. Restarting during a rebalance returns **409 Conflict**.
- Pause is persistent across cluster restarts; failed tasks don't become PAUSED until restarted.
- Since 2.5.0, `status.storage.topic` also tracks the topics each connector uses (`topic.tracking.enable`, default true; disallow resets with `topic.tracking.allow.reset=false`).

## Error reporting and dead letter queues

By default any error in conversion or transformations **fails the connector** ("fail fast"), equivalent to:

```properties
# disable retries on failure
errors.retry.timeout=0
# do not log the error and their contexts
errors.log.enable=false
# do not record errors in a dead letter queue topic
errors.deadletterqueue.topic.name=
# Fail on first error
errors.tolerance=none
```

Retries, logging, a DLQ and tolerating all errors:

```properties
# retry for at most 10 minutes times waiting up to 30 seconds between consecutive failures
errors.retry.timeout=600000
errors.retry.delay.max.ms=30000
# log error context along with application logs, but do not include configs and messages
errors.log.enable=true
errors.log.include.messages=false
# produce error context into the Kafka topic
errors.deadletterqueue.topic.name=my-connector-errors
# Tolerate all errors.
errors.tolerance=all
```

- `errors.log.enable=true` logs each error with the record's topic, partition and offset; `errors.log.include.messages=true` also logs key, value and headers (may log sensitive data).
- `errors.deadletterqueue.topic.name` (sink connectors) sends failed records to a DLQ topic; `errors.deadletterqueue.context.headers.enable=true` adds error context headers.
- Defaults: `errors.retry.timeout=0`, `errors.retry.delay.max.ms=60000`, `errors.tolerance=none`, `errors.log.enable=false`, `errors.log.include.messages=false`.
- Sink connectors can report individual bad records via `ErrantRecordReporter` ([connector development](connector-development.md#reporting-errant-records)).

## Exactly-once support

Connect supports exactly-once for **sink connectors since 0.11.0** and **source connectors since 3.3.0** — but it **depends heavily on the connector**; correct worker settings are not enough if the connector can't use the framework's capabilities.

**Sink connectors:** make the consumer ignore aborted transactions — worker `consumer.isolation.level=read_committed`, or per connector `consumer.override.isolation.level=read_committed` if the override policy permits.

**Source connectors:** distributed mode only (standalone can't provide exactly-once). Set worker `exactly.once.source.support`:

- New clusters: `enabled` on every worker.
- Existing clusters: two rolling upgrades — first `preparing`, then `enabled`.

Connector-level options: `exactly.once.support` (`requested` default, or `required`), `transaction.boundary` (`poll` default, `interval` with `transaction.boundary.interval.ms`, or `connector`), `offsets.storage.topic`. Secured clusters need extra ACLs (below).

## Security

- Plugins can run **arbitrary code** — install only trusted plugins.
- The REST API is **unsecured by default**: anyone who can reach it can start/stop connectors and potentially execute code on workers. Expose it only to trusted users.
- Connectors can by default override internal client configs. **Since Kafka 4.2.0 it is recommended to set `connector.client.config.override.policy=Allowlist`** (the default from Kafka 5.0.0) and only allow what's needed. Class-loading configs such as `sasl.jaas.config` or `sasl.login.class` should only be allowed if only trusted users can reach the REST API.
- Keep secrets out of connector configs with [configuration providers](../configuration/config-providers-and-system-properties.md). More in the [Connect security model](../security/listeners-and-security-overview.md).

### ACL requirements

**Worker principal:**

| Operation | Resource | Name | Note |
| --- | --- | --- | --- |
| Read | Group | Connect `group.id` | |
| Read, Write | Topic | `config.storage.topic` | Create only if missing |
| Read, Write | Topic | `offset.storage.topic` | Create only if missing |
| Read, Write | Topic | `status.storage.topic` | Create only if missing |
| Write, Describe | TransactionalId | `connect-cluster-${groupId}` | Only with exactly-once source enabled or `preparing` |
| IdempotentWrite | Cluster | Kafka cluster hosting the config topic | Exactly-once; deprecated since 2.8, only for pre-2.8 Kafka clusters |

**Source connector principal:**

| Operation | Resource | Name | Note |
| --- | --- | --- | --- |
| Write | Topic | destination topic(s) | |
| Create | Topic | destination topic(s) | Only if `topic.creation.enable=true` and topics are missing |
| Describe | Topic | connector's offsets topic (`offsets.storage.topic` or worker `offset.storage.topic`) | Exactly-once only |
| Write, Describe | TransactionalId | `${groupId}-${connector}-${taskId}` (prefix `${groupId}-${connector}*` allowed) | Exactly-once only |
| IdempotentWrite | Cluster | Kafka cluster hosting the config topic | Exactly-once; pre-2.8 clusters only |

**Sink connector principal:**

| Operation | Resource | Name | Note |
| --- | --- | --- | --- |
| Read | Group | `connect-${connector}` (or `consumer.group.id` / `consumer.override.group.id`) | |
| Read | Topic | sink topics (`topics` / `topics.regex`) | |
| Write | Topic | `errors.deadletterqueue.topic.name` | Only if a DLQ is set |

Some connectors (e.g. CDC connectors storing schema history) use extra topics; see their documentation. ACL commands: [Authorization and ACLs](../security/authorization-and-acls.md).

## Related pages

- [Connect overview and workers](overview-and-running.md)
- [Single message transforms](transformations-and-predicates.md)
- [Connector development](connector-development.md)
- [Connect metrics](../monitoring/client-metrics.md)
