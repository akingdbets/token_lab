---
type: operations-guide
title: Hardware, OS and Production Deployment
description: Production deployment guidance for Kafka brokers and controllers — hardware sizing (memory, disks), OS limits (file descriptors, vm.max_map_count, socket buffers), multiple disks vs RAID, why application fsync is not needed, Linux page-cache flushing, XFS vs EXT4 and mount options, safely replacing a KRaft controller's metadata disk, JVM settings and datacenter layout.
tags: [operations, hardware, os, filesystem, xfs, ext4, jvm, deployment, kraft]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-5a0e50615cb9ac0f604cd6d1
    resource: repo://docs/operations/hardware-and-os.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Hardware, OS and Production Deployment

## Hardware

The reference deployment in the docs uses dual quad-core Intel Xeon machines with 24 GB of memory and 8× 7200 rpm SATA drives.

- **Memory:** enough to buffer active readers and writers. Back-of-the-envelope: buffer 30 seconds → `write_throughput * 30`. Kafka relies on the OS page cache, so leave memory outside the JVM heap (see [Storage](../concepts/storage-and-retention.md)).
- **Disks:** disk throughput is usually the bottleneck — more disks are better. If you force frequent flushes, faster (higher-RPM SAS) disks may help; with default flush settings cheap high-capacity disks work well.

## OS

Kafka runs well on any Unix system and is tested on Linux and Solaris. **Windows is not currently well supported.** Little OS tuning is needed, but three settings matter:

| Setting | Guidance |
| --- | --- |
| **File descriptor limit** | Kafka uses FDs for log segments and connections. A broker needs at least `number_of_partitions * (partition_size / segment_size)` for segments plus connections. Start with **at least 100000** allowed FDs. (`mmap()` adds a reference to a file that isn't released by `close()` until the mapping is gone.) |
| **Max socket buffer size** | Increase for high-performance inter-datacenter transfer. |
| **`vm.max_map_count`** | Often ~65535 by default. Each log segment needs an index and a timeindex file = **2 map areas**, so each partition needs at least 2. 50000 partitions on one broker → 100000 map areas, likely crashing with `OutOfMemoryError (Map failed)` at the default. Partitions usually have more than one segment. |

Example Linux settings:

```bash
# /etc/security/limits.conf (kafka user)
kafka  soft  nofile  100000
kafka  hard  nofile  100000

# sysctl
sysctl -w vm.max_map_count=262144
```

## Disks and filesystem layout

- Use **multiple drives** for throughput and **don't share them** with application logs or other OS activity, to keep latency low.
- Either RAID them into one volume or mount each drive as its own directory in `log.dirs`:
  - **Multiple data directories (JBOD):** partitions are assigned **round-robin** to directories; each partition lives entirely in one directory, so skewed partitions can unbalance disks. Kafka's replication provides redundancy at the application level.
  - **RAID:** may balance load better, but usually costs significant **write throughput** and disk space; RAID rebuilds are so I/O-intensive they effectively disable the server, so availability gains are small.

```properties
log.dirs=/data/dir1,/data/dir2,/data/dir3
```

Decommissioning a log directory is described in [Basic operations](topic-and-cluster-administration.md).

## Flush management: application vs OS

Kafka always writes data to the filesystem immediately; flush policy only controls when it is **forced** from the OS cache to disk (by time or by message count — `flush.ms`/`log.flush.interval.ms`, `flush.messages`/`log.flush.interval.messages`).

- Kafka must eventually `fsync`. On crash recovery, any segment not known to be fsync'd is checked message by message (CRC) and its offset index is rebuilt.
- **Durability does not require syncing to disk**: a failed node always recovers from its replicas.
- **Recommendation: keep the defaults**, which disable application fsync and rely on the OS and Kafka's background flush — no knobs, great throughput and latency, full recovery guarantees. Application-level fsync is still supported for the paranoid, but it gives the OS less freedom to reorder writes and adds latency because `fsync` blocks writes to the file on most Linux filesystems.

### Linux page cache flushing

Written data stays in page cache until an application `fsync` or the OS flush policy writes it out, done by background "flusher threads" (`pdflush` in older kernels). If they can't keep up, writers block. Inspect memory state with:

```bash
$ cat /proc/meminfo
```

The page cache batches small writes, re-sequences writes to reduce seeks, and automatically uses all free memory.

## Filesystem choice

Kafka uses regular files and doesn't require a specific filesystem; **EXT4** and **XFS** are most common. XFS has shown **better performance for Kafka** with no stability compromise: in comparison testing (monitoring "Request Local Time" for appends) XFS achieved about **160 ms vs 250 ms+** for the best EXT4 configuration, with lower and less variable wait times.

**All filesystems:** mount data directories with **`noatime`** — Kafka never uses atime, and this eliminates many writes (especially when consumers bootstrap).

**XFS:** auto-tunes well; no changes needed. Optional: `largeio` (minimal effect in practice), `nobarrier` (slight gain on devices with battery-backed cache; no effect on well-behaved devices).

**EXT4:** serviceable but needs mount tuning for best performance — and those options are **unsafe on failure** (more data loss/corruption, e.g. after a power outage affecting many brokers):

| Option | Effect |
| --- | --- |
| `data=writeback` | Removes `data=ordered` write ordering Kafka doesn't need; significantly lowers latency. |
| Disable journaling | Removes locking-induced write latency spikes at the cost of slower reboots after crashes. |
| `commit=num_secs` | Lower = less unflushed data lost on crash; higher = more throughput. |
| `nobh` | Drops extra ordering with `data=writeback`; safe for Kafka, improves throughput/latency. |
| `delalloc` | Delayed allocation → larger sequential extents; great for throughput, some latency variance. |
| `fast_commit` | (Linux 5.10+) lighter journaling usable with `data=ordered`; significantly lower latency. |

```bash
# /etc/fstab example
/dev/sdb1  /data/dir1  xfs  defaults,noatime  0 0
```

## Replacing a KRaft controller disk

Controllers store cluster metadata in `metadata.log.dir` (or the first log directory if unset). If that directory is lost (hardware failure or replacement), **don't format and start the new controller until a majority of controllers have all committed data**:

```bash
$ bin/kafka-metadata-quorum.sh --bootstrap-server localhost:9092 describe --replication
NodeId	DirectoryId           	LogEndOffset	Lag	LastFetchTimestamp	LastCaughtUpTimestamp	Status
1     	dDo1k_pRSD-VmReEpu383g	966         	0  	1732367153528     	1732367153528        	Leader
2     	wQWaQMJYpcifUPMBGeRHqg	966         	0  	1732367153304     	1732367153304        	Observer
```

1. Wait until `Lag` is small for a majority of controllers (0 if the leader's end offset isn't moving; otherwise until all reach a chosen leader end offset), and `LastFetchTimestamp` ≈ `LastCaughtUpTimestamp` for the majority.
2. Format the metadata directory:

```bash
$ bin/kafka-storage.sh format --cluster-id uuid --config config/server.properties
```

   If it fails with `Log directory ... is already formatted` — which happens in **combined mode** when only the metadata directory was lost — then, and only then, add `--ignore-formatted`.
3. Start the controller:

```bash
$ bin/kafka-server-start.sh config/server.properties
```

More controller procedures: [KRaft cluster setup](kraft-cluster-setup.md).

## JVM

Run the latest LTS Java (Java 25 at the time of writing; 17, 21, 25 fully supported for servers) with G1 GC:

```bash
-Xmx6g -Xms6g -XX:MetaspaceSize=96m -XX:+UseG1GC
-XX:MaxGCPauseMillis=20 -XX:InitiatingHeapOccupancyPercent=35 -XX:G1HeapRegionSize=16M
-XX:MinMetaspaceFreeRatio=50 -XX:MaxMetaspaceFreeRatio=80 -XX:+ExplicitGCInvokesConcurrent
```

Details and LinkedIn reference numbers: [Compatibility and Java versions](../getting-started/compatibility.md#running-kafka-on-the-jvm).

## Datacenters

- Prefer a **local cluster per datacenter**, with applications using only their local cluster and [MirrorMaker](geo-replication-mirrormaker.md) replicating between clusters; use aggregate clusters for a global view.
- Avoid a **single cluster stretched over a high-latency link** — writes suffer high replication latency and availability depends on the inter-DC network.
- For WAN clients, raise `socket.send.buffer.bytes` / `socket.receive.buffer.bytes` on producers, consumers and brokers based on the bandwidth-delay product.

## Related pages

- [Storage, log segments and retention](../concepts/storage-and-retention.md)
- [Monitoring brokers](../monitoring/broker-and-kraft-metrics.md) (watch GC, CPU, I/O service time)
- [Broker configuration](../configuration/broker-configuration.md)
