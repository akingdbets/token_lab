---
type: operations-reference
title: Monitoring Producers, Consumers, Connect and Streams
description: Client-side Kafka metrics and their MBeans — common and per-broker network metrics, producer buffer and transaction timing, consumer poll and new-protocol queue metrics, consumer group coordinator metrics, share consumer metrics, Connect worker metrics, and the Kafka Streams 4-level metric hierarchy (client, thread, task, processor node, state store, RocksDB, record cache) with recording levels.
tags: [monitoring, metrics, jmx, producer, consumer, connect, streams, share-consumer]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-82a79fdc3cb35121a3a2ee62
    resource: repo://docs/operations/monitoring.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Monitoring Producers, Consumers, Connect and Streams

Java clients register metrics in Kafka Metrics and expose them over **JMX** (`metric.reporters` default `org.apache.kafka.common.metrics.JmxReporter`). Each rate metric has a `-total` counterpart. Clients can additionally **push** metrics to the cluster when `enable.metrics.push=true` (default for producer and consumer) and a matching client-metrics subscription exists. Recording detail is controlled by `metrics.recording.level` (`INFO` default, `DEBUG`, `TRACE`). Broker-side metrics are in [Brokers and KRaft](broker-and-kraft-metrics.md).

## What to watch first

- **Producers:** record/byte send rate, request latency, `buffer-available-bytes`, `waiting-threads`, `buffer-exhausted-rate`, errors and retries.
- **Consumers:** **max lag** across partitions (`records-lag-max`) and **min fetch rate** — to keep up, max lag must stay under a threshold and fetch rate above 0; `time-between-poll-max` vs `max.poll.interval.ms`; rebalance rate.
- **Everyone:** request/byte rates (global and per topic), request size and time, authentication failures, GC and CPU of the client host.

## Common metrics (producer, consumer, Connect, Streams)

MBean: `kafka.[producer|consumer|connect]:type=[producer|consumer|connect]-metrics,client-id=([-.\w]+)`

| Group | Metrics |
| --- | --- |
| Connections | `connection-count`, `connection-creation-rate`/`-total`, `connection-close-rate`/`-total` |
| Network I/O | `network-io-rate`/`-total`, `outgoing-byte-rate`/`-total`, `incoming-byte-rate`/`-total`, `select-rate`/`-total` |
| Requests | `request-rate`/`-total`, `request-size-avg`/`-max`, `response-rate`/`-total` |
| I/O thread | `io-wait-time-ns-avg`/`-total`, `io-wait-ratio`, `io-time-ns-avg`/`-total`, `io-ratio` |
| Authentication | `successful-authentication-rate`/`-total`, `failed-authentication-rate`/`-total`, `successful-reauthentication-rate`/`-total`, `failed-reauthentication-rate`/`-total`, `reauthentication-latency-avg`/`-max`, `successful-authentication-no-reauth-total` (pre-2.2.0 SASL clients) |

### Per-broker (node) metrics

MBean: `kafka.[producer|consumer|connect]:type=[consumer|producer|connect]-node-metrics,client-id=…,node-id=…`

`outgoing-byte-rate`/`-total`, `incoming-byte-rate`/`-total`, `request-rate`/`-total`, `request-size-avg`/`-max`, **`request-latency-avg`/`-max`**, `response-rate`/`-total` — useful to find one slow broker.

## Producer metrics

MBean: `kafka.producer:type=producer-metrics,client-id=([-.\w]+)`

| Metric | Meaning |
| --- | --- |
| `waiting-threads` | User threads blocked waiting for buffer memory. |
| `buffer-total-bytes` / `buffer-available-bytes` | Buffer capacity (`buffer.memory`) and unused part. |
| `buffer-exhausted-rate` / `-total` | Sends dropped due to buffer exhaustion. |
| `bufferpool-wait-ratio`, `bufferpool-wait-time-ns-total` | Time appenders wait for buffer space. |
| `flush-time-ns-total` | Time spent in `Producer.flush`. |
| `txn-init-time-ns-total`, `txn-begin-time-ns-total`, `txn-send-offsets-time-ns-total`, `txn-commit-time-ns-total`, `txn-abort-time-ns-total` | Time in each transactional API (EOS). |
| `metadata-wait-time-ns-total` | Time waiting for metadata. |

The **producer sender metrics** (record send/retry/error rates, batch sizes, compression rate, request latency, per-topic metrics) are generated into `producer_metrics.html`. Low `buffer-available-bytes` with rising `waiting-threads` means the producer is throttled by the network or brokers — see [Producer](../clients/producer.md) tuning (`buffer.memory`, `batch.size`, `linger.ms`).

## Consumer metrics

MBean: `kafka.consumer:type=consumer-metrics,client-id=([-.\w]+)`

| Metric | Meaning |
| --- | --- |
| `time-between-poll-avg` / `-max` | Delay between `poll()` calls — compare with `max.poll.interval.ms`. |
| `last-poll-seconds-ago` | Seconds since the last `poll()`. |
| `poll-idle-ratio-avg` | Fraction of time `poll()` is idle vs. waiting for the application. |
| `committed-time-ns-total`, `commit-sync-time-ns-total` | Time in `committed()` and `commitSync()`. |

With the new **consumer** group protocol (KIP-848 threading model): `application-event-queue-size`, `application-event-queue-time-avg/max`, `application-event-queue-processing-time-avg/max`, `application-events-expired-count`, `background-event-queue-size`, `background-event-queue-time-avg/max`, `background-event-queue-processing-time-avg/max`, `time-between-network-thread-poll-avg/max`, `unsent-requests-queue-size`, `unsent-requests-queue-time-avg/max`.

### Consumer group (coordinator) metrics

MBean: `kafka.consumer:type=consumer-coordinator-metrics,client-id=([-.\w]+)`

`commit-latency-avg/max`, `commit-rate`/`-total`, `assigned-partitions`, `heartbeat-response-time-max`, `heartbeat-rate`/`-total`, `join-time-avg/max`, `join-rate`/`-total`, `sync-time-avg/max`, `sync-rate`/`-total`, `rebalance-latency-avg/max/total`, `rebalance-total`, `rebalance-rate-per-hour`, `failed-rebalance-total`, `failed-rebalance-rate-per-hour`, `last-rebalance-seconds-ago`, `last-heartbeat-seconds-ago`, `partitions-revoked-latency-avg/max`, `partitions-assigned-latency-avg/max`, `partitions-lost-latency-avg/max` (time spent in your `ConsumerRebalanceListener` callbacks).

### Consumer fetch metrics

Generated into `consumer_metrics.html`: fetch rates and latency, bytes/records consumed (per topic and partition) and lag metrics such as `records-lag-max` (attribute of `kafka.consumer:type=consumer-fetch-manager-metrics,client-id={client-id}`), the number of messages the consumer lags behind the producer.

## Share consumer metrics

MBean: `kafka.consumer:type=consumer-share-metrics,…,client-id=([-.\w]+)`

`last-poll-seconds-ago`, `time-between-poll-avg/max`, `poll-idle-ratio-avg`, `heartbeat-response-time-max`, `heartbeat-rate`/`-total`, `last-heartbeat-seconds-ago`, `rebalance-total`, `rebalance-rate-per-hour`, `fetch-size-avg/max`, `records-per-request-avg/max`, `bytes-consumed-rate`/`-total`, `records-consumed-rate`/`-total`, `acknowledgements-send-rate`/`-total`, `acknowledgements-error-rate`/`-total`, `fetch-latency-avg/max`, `fetch-rate`/`-total`, `fetch-throttle-time-avg/max`. See [Share groups](../clients/share-groups.md).

## Connect metrics

A Connect worker exposes **all producer and consumer metrics** plus Connect-specific metrics for the worker itself and for each connector and task (generated into `connect_metrics.html`: worker connector/task counts and startup results, rebalance metrics, connector status, task batch sizes, offset commit success/failure, source poll and sink put rates, and error/DLQ counts). See [Connect REST API and operations](../connect/rest-api-and-operations.md).

## Kafka Streams metrics

A Streams instance exposes all producer and consumer metrics plus Streams metrics in a **4-level hierarchy**: client → stream threads → tasks → processor nodes, with state stores and record caches attached to tasks. Choose what is recorded:

```properties
metrics.recording.level=info
```

(Levels `info`, `debug`, `trace`; Streams' default is `INFO`.)

### Client — `kafka.streams:type=stream-metrics,client-id=…` (info)

`version`, `commit-id`, `application-id`, `topology-description`, `state`, `client-state` (ordinal of the state), `alive-stream-threads`, `failed-stream-threads`, `recording-level` (0 = INFO, 1 = DEBUG, 2 = TRACE).

### Thread — `kafka.streams:type=stream-thread-metrics,thread-id=…` (info)

`state`, `thread-state`; `commit-latency-avg/max`, `poll-latency-avg/max`, `process-latency-avg/max`, `punctuate-latency-avg/max`; `commit-ratio`/`-rate`/`-total`, `poll-ratio`/`-rate`/`-total`, `poll-records-avg/max`, `process-ratio`/`-rate`/`-total`, `process-records-avg/max`, `punctuate-ratio`/`-rate`/`-total`; `task-created-rate`/`-total`, `task-closed-rate`/`-total`; `blocked-time-ns-total`, `thread-start-time`; `tasks-revoked-latency-avg/max`, `tasks-assigned-latency-avg/max`, `tasks-lost-latency-avg/max`.

### Task — `kafka.streams:type=stream-task-metrics,thread-id=…,task-id=…` (debug; `dropped-records-*` and `active-process-ratio` are info)

`process-latency-avg/max`, `process-rate`/`-total`, `punctuate-latency-avg/max`, `punctuate-rate`/`-total`, `record-lateness-avg/max`, `enforced-processing-rate`/`-total`, **`dropped-records-rate`/`-total`**, `active-process-ratio`, `active-buffer-count`, `input-buffer-bytes-total`, `cache-size-bytes-total`, `record-rate`/`-total`, `update-rate`/`-total`.

### Processor node (debug; `record-e2e-latency-*` are info)

`bytes-consumed-total`, `bytes-produced-total`, `records-consumed-total`, `records-produced-total` (topic-level, `kafka.streams:type=stream-topic-metrics,…`), `process-rate`/`-total` (source nodes), `suppression-emit-rate`/`-total` (suppression nodes), `emit-final-latency-avg/max`, `emit-final-records-rate`/`-total` (windowed aggregations), `record-e2e-latency-avg/max/min` (source and terminal nodes), `Idempotent-update-skip-rate`/`-total`. At terminal nodes, all records in a batch share one completion time, so end-to-end latency values are **upper bounds** (biased up by at most the batch duration); `record-e2e-latency-min` is not a lower bound for any record.

### State store — `kafka.streams:type=stream-state-metrics,thread-id=…,task-id=…,[store-scope]-id=…` (debug; `record-e2e-latency-*` trace; `num-open-iterators`, `num-keys` info)

Latencies (`-avg/-max`) and rates for `put`, `put-if-absent`, `get`, `delete`, `put-all`, `all`, `range`, `prefix-scan`, `commit`, `restore` (and deprecated `flush`); `suppression-buffer-size-avg/max`, `suppression-buffer-count-avg/max`; `record-e2e-latency-avg/max/min`; `num-open-iterators`, `num-keys`, `iterator-duration-avg/max`, `oldest-iterator-open-since-ms`. `store-scope` comes from `StoreSupplier#metricsScope()`; built-ins include `in-memory-state`, `in-memory-lru-state`, `in-memory-window-state`, `rocksdb-state`, `rocksdb-window-state`, `rocksdb-session-state`.

### RocksDB

- **Statistics-based** (debug, because RocksDB statistics cost performance; collected every minute; aggregated over all RocksDB instances of window/session stores): `bytes-written-rate`/`-total`, `bytes-read-rate`/`-total`, `memtable-bytes-flushed-rate`/`-total`, `memtable-hit-ratio`, `memtable-flush-time-avg/min/max`, `block-cache-data-hit-ratio`, `block-cache-index-hit-ratio`, `block-cache-filter-hit-ratio`, `write-stall-duration-avg`/`-total`, `bytes-read-compaction-rate`, `bytes-written-compaction-rate`, `compaction-time-avg/min/max`, `number-open-files`, `number-file-errors-total`.
- **Properties-based** (info, recorded when accessed): `num-immutable-mem-table`, `cur-size-active-mem-table`, `cur-size-all-mem-tables`, `size-all-mem-tables`, `num-entries-active-mem-table`, `num-entries-imm-mem-tables`, `num-deletes-active-mem-table`, `num-deletes-imm-mem-tables`, `mem-table-flush-pending`, `num-running-flushes`, `compaction-pending`, `num-running-compactions`, `estimate-pending-compaction-bytes`, `total-sst-files-size`, `live-sst-files-size`, `num-live-versions`, `block-cache-capacity`, `block-cache-usage`, `block-cache-pinned-usage`, `estimate-num-keys`, `estimate-table-readers-mem`, `background-errors`.

### Record cache — `kafka.streams:type=stream-record-cache-metrics,thread-id=…,task-id=…,record-cache-id=…` (debug)

`hit-ratio-avg`, `hit-ratio-min`, `hit-ratio-max`. Cache sizing: [State stores and memory management](../streams/state-stores-and-interactive-queries.md).

## Related pages

- [Monitoring brokers, KRaft and coordinators](broker-and-kraft-metrics.md)
- [Client configuration](../configuration/client-configuration.md) (`metric.reporters`, `metrics.recording.level`, `enable.metrics.push`)
- [Streams configuration](../streams/configuration.md)
