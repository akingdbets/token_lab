---
type: operations-reference
title: Monitoring Brokers, KRaft and the Group Coordinator
description: How Kafka exposes server metrics over JMX and how to secure remote JMX, the broker MBeans to graph and alert on (throughput, request latency breakdown, under-replicated/under-min-ISR partitions, idle ratios, quotas, log size), group and share coordinator metrics, tiered storage metrics, and KRaft quorum, controller and broker metadata metrics with their normal values.
tags: [monitoring, metrics, jmx, broker, kraft, group-coordinator, tiered-storage, share-groups]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-82a79fdc3cb35121a3a2ee62
    resource: repo://docs/operations/monitoring.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Monitoring Brokers, KRaft and the Group Coordinator

## How metrics are exposed

- The **server** uses Yammer Metrics; the **Java clients** use Kafka Metrics (a built-in registry with minimal dependencies). Both expose metrics via **JMX** and can report to other systems through pluggable reporters (`metric.reporters`).
- **Every rate metric has a cumulative `-total` counterpart** (e.g. `records-consumed-rate` → `records-consumed-total`).
- The quickest way to browse metrics is `jconsole` attached to a running broker or client.

### Remote JMX security

Remote JMX is **disabled by default**. Enable it by setting `JMX_PORT` for processes started with the CLI scripts (or standard Java system properties). JMX **authentication is disabled by default**, so in production override the security settings via `KAFKA_JMX_OPTS` (or system properties) so unauthorized users cannot monitor or control the broker:

```bash
export JMX_PORT=9999
export KAFKA_JMX_OPTS="-Dcom.sun.management.jmxremote \
  -Dcom.sun.management.jmxremote.authenticate=true \
  -Dcom.sun.management.jmxremote.ssl=true \
  -Dcom.sun.management.jmxremote.password.file=/etc/kafka/jmxremote.password \
  -Dcom.sun.management.jmxremote.access.file=/etc/kafka/jmxremote.access"
bin/kafka-server-start.sh config/server.properties
```

The JMX endpoint is part of the attack surface; see the [security model](../security/listeners-and-security-overview.md).

## Key broker metrics

Patterns like `topic=([-.\w]+)` mean "one MBean per topic"; omit the tag for the all-topic value.

### Throughput

| Metric | MBean | Normal value / note |
| --- | --- | --- |
| Message in rate | `kafka.server:type=BrokerTopicMetrics,name=MessagesInPerSec,topic=([-.\w]+)` | per topic |
| Bytes in from clients | `kafka.server:type=BrokerTopicMetrics,name=BytesInPerSec,topic=([-.\w]+)` | |
| Bytes out to clients | `kafka.server:type=BrokerTopicMetrics,name=BytesOutPerSec,topic=([-.\w]+)` | |
| Replication bytes in/out | `kafka.server:type=BrokerTopicMetrics,name=ReplicationBytesInPerSec` / `ReplicationBytesOutPerSec` | across all topics |
| Produce / fetch request rate | `kafka.server:type=BrokerTopicMetrics,name=TotalProduceRequestsPerSec` / `TotalFetchRequestsPerSec,topic=…` | |
| Failed produce / fetch rate | `kafka.server:type=BrokerTopicMetrics,name=FailedProduceRequestsPerSec` / `FailedFetchRequestsPerSec` | |
| Rejected bytes | `kafka.server:type=BrokerTopicMetrics,name=BytesRejectedPerSec,topic=…` | batches too large |
| Reassignment traffic | `kafka.server:type=BrokerTopicMetrics,name=ReassignmentBytesInPerSec` / `ReassignmentBytesOutPerSec` | 0 unless reassigning |
| Message conversion rate | `kafka.server:type=BrokerTopicMetrics,name={Produce\|Fetch}MessageConversionsPerSec,topic=…` | |

### Requests and latency

| Metric | MBean | Normal value / note |
| --- | --- | --- |
| Request rate | `kafka.network:type=RequestMetrics,name=RequestsPerSec,request={Produce\|FetchConsumer\|FetchFollower},version=…` | |
| Error rate | `kafka.network:type=RequestMetrics,name=ErrorsPerSec,request=…,error=…` | per request type and error code |
| Request total time | `kafka.network:type=RequestMetrics,name=TotalTimeMs,request={Produce\|FetchConsumer\|FetchFollower}` | = queue + local + remote + response send |
| Request queue time | `…name=RequestQueueTimeMs,request=…` | |
| Local (leader) time | `…name=LocalTimeMs,request=…` | |
| Remote time (waiting for followers) | `…name=RemoteTimeMs,request=…` | non-zero for produce with `acks=-1` |
| Response queue / send time | `…name=ResponseQueueTimeMs` / `ResponseSendTimeMs` | |
| Request size | `kafka.network:type=RequestMetrics,name=RequestBytes,request=…` | |
| Request queue size | `kafka.network:type=RequestChannel,name=RequestQueueSize` | |
| Network processor idle | `kafka.network:type=SocketServer,name=NetworkProcessorAvgIdlePercent` | 0–1, ideally **> 0.3** |
| Request handler idle | `kafka.server:type=KafkaRequestHandlerPool,name=RequestHandlerAvgIdlePercent` | 0–1, ideally **> 0.3** |
| Producer purgatory | `kafka.server:type=DelayedOperationPurgatory,name=PurgatorySize,delayedOperation=Produce` | non-zero if `acks=-1` |
| Fetch purgatory | `…name=PurgatorySize,delayedOperation=Fetch` | depends on consumer `fetch.max.wait.ms` |

Idle ratios below ~0.3 suggest raising `num.network.threads` / `num.io.threads` (dynamically updatable; see [Broker configuration](../configuration/broker-configuration.md)).

### Replication health (alert on these)

| Metric | MBean | Normal value |
| --- | --- | --- |
| Under-replicated partitions (ISR < all replicas) | `kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions` | **0** |
| Under-min-ISR partitions (ISR < `min.insync.replicas`) | `kafka.server:type=ReplicaManager,name=UnderMinIsrPartitionCount` | **0** |
| At-min-ISR partitions | `kafka.server:type=ReplicaManager,name=AtMinIsrPartitionCount` | **0** |
| Offline replicas | `kafka.server:type=ReplicaManager,name=OfflineReplicaCount` | **0** |
| Partition count / leader count | `kafka.server:type=ReplicaManager,name=PartitionCount` / `LeaderCount` | mostly even across brokers |
| ISR shrink / expand rate | `kafka.server:type=ReplicaManager,name=IsrShrinksPerSec` / `IsrExpandsPerSec` | shrink when a broker goes down, expand when it catches up |
| Failed ISR updates | `kafka.server:type=ReplicaManager,name=FailedIsrUpdatesPerSec` | 0 |
| Max follower lag | `kafka.server:type=ReplicaFetcherManager,name=MaxLag,clientId=Replica` | proportional to max producer batch size |
| Per-follower lag | `kafka.server:type=FetcherLagMetrics,name=ConsumerLag,clientId=…,topic=…,partition=…` | |
| Leader elections | `kafka.controller:type=ControllerStats,name=LeaderElectionRateAndTimeMs` | non-zero on broker failures |
| Unclean leader elections | `kafka.controller:type=ControllerStats,name=UncleanLeaderElectionsPerSec` | **0** |
| ELR elections | `kafka.controller:type=ControllerStats,name=ElectionFromEligibleLeaderReplicasPerSec` | 0 |
| Reassigning partitions | `kafka.server:type=ReplicaManager,name=ReassigningPartitions` | |

### Logs and storage

| Metric | MBean | Normal value / note |
| --- | --- | --- |
| Offline log directories | `kafka.log:type=LogManager,name=OfflineLogDirectoryCount` | **0** |
| Log directory offline | `kafka.log:type=LogManager,name=LogDirectoryOffline` | 1 offline / 0 online |
| Log flush rate and time | `kafka.log:type=LogFlushStats,name=LogFlushRateAndTimeMs` | |
| Partition size | `kafka.log:type=Log,name=Size,topic=…,partition=…` | bytes |
| Size vs `retention.bytes` | `kafka.log:type=Log,name=RetentionSizeInPercent,topic=…,partition=…` | |
| Segment count | `kafka.log:type=Log,name=NumLogSegments,…` | |
| Log start / end offset | `kafka.log:type=Log,name=LogStartOffset` / `LogEndOffset` | |
| Recovery progress | `kafka.log:type=LogManager,name=remainingLogsToRecover` / `remainingSegmentsToRecover` | during startup |
| Validation failures | `kafka.server:type=BrokerTopicMetrics,name=NoKeyCompactedTopicRecordsPerSec`, `InvalidMagicNumberRecordsPerSec`, `InvalidMessageCrcRecordsPerSec`, `InvalidOffsetOrSequenceRecordsPerSec` | **0** |

Log cleaner health: `uncleanable-partitions-count`, `max-clean-time-secs`, `max-compaction-delay-secs` (see [Log compaction](../concepts/log-compaction.md)).

### Quotas, connections and coordinators

| Metric | MBean | Note |
| --- | --- | --- |
| Bandwidth quota per (user, client-id) | `kafka.server:type={Produce\|Fetch},user=…,client-id=…` | attributes `throttle-time`, `byte-rate` |
| Request quota per (user, client-id) | `kafka.server:type=Request,user=…,client-id=…` | `throttle-time`, `request-time` |
| Exempt requests | `kafka.server:type=Request` | `exempt-throttle-time` |
| Expired connections killed (re-auth) | `kafka.network:type=SocketServer,name=ExpiredConnectionsKilledCount` | ideally 0 with re-authentication |
| Group metadata load time | `kafka.server:type=group-coordinator-metrics,name=partition-load-time-max/avg` | |
| Transaction metadata load time | `kafka.server:type=transaction-coordinator-metrics,name=partition-load-time-max/avg` | |
| Transaction verification | `kafka.server:type=AddPartitionsToTxnManager,name=VerificationFailureRate` / `VerificationTimeMs` | |
| Producer IDs | `kafka.server:type=ReplicaManager,name=ProducerIdCount` | idempotent + transactional |

See [Quotas](../operations/quotas-and-multi-tenancy.md).

## Group coordinator metrics

All under `kafka.server:type=group-coordinator-metrics`:

| Name | Meaning |
| --- | --- |
| `num-partitions,state={loading\|active\|failed}` | `__consumer_offsets` partitions hosted, by state |
| `partition-load-time-max` / `-avg` | Time to load partition state |
| `thread-idle-ratio-avg` | Coordinator thread idle ratio |
| `event-queue-size`, `event-queue-time-ms-[max\|p50\|p95\|p99\|p999]`, `event-processing-time-ms-*`, `event-purgatory-time-ms-*` | Coordinator event loop |
| `batch-linger-time-ms-*`, `batch-flush-time-ms-*`, `batch-flush-rate`, `batch-buffer-cache-size-bytes`, `batch-buffer-cache-discard-count` | Write batching |
| `group-count,protocol={consumer\|classic\|streams\|share}` | Groups by type |
| `consumer-group-count,state=[Empty\|Assigning\|Reconciling\|Stable\|Dead]` | Consumer groups by state |
| `consumer-group-rebalance-rate` / `-count` | KIP-848 rebalances |
| `classic-group-count,state=[…]`, `group-completed-rebalance-rate` / `-count` | Classic groups |
| `streams-group-count,state=[…]`, `streams-group-rebalance-rate` / `-count` | Streams groups |
| `streams-group-topology-description-{set,get,delete}-{success,error}-{rate,count}`, `…-cleanup-*` | Topology description plugin calls |
| `offset-count`, `offset-commit-rate`/`-count`, `offset-expiration-rate`/`-count`, `offset-deletion-rate`/`-count` | Offsets |

Deprecated: `kafka.server:type=GroupMetadataManager,name=NumGroups`, `NumGroups[PreparingRebalance,…]`, `NumOffsets` — use `group-count`, `classic-group-count`, `offset-count`.

## Share group metrics (broker)

| Metric | MBean |
| --- | --- |
| Share fetch / acknowledgement request rates (total, failed) | `kafka.server:type=BrokerTopicMetrics,name=TotalShareFetchRequestsPerSec`, `FailedShareFetchRequestsPerSec`, `TotalShareAcknowledgementRequestsPerSec`, `FailedShareAcknowledgementRequestsPerSec` |
| Records acknowledged by type | `kafka.server:type=ShareGroupMetrics,name=RecordAcknowledgementsPerSec,ackType={Accept\|Release\|Reject\|Renew}` |
| Share partition load time | `kafka.server:type=ShareGroupMetrics,name=PartitionLoadTimeMs` |
| Acquisition lock timeouts | `kafka.server:type=SharePartitionMetrics,name=AcquisitionLockTimeoutPerSec,group=…,topic=…,partition=…` |
| In-flight messages / batches | `kafka.server:type=SharePartitionMetrics,name=InFlightMessageCount` / `InFlightBatchCount` / `InFlightBatchMessageCount` |
| Fetch lock time / ratio | `kafka.server:type=SharePartitionMetrics,name=FetchLockTimeMs` / `FetchLockRatio` |
| Share sessions | `kafka.server:type=ShareSessionCache,name=ShareSessionsCount` / `SharePartitionsCount` / `ShareSessionEvictionsPerSec` |
| Delayed share fetch | `kafka.server:type=DelayedOperationPurgatory,name=PurgatorySize,delayedOperation=ShareFetch`; `kafka.server:type=DelayedShareFetchMetrics,name=ExpiresPerSec` |
| Share coordinator | `kafka.server:type=share-coordinator-metrics,name=` `partition-load-time-max/avg`, `thread-idle-ratio-min/avg`, `write-rate`, `write-total`, `write-latency-avg/max`, `num-partitions`, `last-pruned-offset` |
| Share group counts/rebalances | `kafka.server:type=group-coordinator-metrics,name=group-count,protocol=share`, `share-group-rebalance-rate`/`-count` |

Client-side share consumer metrics are in [client metrics](client-metrics.md).

## Tiered storage metrics

| Metric | MBean |
| --- | --- |
| Remote fetch bytes / requests / errors per sec | `kafka.server:type=BrokerTopicMetrics,name=RemoteFetchBytesPerSec` / `RemoteFetchRequestsPerSec` / `RemoteFetchErrorsPerSec,topic=…` |
| Remote copy bytes / requests / errors per sec | `…name=RemoteCopyBytesPerSec` / `RemoteCopyRequestsPerSec` / `RemoteCopyErrorsPerSec` |
| Copy lag (eligible but not yet tiered) | `…name=RemoteCopyLagBytes` / `RemoteCopyLagSegments` |
| Remote delete requests / errors, delete lag | `…name=RemoteDeleteRequestsPerSec` / `RemoteDeleteErrorsPerSec` / `RemoteDeleteLagBytes` / `RemoteDeleteLagSegments` |
| Aux state rebuild requests / errors | `…name=BuildRemoteLogAuxStateRequestsPerSec` / `BuildRemoteLogAuxStateErrorsPerSec` |
| Remote log size / metadata count / size computation time | `…name=RemoteLogSizeBytes` / `RemoteLogMetadataCount` / `RemoteLogSizeComputationTime` |
| Expired delayed remote fetches | `kafka.server:type=DelayedRemoteFetchMetrics,name=ExpiresPerSec,topic=…` |
| Reader queue / idle | `org.apache.kafka.storage.internals.log:type=RemoteStorageThreadPool,…` (`RemoteLogReaderTaskQueueSize`, `RemoteLogReaderAvgIdlePercent`) |
| Copier idle | `kafka.log.remote:type=RemoteLogManager,name=RemoteLogManagerTasksAvgIdlePercent` |
| Fetch / copy throttle time | `kafka.server:type=RemoteLogManager, name=remote-fetch-throttle-time-avg/max`, `remote-copy-throttle-time-avg/max` |
| Retention usage | `kafka.log.remote:type=RemoteLogManager,name=RetentionSizeInPercent` / `LocalRetentionSizeInPercent,topic=…,partition=…` |

See [Tiered storage](../operations/tiered-storage.md).

## KRaft metrics

Which metrics exist depends on the node's `process.roles`.

### Quorum (`kafka.server:type=raft-metrics`)

| Metric | Meaning |
| --- | --- |
| Current State | `leader`, `candidate`, `voted`, `follower`, `unattached`, `observer` |
| Current Leader / Current Voted / Current Epoch | Leader id (`-1` unknown), voted id, epoch |
| High Watermark / Log End Offset | Raft log positions (`-1` unknown) |
| Number of Unknown Voter Connections | Voters without cached connection info |
| Average / Maximum Commit Latency | ms to commit an entry |
| Average / Maximum Election Latency | ms to elect a leader |
| Fetch Records Rate / Append Records Rate | Raft replication throughput |
| Average Poll Idle Ratio | Raft IO thread idle ratio |

Metadata loading: `kafka.server:type=MetadataLoader,name=CurrentMetadataVersion`, `…name=HandleLoadSnapshotCount`; snapshots: `kafka.server:type=SnapshotEmitter,name=LatestSnapshotGeneratedBytes` / `LatestSnapshotGeneratedAgeMs`.

### Controller (`kafka.controller:type=KafkaController` unless noted)

| Name | Meaning |
| --- | --- |
| `ActiveControllerCount` | 1 on the active controller, 0 elsewhere — exactly one node in the cluster should report 1 |
| `ControllerEventManager,name=EventQueueTimeMs` / `EventQueueProcessingTimeMs` | Event queue wait/processing histograms |
| `FencedBrokerCount` / `ActiveBrokerCount` | Broker states as seen by the controller |
| `GlobalTopicCount` / `GlobalPartitionCount` | Cluster totals |
| `OfflinePartitionsCount` | Offline (non-internal) partitions — alert if > 0 |
| `PreferredReplicaImbalanceCount` | Partitions not led by the preferred leader |
| `MetadataErrorCount` | Metadata log processing errors |
| `LastAppliedRecordOffset` / `LastCommittedRecordOffset` / `LastAppliedRecordTimestamp` / `LastAppliedRecordLagMs` | Metadata log progress |
| `TimedOutBrokerHeartbeatCount` | Broker heartbeats that timed out |
| `EventQueueOperationsStartedCount` / `EventQueueOperationsTimedOutCount` | Event queue operations |
| `NewActiveControllersCount` | Controller elections observed |

### Broker (`kafka.server:type=broker-metadata-metrics`)

Last Applied Record Offset, Last Applied Record Timestamp, Last Applied Record Lag Ms (how far the broker's metadata view trails the controller), Metadata Load Error Count (errors in `BrokerMetadataListener` loading the metadata log) and Metadata Apply Error Count (errors in `BrokerMetadataPublisher` applying a new metadata image).

Debugging tools for the quorum (`kafka-metadata-quorum.sh`, `kafka-dump-log.sh`, `kafka-metadata-shell.sh`) are in [KRaft cluster setup](../operations/kraft-cluster-setup.md#debugging).

## Other things to watch

Monitor **GC time**, **CPU utilization** and **I/O service time** on servers. On clients, watch message/byte rates (global and per topic), request rate/size/time, and for consumers the **max lag** across partitions and **min fetch request rate** — to keep up, max lag must stay under a threshold and min fetch rate above 0.

## Related pages

- [Monitoring producers, consumers, Connect and Streams](client-metrics.md)
- [Replication](../concepts/replication.md)
- [KRaft cluster setup](../operations/kraft-cluster-setup.md)
