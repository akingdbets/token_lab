---
type: operations-guide
title: ZooKeeper to KRaft Migration and Differences
description: How to get from ZooKeeper mode to KRaft (via the 3.9 bridge release) and what changes — removed ZooKeeper-only configs (zookeeper.*, password.encoder.*, control.plane.listener.name, broker.id generation, inter.broker.protocol.version), dynamic log levels and dynamic configs on controllers with --bootstrap-controller, removed metrics, and behavioral differences such as policy classes running on controllers.
tags: [kraft, zookeeper, migration, upgrade, configuration, metrics]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-00c3dbe963dcc60bcfd114a7
    resource: repo://docs/getting-started/zk2kraft.md
  - id: openwiki-source-8af78d0e38f41f3cef772520
    resource: repo://docs/operations/kraft.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# ZooKeeper to KRaft Migration and Differences

Kafka 4.x runs **only in KRaft mode**. ZooKeeper mode and its configs, metrics and tooling options (e.g. `--zookeeper`) are gone.

## How to migrate

**You must use a bridge release to migrate from ZooKeeper to KRaft; the last bridge release is Kafka 3.9.** Follow the "ZooKeeper to KRaft Migration" steps in the **3.9 documentation** to migrate an existing ZooKeeper cluster to KRaft on 3.9, then upgrade the KRaft cluster to 4.x.

Things to plan for:

- Upgrade paths to a 4.0 server depend on the KRaft version and voter type — 3.3.x–3.8.x clusters upgrade only with **static** voters; 3.9.x and 4.0.x support static and dynamic voters; static voters can't be converted to dynamic on 4.0 (KAFKA-16538). Kafka 4.1+ supports upgrading static → dynamic quorums via `kraft.version=1` (see [KRaft cluster setup](kraft-cluster-setup.md#upgrading-static--dynamic-kafka-41)).
- Old clients (0.x, 1.x, 2.0) can't talk to 4.0 brokers; 2.1–2.8 are partially compatible ([Compatibility](../getting-started/compatibility.md)).
- Move `CreateTopicPolicy` / `AlterConfigPolicy` JARs and configs from brokers to controllers (see below).

## Removed configurations

| Removed | Why / replacement |
| --- | --- |
| `password.encoder.secret`, `password.encoder.old.secret`, `password.encoder.keyfactory.algorithm`, `password.encoder.cipher.algorithm`, `password.encoder.key.length`, `password.encoder.iterations` | ZooKeeper-mode encryption of sensitive dynamic configs. In KRaft, sensitive data is stored in metadata records **and is not encrypted by Kafka** — protect the metadata log directories (and consider [config providers](../configuration/config-providers-and-system-properties.md)). |
| `control.plane.listener.name` | The control plane is built into KRaft: brokers handle data requests, controllers handle metadata with Raft. Use `controller.listener.names`, `listeners`, `listener.security.protocol.map`. |
| `controlled.shutdown.max.retries`, `controlled.shutdown.retry.backoff.ms` | Shutdown is handled by the quorum controller with automated leader transfer. |
| `reserved.broker.max.id`, `broker.id.generation.enable` | Servers are identified by `node.id`. |
| `inter.broker.protocol.version` | Cluster feature level is `metadata.version`, managed with `bin/kafka-features.sh`. |
| Dynamic `advertised.listeners` relying on ZooKeeper | Changing it requires restarting the broker/controller. |
| `leader.imbalance.per.broker.percentage` | ZooKeeper-only preferred-leader election throttle. |
| `zookeeper.connect`, `zookeeper.session.timeout.ms`, `zookeeper.connection.timeout.ms`, `zookeeper.set.acl`, `zookeeper.max.in.flight.requests`, `zookeeper.ssl.client.enable`, `zookeeper.clientCnxnSocket`, `zookeeper.ssl.keystore.*`, `zookeeper.ssl.truststore.*`, `zookeeper.ssl.protocol`, `zookeeper.ssl.enabled.protocols`, `zookeeper.ssl.cipher.suites`, `zookeeper.ssl.endpoint.identification.algorithm`, `zookeeper.ssl.crl.enable`, `zookeeper.ssl.ocsp.enable` | No ZooKeeper. |

Check feature levels:

```bash
$ bin/kafka-features.sh --bootstrap-controller localhost:9093 describe
Feature: kraft.version  SupportedMinVersion: 0  SupportedMaxVersion: 1  FinalizedVersionLevel: 0        Epoch: 7
Feature: metadata.version       SupportedMinVersion: 3.3-IV3    SupportedMaxVersion: 4.0-IV3    FinalizedVersionLevel: 4.0-IV3  Epoch: 7

$ bin/kafka-features.sh --bootstrap-server localhost:9092 upgrade --release-version 4.1
```

## Dynamic log levels

Change log4j levels of running processes without restart. Broker syntax is unchanged:

```bash
./bin/kafka-configs.sh --bootstrap-server localhost:9092 \
    --entity-type broker-loggers \
    --entity-name 1 \
    --alter \
    --add-config org.apache.kafka.raft.KafkaNetworkChannel=TRACE
```

For **controllers**, use `--bootstrap-controller` — and still `--entity-type broker-loggers`:

```bash
./bin/kafka-configs.sh --bootstrap-controller localhost:9093 \
    --entity-type broker-loggers \
    --entity-name 1 \
    --alter \
    --add-config org.apache.kafka.raft.KafkaNetworkChannel=TRACE
```

**Combined** nodes have a single set of log levels; either `--bootstrap-server` or `--bootstrap-controller` works.

## Dynamic controller configurations

Broker dynamic config syntax is unchanged:

```bash
./bin/kafka-configs.sh --bootstrap-server localhost:9092 \
    --entity-type brokers \
    --entity-name 1 \
    --alter \
    --add-config num.io.threads=5
```

Controllers apply all applicable **cluster-level** dynamic configs — this changes `max.connections` on all brokers **and** controllers:

```bash
./bin/kafka-configs.sh --bootstrap-server localhost:9092 \
    --entity-type brokers \
    --entity-default \
    --alter \
    --add-config max.connections=10000
```

**Version note:** prior to 4.3, dynamic configuration updates were not supported unless a static quorum was used.

## Metrics changes

- `ControlPlaneNetworkProcessorAvgIdlePercent` and `ControlPlaneExpiredConnectionsKilledCount` are removed; use `NetworkProcessorAvgIdlePercent` and `ExpiredConnectionsKilledCount`.
- ZooKeeper-mode controller and session metrics are removed, including `kafka.controller:type=ControllerChannelManager,*`, the `kafka.controller:type=ControllerStats,name=*RateAndTimeMs` family (e.g. `AutoLeaderBalanceRateAndTimeMs`, `ControlledShutdownRateAndTimeMs`, `ControllerChangeRateAndTimeMs`, `IsrChangeRateAndTimeMs`, `PartitionReassignmentRateAndTimeMs`, `TopicDeletionRateAndTimeMs`, …), `kafka.controller:type=KafkaController,name=ControllerState`, `MigratingZkBrokerCount`, `ZkMigrationState`, `ElectLeader`/`topic` purgatory metrics, all `kafka.server:type=SessionExpireListener,*` ZooKeeper session metrics and `kafka.server:type=ZooKeeperClientMetrics,name=ZooKeeperRequestLatencyMs`.
- The docs' removal list also names ZooKeeper-controller versions of `ActiveControllerCount`, `ActiveBrokerCount`, `FencedBrokerCount`, `GlobalTopicCount`, `GlobalPartitionCount`, `OfflinePartitionsCount`, `PreferredReplicaImbalanceCount` and topic-deletion counts. KRaft controllers expose their own metrics with these names — see [KRaft controller metrics](../monitoring/broker-and-kraft-metrics.md#controller-kafkacontrollertypekafkacontroller-unless-noted).

Update dashboards and alerts accordingly.

## Behavioral differences

- **Config value size:** KRaft limits configuration values to `Short.MAX_VALUE` bytes, so you can't grow very large values with append operations.
- **Policy classes run on controllers:** `CreateTopicPolicy` and `AlterConfigPolicy` execute on the **controller**. Deploy their JARs on controllers and set `create.topic.policy.class.name` / `alter.config.policy.class.name` there. When migrating from ZooKeeper, move policy JARs from brokers to controllers.
- **Custom `KafkaPrincipalBuilder`:** must also implement `KafkaPrincipalSerde`, otherwise brokers can't forward requests to the controller (see [Authorization](../security/authorization-and-acls.md)).
- **Formatting is mandatory:** KRaft storage must be formatted with `kafka-storage.sh` and a cluster ID; there's no auto-formatting ([KRaft setup](kraft-cluster-setup.md#provisioning-nodes-formatting-storage)).
- **Admin tools:** `--zookeeper` is removed; use `--bootstrap-server`, or `--bootstrap-controller` for controller-side operations.

## Related pages

- [KRaft cluster setup and controller management](kraft-cluster-setup.md)
- [Compatibility and Java versions](../getting-started/compatibility.md)
- [Broker configuration](../configuration/broker-configuration.md)
