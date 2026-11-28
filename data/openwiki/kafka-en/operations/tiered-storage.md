---
type: operations-guide
title: Tiered Storage
description: Kafka tiered storage (KIP-405) — local and remote tiers, broker configs (remote.log.storage.system.enable, RemoteStorageManager and RemoteLogMetadataManager plugins), topic configs (remote.storage.enable, local.retention.*), a LocalTieredStorage quick start, disabling tiered storage per topic or cluster, RLMM client configs, copy/fetch throttles, limitations and key metrics.
tags: [tiered-storage, remote-storage, retention, kip-405, operations, configuration]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-2059af39ef370916603f36ab
    resource: repo://docs/configuration/tiered-storage-configs.md
  - id: openwiki-source-558b53d8c307068fbc04d679
    resource: repo://docs/operations/tiered-storage.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Tiered Storage

## Overview

Kafka data is mostly consumed by **tail reads** served from the OS page cache; older data is read from disk only for backfill or recovery. Tiered storage (KIP-405) gives a cluster **two tiers**:

- **Local tier** — brokers' local disks, as today.
- **Remote tier** — an external system such as HDFS or S3 storing **completed (non-active) log segments**.

Local disks then only need to hold recent data, while topics can retain much longer histories remotely. Consumers read transparently from either tier.

## Broker configuration

| Config | Default | Purpose |
| --- | --- | --- |
| `remote.log.storage.system.enable` | `false` | Enable tiered storage services on the broker. |
| `remote.log.storage.manager.class.name` | `null` | **Required.** `RemoteStorageManager` implementation — manages the lifecycle of remote segments and indexes. Kafka ships **no** production implementation. |
| `remote.log.storage.manager.class.path` | `null` | Class path for the RSM implementation (loaded in its own class loader). |
| `remote.log.storage.manager.impl.prefix` | `rsm.config.` | Prefix for properties passed to the RSM. |
| `remote.log.metadata.manager.class.name` | `org.apache.kafka.server.log.remote.metadata.storage.TopicBasedRemoteLogMetadataManager` | `RemoteLogMetadataManager` — strongly consistent metadata about remote segments; default stores it in the internal topic `__remote_log_metadata`. |
| `remote.log.metadata.manager.class.path` | `null` | Class path for a custom RLMM. |
| `remote.log.metadata.manager.impl.prefix` | `rlmm.config.` | Prefix for RLMM properties. |
| `remote.log.metadata.manager.listener.name` | `null` | **Mandatory with the default RLMM**: the broker listener its clients connect to. |

Tuning (defaults): `remote.log.manager.copier.thread.pool.size=10`, `remote.log.manager.expiration.thread.pool.size=10`, `remote.log.manager.follower.thread.pool.size=2`, `remote.log.reader.threads=10`, `remote.log.reader.max.pending.tasks=100` (fetches fail when the queue is full), `remote.log.manager.task.interval.ms=30000`, `remote.log.index.file.cache.total.size.bytes=1073741824`, `remote.fetch.max.wait.ms=500`, `remote.list.offsets.request.timeout.ms=30000`, `remote.log.metadata.custom.metadata.max.bytes=128`. Many thread pools can be resized dynamically (see [Broker configuration](../configuration/broker-configuration.md#what-can-be-changed-dynamically)).

Bandwidth throttles: `remote.log.manager.copy.max.bytes.per.second` and `remote.log.manager.fetch.max.bytes.per.second` (default `9223372036854775807`, i.e. unlimited), measured over `remote.log.manager.copy/fetch.quota.window.num=11` windows of `…window.size.seconds=1`.

## Topic configuration

| Topic config | Default | Meaning |
| --- | --- | --- |
| `remote.storage.enable` | `false` | Use tiered storage for this topic. |
| `local.retention.ms` | `-2` | How long segments stay on local disk; `-2` = use `retention.ms`. |
| `local.retention.bytes` | `-2` | Max local size per partition; `-2` = use `retention.bytes`. |
| `retention.ms` / `retention.bytes` | `604800000` / `-1` | **Total** retention (local + remote); remote segments are deleted after this. |
| `remote.copy.lag.ms` / `remote.copy.lag.bytes` | `0` / `-1` | Upload eligibility checks for non-active segments. |
| `remote.log.copy.disable` | `false` | Make tiered data read-only (no more uploads). |
| `remote.log.delete.on.disable` | `false` | Delete remote data when disabling tiered storage on the topic. |

Broker-level defaults: `log.local.retention.ms`, `log.local.retention.bytes` (both `-2`), `log.remote.copy.lag.ms` (`0`), `log.remote.copy.lag.bytes` (`-1`). A local segment becomes eligible for deletion **only after it has been uploaded** to remote storage.

## Quick start with LocalTieredStorage

Kafka has no built-in RSM, but the test implementation `LocalTieredStorage` simulates remote storage in a local directory. Build it from the source tag you use:

```bash
# please checkout to the specific version tag you're using before building it
# ex: `git checkout 4.3.0`
$ ./gradlew clean :storage:testJar
```

This produces `storage/build/libs/kafka-storage-x.x.x-test.jar`. Broker `server.properties`:

```properties
# Sample KRaft broker server.properties listening on PLAINTEXT://:9092
remote.log.storage.system.enable=true

# Setting the listener for the clients in RemoteLogMetadataManager to talk to the brokers.
remote.log.metadata.manager.listener.name=PLAINTEXT

# Mandatory: the RemoteStorageManager implementation
remote.log.storage.manager.class.name=org.apache.kafka.server.log.remote.storage.LocalTieredStorage
remote.log.storage.manager.class.path=/PATH/TO/kafka-storage-4.3.0-test.jar

# These 2 prefix are default values, but customizable
remote.log.storage.manager.impl.prefix=rsm.config.
remote.log.metadata.manager.impl.prefix=rlmm.config.

# Directory used by LocalTieredStorage (brokers must have access)
rsm.config.dir=/tmp/kafka-remote-storage

# For single broker cluster, set this to 1. Default is 3 for clusters with 3 or more brokers.
rlmm.config.remote.log.metadata.topic.replication.factor=1
# Default 2. For a single broker (replication factor = 1), set this to 1.
rlmm.config.remote.log.metadata.topic.min.isr=1

# Speed up the retention check for testing
log.retention.check.interval.ms=1000
```

Create a tiered topic (small segments and delays for testing):

```bash
$ bin/kafka-topics.sh --create --topic tieredTopic --bootstrap-server localhost:9092 \
--config remote.storage.enable=true --config local.retention.ms=1000 --config retention.ms=3600000 \
--config segment.bytes=1048576 --config file.delete.delay.ms=1000
```

Produce enough data to roll segments:

```bash
$ bin/kafka-producer-perf-test.sh --bootstrap-server localhost:9092 --topic tieredTopic --num-records 1200 --record-size 1024 --throughput -1
```

Rolled segments are uploaded and deleted locally; check the remote directory:

```bash
$ ls /tmp/kafka-remote-storage/kafka-tiered-storage/tieredTopic-0-jF8s79t9SrG_PNqlwv7bAA
00000000000000000000-knnxbs3FSRyKdPcSAOQC-w.index
00000000000000000000-knnxbs3FSRyKdPcSAOQC-w.snapshot
00000000000000000000-knnxbs3FSRyKdPcSAOQC-w.leader_epoch_checkpoint
00000000000000000000-knnxbs3FSRyKdPcSAOQC-w.timeindex
00000000000000000000-knnxbs3FSRyKdPcSAOQC-w.log
```

Read offset 0 back from remote storage:

```bash
$ bin/kafka-console-consumer.sh --topic tieredTopic --from-beginning --max-messages 1 --bootstrap-server localhost:9092 --formatter-property print.offset=true
```

## Disabling tiered storage

In KRaft mode you can disable it per topic:

**Read-only remote logs** (stop uploading, keep remote data). Also set local retention equal to total retention or `-2`, because after disabling copy the local retention policies no longer apply and disks could fill up unexpectedly:

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 \
   --alter --entity-type topics --entity-name tieredTopic \
   --add-config 'remote.storage.enable=true,remote.log.copy.disable=true,local.retention.ms=-2,local.retention.bytes=-2'
```

**Fully disable and delete remote data:**

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 \
   --alter --entity-type topics --entity-name tieredTopic \
   --add-config 'remote.storage.enable=false,remote.log.delete.on.disable=true'
```

Tiered storage can be re-enabled on a topic later. To disable it **cluster-wide**, first **delete all tiered topics** — otherwise brokers throw an exception at startup — then set `remote.log.storage.system.enable=false`:

```bash
$ bin/kafka-topics.sh --delete --topic tieredTopic --bootstrap-server localhost:9092
```

## RLMM configuration

The default `TopicBasedRemoteLogMetadataManager` creates admin, producer and consumer clients for `__remote_log_metadata`. Its settings take the `remote.log.metadata.manager.impl.prefix` (e.g. `rlmm.config.remote.log.metadata.consume.wait.ms`); notable ones are `remote.log.metadata.topic.replication.factor` (default 3) and `remote.log.metadata.topic.min.isr` (default 2). Client overrides:

```properties
# Configs for admin, producer, and consumer clients
<rlmm.prefix>.remote.log.metadata.common.client.<kafka.property> = <value>
# Configs only for admin client
<rlmm.prefix>.remote.log.metadata.admin.<kafka.property> = <value>
# Configs only for producer client
<rlmm.prefix>.remote.log.metadata.producer.<kafka.property> = <value>
# Configs only for consumer client
<rlmm.prefix>.remote.log.metadata.consumer.<kafka.property> = <value>
```

E.g. on a secured cluster: `rlmm.config.remote.log.metadata.common.client.security.protocol=SASL_SSL`.

## Limitations

- **No support for compacted topics.**
- Tiered storage must be disabled on all topics before disabling it at the broker level.
- Tiered-storage admin actions require clients 3.0+.
- Log segments missing a producer snapshot file (topics created before 2.8.0) are not supported.

## Monitoring

Key metrics (details in [broker metrics](../monitoring/broker-and-kraft-metrics.md#tiered-storage-metrics)):

- `kafka.server:type=BrokerTopicMetrics,name=RemoteCopyLagBytes` / `RemoteCopyLagSegments` — data eligible for tiering but not yet uploaded.
- `…name=RemoteCopyErrorsPerSec`, `RemoteFetchErrorsPerSec`, `RemoteDeleteErrorsPerSec` — should be 0.
- `…name=RemoteFetchBytesPerSec`, `RemoteCopyBytesPerSec`, `RemoteLogSizeBytes`.
- `kafka.log.remote:type=RemoteLogManager,name=RetentionSizeInPercent` / `LocalRetentionSizeInPercent`.
- `kafka.server:type=RemoteLogManager, name=remote-fetch-throttle-time-avg/max`, `remote-copy-throttle-time-avg/max`.

## Related pages

- [Storage, log segments and retention](../concepts/storage-and-retention.md)
- [Topic configuration](../configuration/topic-and-group-configuration.md#tiered-storage)
- [Monitoring brokers](../monitoring/broker-and-kraft-metrics.md)
