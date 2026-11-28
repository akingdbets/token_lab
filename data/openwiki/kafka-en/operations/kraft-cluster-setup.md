---
type: operations-guide
title: KRaft Cluster Setup and Controller Management
description: Setting up and operating a KRaft-mode Kafka cluster — process.roles and combined vs dedicated controllers, controller quorum sizing and controller.quorum.bootstrap.servers, formatting storage with kafka-storage.sh (standalone, initial controllers, new brokers/controllers), static vs dynamic (KIP-853) quorums and upgrading kraft.version, adding/removing/unregistering controllers, debugging with kafka-metadata-quorum.sh, kafka-dump-log.sh and kafka-metadata-shell.sh, and deployment sizing.
tags: [kraft, controllers, operations, kafka-storage, metadata-quorum, cluster-setup]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-8af78d0e38f41f3cef772520
    resource: repo://docs/operations/kraft.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# KRaft Cluster Setup and Controller Management

Kafka runs in **KRaft mode**: cluster metadata is kept in a Raft-replicated metadata log (`__cluster_metadata`) managed by **controllers**, with no ZooKeeper. (Migrating from ZooKeeper: see [ZooKeeper to KRaft](zookeeper-to-kraft-migration.md).)

## Process roles

`process.roles` sets what a server does:

| Value | Role |
| --- | --- |
| `broker` | Broker only. |
| `controller` | Controller only. |
| `broker,controller` | **Combined** server. |

Combined servers are simpler for small/dev setups, but the controller is less isolated — you can't roll or scale controllers separately from brokers. **Combined mode is not recommended for critical deployments.** The shipped `config/server.properties` is combined; `config/broker.properties` and `config/controller.properties` show dedicated roles (see [Broker configuration](../configuration/broker-configuration.md#sample-properties-files)).

## Controllers and the quorum

- Controllers participate in the metadata quorum; one is **active**, the others are **hot standbys**.
- Typically choose **3 or 5** controllers. A **majority must be alive** for availability: 3 tolerate 1 failure, 5 tolerate 2. In general, tolerating `N` concurrent failures needs `2N + 1` controllers.
- **Every broker and controller** sets `controller.quorum.bootstrap.servers` (list all controllers as `host:port`) to discover the active controller.

Example for `controller1` of three:

```properties
process.roles=controller
node.id=1
listeners=CONTROLLER://controller1.example.com:9093
controller.quorum.bootstrap.servers=controller1.example.com:9093,controller2.example.com:9093,controller3.example.com:9093
controller.listener.names=CONTROLLER
```

## Provisioning nodes (formatting storage)

Storage must be **formatted explicitly** with `bin/kafka-storage.sh` using a cluster ID shared by all nodes. Kafka no longer auto-formats blank directories or auto-generates cluster IDs, because auto-formatting can hide errors — e.g. a majority of controllers starting with empty logs could elect a leader that is missing committed data.

```bash
$ bin/kafka-storage.sh random-uuid
```

### Bootstrap a standalone controller (recommended)

Start a new controller cluster with **one voter**, then add the others dynamically:

```bash
$ bin/kafka-storage.sh format --cluster-id <CLUSTER_ID> --standalone --config config/controller.properties
```

This creates `meta.properties` in `metadata.log.dir` with a random `directory.id`, and a snapshot `00000000000000000000-0000000000.checkpoint` containing `KRaftVersionRecord` and `VotersRecord` making this node the only voter.

### Bootstrap with multiple controllers

```bash
CLUSTER_ID="$(bin/kafka-storage.sh random-uuid)"
CONTROLLER_0_UUID="$(bin/kafka-storage.sh random-uuid)"
CONTROLLER_1_UUID="$(bin/kafka-storage.sh random-uuid)"
CONTROLLER_2_UUID="$(bin/kafka-storage.sh random-uuid)"

# In each controller execute
bin/kafka-storage.sh format --cluster-id ${CLUSTER_ID} \
                     --initial-controllers "0@controller-0:1234:${CONTROLLER_0_UUID},1@controller-1:1234:${CONTROLLER_1_UUID},2@controller-2:1234:${CONTROLLER_2_UUID}" \
                     --config config/controller.properties
```

Each entry is `<replica id>@<host>:<port>:<directory id>`. The `--initial-controllers` value **must be identical on all controllers** of the cluster.

### Formatting new nodes for an existing cluster

```bash
# new broker
$ bin/kafka-storage.sh format --cluster-id <CLUSTER_ID> --config config/server.properties

# new controller (to be added dynamically)
$ bin/kafka-storage.sh format --cluster-id <CLUSTER_ID> --config config/server.properties --no-initial-controllers
```

## Static vs dynamic quorums

| | Dynamic (KIP-853) | Static |
| --- | --- | --- |
| Config | `controller.quorum.bootstrap.servers` (need not list every controller, like client `bootstrap.servers`); `controller.quorum.voters` **must not** be set | Every node lists all controller IDs, hosts and ports in `controller.quorum.voters` |
| Membership changes | Add/remove controllers online | Not supported |
| `kraft.version` | ≥ 1 | 0 or absent |

The type is fixed **at format time**: a quorum is dynamic if `controller.quorum.voters` is not present and one of `--standalone`, `--initial-controllers` or `--no-initial-controllers` is used.

Check which you have:

```bash
$ bin/kafka-features.sh --bootstrap-controller localhost:9093 describe
Feature: kraft.version  SupportedMinVersion: 0  SupportedMaxVersion: 1  FinalizedVersionLevel: 1 Epoch: 5
Feature: metadata.version       SupportedMinVersion: 3.3-IV3    SupportedMaxVersion: 3.9-IV0 FinalizedVersionLevel: 3.9-IV0  Epoch: 5
```

`FinalizedVersionLevel: 1` (or higher) for `kraft.version` → dynamic; `0` or no `kraft.version` line → static.

### Upgrading static → dynamic (Kafka 4.1+)

Kafka **4.1** added upgrading from a static to a dynamic controller configuration (dynamic quorums need `kraft.version=1` / `release-version 4.1`):

```bash
# upgrade all features to the latest
$ bin/kafka-features.sh --bootstrap-server localhost:9092 upgrade --release-version 4.1

# or just kraft.version
$ bin/kafka-features.sh --bootstrap-server localhost:9092 upgrade --feature kraft.version=1
```

Then, on **all** nodes, remove the deprecated `controller.quorum.voters` and add `controller.quorum.bootstrap.servers`:

```properties
process.roles=...
node.id=...
controller.quorum.bootstrap.servers=controller1.example.com:9093,controller2.example.com:9093,controller3.example.com:9093
controller.listener.names=CONTROLLER
```

(The 4.0 compatibility matrix notes that a 4.0 server can't be converted from static to dynamic voters — KAFKA-16538; see [Compatibility](../getting-started/compatibility.md).)

## Controller membership changes (dynamic quorums)

### Add a controller

1. Format the new controller with `--no-initial-controllers` and start it.
2. Watch it catch up: `bin/kafka-metadata-quorum.sh describe --replication`.
3. Add it to the voter set:

```bash
# via brokers
$ bin/kafka-metadata-quorum.sh --command-config config/controller.properties --bootstrap-server localhost:9092 add-controller
# via controllers
$ bin/kafka-metadata-quorum.sh --command-config config/controller.properties --bootstrap-controller localhost:9093 add-controller
```

`--command-config` must point to the **new controller's** config file, which must also contain any Admin client settings (e.g. authentication), and its `controller.quorum.bootstrap.servers` must include at least one current quorum member.

### Remove a controller

Remove it from the quorum **before** shutting it down:

```bash
$ bin/kafka-metadata-quorum.sh --bootstrap-server localhost:9092 remove-controller --controller-id <id> --controller-directory-id <directory-id>
$ bin/kafka-metadata-quorum.sh --bootstrap-controller localhost:9093 remove-controller --controller-id <id> --controller-directory-id <directory-id>

# remove and unregister in one step
$ bin/kafka-metadata-quorum.sh --bootstrap-server localhost:9092 remove-controller --controller-id <id> --controller-directory-id <directory-id> --unregister
```

### Unregister a controller

A controller already removed from the voter set (and shut down — a running controller re-registers itself) can be unregistered from cluster metadata:

```bash
$ bin/kafka-cluster.sh unregister-controller --bootstrap-server localhost:9092 --id <id>
$ bin/kafka-cluster.sh unregister-controller --bootstrap-controller localhost:9093 --id <id>
```

Replacing a controller whose metadata disk was lost: see [Hardware and OS](hardware-os-and-deployment.md#replacing-a-kraft-controller-disk).

## Debugging

### kafka-metadata-quorum.sh

```bash
$ bin/kafka-metadata-quorum.sh --bootstrap-server localhost:9092 describe --status
ClusterId:              fMCL8kv1SWm87L_Md-I2hg
LeaderId:               3002
LeaderEpoch:            2
HighWatermark:          10
MaxFollowerLag:         0
MaxFollowerLagTimeMs:   -1
CurrentVoters:          [{"id": 3000, "directoryId": "ILZ5MPTeRWakmJu99uBJCA", "endpoints": ["CONTROLLER://localhost:9093"]},
                         {"id": 3001, "directoryId": "b-DwmhtOheTqZzPoh52kfA", "endpoints": ["CONTROLLER://localhost:9094"]},
                         {"id": 3002, "directoryId": "g42deArWBTRM5A1yuVpMCg", "endpoints": ["CONTROLLER://localhost:9095"]}]
CurrentObservers:       [{"id": 0, "directoryId": "3Db5QLSqSZieL3rJBUUegA"}, ...]
```

`describe --replication` shows per-node `LogEndOffset`, `Lag`, `LastFetchTimestamp`, `LastCaughtUpTimestamp` and `Status` (Leader, Follower, Observer). Brokers appear as observers.

### kafka-dump-log.sh

Decode metadata log segments and snapshots:

```bash
$ bin/kafka-dump-log.sh --cluster-metadata-decoder --files metadata_log_dir/__cluster_metadata-0/00000000000000000000.log
$ bin/kafka-dump-log.sh --cluster-metadata-decoder --files metadata_log_dir/__cluster_metadata-0/00000000000000000100-0000000001.checkpoint
```

### kafka-metadata-shell.sh

Interactively browse a metadata snapshot:

```bash
$ bin/kafka-metadata-shell.sh --snapshot metadata_log_dir/__cluster_metadata-0/00000000000000007228-0000000001.checkpoint
>> ls /
brokers  local  metadataQuorum  topicIds  topics
>> ls /topics
foo
>> cat /topics/foo/0/data
{
  "partitionId" : 0,
  "topicId" : "5zoAlv-xEh9xRANKXt1Lbg",
  "replicas" : [ 1 ],
  "isr" : [ 1 ],
  "removingReplicas" : null,
  "addingReplicas" : null,
  "leader" : 1,
  "leaderEpoch" : 0,
  "partitionEpoch" : 0
}
>> exit
```

`00000000000000000000-0000000000.checkpoint` (the bootstrap snapshot) contains no cluster metadata — use a real snapshot.

Quorum health metrics (`kafka.server:type=raft-metrics`, `ActiveControllerCount`, `FencedBrokerCount`, …) are in [Monitoring brokers and KRaft](../monitoring/broker-and-kraft-metrics.md#kraft-metrics).

## Deployment considerations

- Set `process.roles` to `broker` **or** `controller` in production; combined mode only for development.
- Use **3 or more** controllers; `2N + 1` controllers survive `N` concurrent failures.
- Controllers keep all metadata in memory and on disk; for a typical cluster **5 GB of RAM and 5 GB of disk** for the metadata log directory is sufficient.
- Metadata log location: `metadata.log.dir` (defaults to the first `log.dirs` entry).
- Key quorum timeouts (defaults): `controller.quorum.fetch.timeout.ms=2000`, `controller.quorum.election.timeout.ms=1000`, `controller.quorum.election.backoff.max.ms=1000`, `controller.quorum.request.timeout.ms=2000`, `broker.session.timeout.ms=9000`, `broker.heartbeat.interval.ms=2000`.

## Related pages

- [ZooKeeper to KRaft migration and differences](zookeeper-to-kraft-migration.md)
- [Broker and controller configuration](../configuration/broker-configuration.md)
- [Quickstart](../getting-started/local-quickstart.md) (single-node `--standalone` format)
