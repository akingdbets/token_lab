---
type: operations-guide
title: Geo-Replication with MirrorMaker 2
description: Replicating data between Kafka clusters with MirrorMaker 2 — replication flows ({source}->{target}), connect-mirror-maker.properties syntax, per-cluster and per-client overrides, topic/group filters and defaults, exactly-once (3.5.0+), securing flows, remote topic naming with ReplicationPolicy, avoiding config conflicts, deployment patterns (active/passive, active/active, multi-DC), running with --clusters, monitoring metrics, and multi-datacenter design advice.
tags: [geo-replication, mirrormaker, disaster-recovery, multi-datacenter, connect, operations]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-633b9faf62392487a36897b8
    resource: repo://docs/operations/datacenters.md
  - id: openwiki-source-d8d9971b9f962e58be1fa69b
    resource: repo://docs/operations/geo-replication-(cross-cluster-data-mirroring).md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Geo-Replication with MirrorMaker 2

## When you need it

Data flows across clusters, datacenters or regions are needed for geo-replication, disaster recovery, feeding edge clusters into a central aggregate cluster, isolating clusters (production vs testing), cloud migration and hybrid cloud, and legal/compliance requirements.

**MirrorMaker (version 2)** replicates data between Kafka environments in a streaming way. It is built on **Kafka Connect** and:

- replicates topics (data plus configurations),
- replicates consumer groups including offsets (to migrate applications),
- replicates ACLs,
- preserves partitioning,
- detects new topics and partitions automatically,
- provides metrics such as end-to-end replication latency,
- is fault-tolerant and horizontally scalable.

This **inter-cluster** replication is different from Kafka's **intra-cluster** [replication](../concepts/replication.md).

## Replication flows

A **replication flow** is a directional `{source_cluster}->{target_cluster}` pair. MirrorMaker uses connectors to consume from sources and produce to targets. Patterns:

| Pattern | Flows |
| --- | --- |
| Active/Active HA | `A->B, B->A` |
| Active/Passive (standby) HA | `A->B` |
| Aggregation | `A->K, B->K, C->K` |
| Fan-out | `K->A, K->B, K->C` |
| Forwarding | `A->B, B->C, C->D` |

By default a flow replicates all topics and consumer groups except excluded ones; each flow can be configured independently.

```properties
# Basic settings
clusters = primary, secondary
primary.bootstrap.servers = broker3-primary:9092
secondary.bootstrap.servers = broker5-secondary:9092

# Define replication flows
primary->secondary.enabled = true
primary->secondary.topics = foobar-topic, quux-.*
```

## Configuration file syntax (`connect-mirror-maker.properties`)

The file configures three kinds of settings: MirrorMaker settings (cluster aliases, per-flow settings), Kafka Connect and connector settings, and producer/consumer/admin client settings. These sections describe a **dedicated MirrorMaker cluster**; running inside an existing Connect cluster is described in KIP-382 and may use different config names.

```properties
# Global settings
clusters = us-west, us-east   # defines cluster aliases
us-west.bootstrap.servers = broker3-west:9092
us-east.bootstrap.servers = broker5-east:9092

topics = .*   # all topics to be replicated by default

# Specific replication flow settings (here: flow from us-west to us-east)
us-west->us-east.enabled = true
us-west->us-east.topics = foo.*, bar.*  # override the default above
```

- **Connect settings** are used directly, without prefixes, e.g. `tasks.max = 5`. Defaults are fine except `tasks.max`: set it to **at least 2** (preferably higher, depending on hardware and partitions) to spread work across MirrorMaker processes.
- **Per-cluster worker settings:** `{cluster}.{config_name}`, e.g. `us-west.offset.storage.topic = my-mirrormaker-offsets`.
- **Client overrides:** `{source}.consumer.{consumer_config}`, `{target}.producer.{producer_config}`, `{source_or_target}.admin.{admin_config}`:

```properties
# us-west cluster (from which to consume)
us-west.consumer.isolation.level = read_committed
us-west.admin.bootstrap.servers = broker57-primary:9092

# us-east cluster (to which to produce)
us-east.producer.compression.type = gzip
us-east.producer.buffer.memory = 32768
us-east.admin.bootstrap.servers = broker8-secondary:9092
```

The shipped sample `config/connect-mirror-maker.properties` defines a bidirectional `A`/`B` setup with `A->B.topics = .*`, `B->A.topics = .*` and replication factors of 1 for development:

```properties
clusters = A, B
A.bootstrap.servers = A_host1:9092, A_host2:9092, A_host3:9092
B.bootstrap.servers = B_host1:9092, B_host2:9092, B_host3:9092
A->B.enabled = true
A->B.topics = .*
B->A.enabled = true
B->A.topics = .*
replication.factor=1
checkpoints.topic.replication.factor=1
heartbeats.topic.replication.factor=1
offset-syncs.topic.replication.factor=1
offset.storage.replication.factor=1
status.storage.replication.factor=1
config.storage.replication.factor=1
```

## Creating and configuring flows

Required:

- `clusters` — comma-separated cluster aliases.
- `{clusterAlias}.bootstrap.servers` — bootstrap brokers for each alias.
- `{source}->{target}.enabled = true` — flows are directional and **disabled by default**; enable both directions for bidirectional replication.

Flow settings combine top-level defaults with `{source}->{target}.{config.name}` overrides. Most important:

| Setting | Default | Meaning |
| --- | --- | --- |
| `topics` | `.*` | Topics (list or regex) to replicate. |
| `topics.exclude` | `.*[\-\.]internal, .*\.replica, __.*` | Topics excluded after matching `topics`. |
| `groups` | `.*` | Consumer groups to replicate. |
| `groups.exclude` | `console-consumer-.*, connect-.*, __.*` | Groups excluded after matching `groups`. |
| `{source}->{target}.enabled` | `false` | Enable the flow. |

```properties
# Custom top-level defaults that apply to all replication flows
topics = .*
groups = consumer-group1, consumer-group2

# Don't forget to enable a flow!
us-west->us-east.enabled = true

# Custom settings for specific replication flows
us-west->us-east.topics = foo.*
us-west->us-east.groups = bar.*
us-west->us-east.emit.heartbeats = false
```

Note: groups created by `kafka-console-consumer.sh` are **not** replicated by default (`console-consumer-.*` is excluded) — adjust `groups.exclude` temporarily if you test with console consumers. Other settings (MirrorMaker common, source, checkpoint and heartbeat connector configs) are in the generated MirrorMaker config reference (`mirror_connector_config.html`, `mirror_source_config.html`, `mirror_checkpoint_config.html`, `mirror_heartbeat_config.html`).

## Remote topic naming

Replicated (**remote**) topics are renamed by a **replication policy** so records from different clusters never land in the same topic-partition. `DefaultReplicationPolicy` names them `{source}.{source_topic_name}`:

```text
us-west         us-east
=========       =================
                bar-topic
foo-topic  -->  us-west.foo-topic
```

```properties
# Defining a custom separator (default ".")
us-west->us-east.replication.policy.separator = _
```

For full control implement a custom `ReplicationPolicy` and set `replication.policy.class` (default `DefaultReplicationPolicy`). Because remote topics are prefixed, **active/active flows defined in the same config file don't create replication loops** — no extra `topics.exclude` is needed.

## Exactly-once (since 3.5.0)

Supported for **dedicated MirrorMaker clusters as of 3.5.0**.

```properties
# new clusters: enable for each target written with exactly-once
us-east.exactly.once.source.support = enabled

# required: intra-cluster REST communication between MirrorMaker nodes (KIP-710)
dedicated.mode.enable.internal.rest = true
listeners = http://localhost:8080

# recommended: drop records of aborted transactions from sources
us-west.consumer.isolation.level = read_committed
```

For existing clusters, first set `exactly.once.source.support = preparing` on all nodes, then `enabled` in a second round of restarts. **Secure the internal REST servers in production** using the Connect REST configs. See [Connect exactly-once](../connect/rest-api-and-operations.md#exactly-once-support).

## Securing flows

MirrorMaker supports the same security settings as Kafka Connect, scoped per cluster alias:

```properties
us-east.security.protocol=SSL
us-east.ssl.truststore.location=/path/to/truststore.jks
us-east.ssl.truststore.password=my-secret-password
us-east.ssl.keystore.location=/path/to/keystore.jks
us-east.ssl.keystore.password=my-secret-password
us-east.ssl.key.password=my-secret-password
```

## Preventing configuration conflicts

MirrorMaker processes share configuration **via their target clusters**. If two processes targeting cluster `B` disagree, the elected leader wins and only one config applies:

```properties
# Configuration of process 1
A->B.enabled = true
A->B.topics = foo

# Configuration of process 2
A->B.enabled = true
A->B.topics = bar
```

Here either `foo` or `bar` is replicated, not both. Keep configs consistent for all flows to the same target — e.g. one shared config file managed by automation.

## Best practice: consume from remote, produce to local

Producers suffer more from unreliable/high-latency links than consumers, so run MirrorMaker **close to the target cluster** and name the local clusters with `--clusters` (space-separated aliases). This also stops the process from producing or sending config to remote clusters.

```text
First DC          Second DC
==========        =========================
primary --------- MirrorMaker --> secondary
(remote)                           (local)
```

```bash
# Run in secondary's data center, reading from the remote `primary` cluster
$ bin/connect-mirror-maker.sh connect-mirror-maker.properties --clusters secondary
```

## Example deployments

**Active/passive:**

```properties
# Unidirectional flow (one-way) from primary to secondary cluster
primary.bootstrap.servers = broker1-primary:9092
secondary.bootstrap.servers = broker2-secondary:9092

primary->secondary.enabled = true
secondary->primary.enabled = false

primary->secondary.topics = foo.*  # only replicate some topics
```

**Active/active:**

```properties
# Bidirectional flow (two-way) between us-west and us-east clusters
clusters = us-west, us-east
us-west.bootstrap.servers = broker1-west:9092,broker2-west:9092
us-east.bootstrap.servers = broker3-east:9092,broker4-east:9092

us-west->us-east.enabled = true
us-east->us-west.enabled = true
```

**Multi-cluster, three datacenters** (two clusters per DC; active/active inside each DC plus cross-DC replication via `west-1`, `east-1`, `north-1`):

```properties
clusters: west-1, west-2, east-1, east-2, north-1, north-2
# ... bootstrap.servers for each ...
west-1->west-2.enabled = true
west-2->west-1.enabled = true
east-1->east-2.enabled = true
east-2->east-1.enabled = true
north-1->north-2.enabled = true
north-2->north-1.enabled = true
west-1->east-1.enabled  = true
west-1->north-1.enabled = true
east-1->west-1.enabled  = true
east-1->north-1.enabled = true
north-1->west-1.enabled = true
north-1->east-1.enabled = true
```

```bash
# In West DC:
$ bin/connect-mirror-maker.sh connect-mirror-maker.properties --clusters west-1 west-2
# In East DC:
$ bin/connect-mirror-maker.sh connect-mirror-maker.properties --clusters east-1 east-2
# In North DC:
$ bin/connect-mirror-maker.sh connect-mirror-maker.properties --clusters north-1 north-2
```

`--clusters` is optional but avoids cross-DC "producer lag" and data transfer costs.

## Starting, stopping and changing

```bash
$ bin/connect-mirror-maker.sh connect-mirror-maker.properties
$ kill <MirrorMaker pid>        # SIGTERM to stop
```

- Run as many processes as needed: processes replicating the same clusters find each other, share configuration and load-balance (Connect distributed mode). Add processes to raise throughput.
- It can take a few minutes after startup before replication begins.
- **Configuration changes require restarting** the MirrorMaker processes.

## Monitoring

MirrorMaker inherits all Connect metrics (e.g. `source-record-poll-rate`) and adds its own under `kafka.connect.mirror`, tagged with `source`, `target`, `topic` (the remote topic, e.g. `primary.topic1`) and `partition`:

```text
# MBean: kafka.connect.mirror:type=MirrorSourceConnector,target=([-.w]+),topic=([-.w]+),partition=([0-9]+)
record-count            # number of records replicated source -> target
record-rate             # average number of records/sec in replicated records
record-age-ms           # age of records when they are replicated
record-age-ms-min / -max / -avg
replication-latency-ms  # time it takes records to propagate source->target
replication-latency-ms-min / -max / -avg
byte-rate               # average number of bytes/sec in replicated records
byte-count              # number of bytes replicated source -> target

# MBean: kafka.connect.mirror:type=MirrorCheckpointConnector,source=([-.w]+),target=([-.w]+),group=([-.w]+),topic=([-.w]+),partition=([0-9]+)
checkpoint-latency-ms   # time it takes to replicate consumer offsets
checkpoint-latency-ms-min / -max / -avg
```

These metrics don't distinguish create-time from log-append-time timestamps.

## Multi-datacenter design

- **Recommended:** a local Kafka cluster per datacenter; applications talk only to their local cluster; mirror between clusters. Each DC can operate independently when inter-DC links fail — mirroring falls behind and catches up when the link returns.
- For a **global view**, mirror all local clusters into **aggregate clusters** used by applications needing the full data set.
- Reading/writing a remote cluster over the WAN is possible but adds latency. Kafka's batching keeps throughput high over high-latency links, but you may need larger TCP buffers (`socket.send.buffer.bytes`, `socket.receive.buffer.bytes` on producer, consumer and broker; size them by the bandwidth-delay product).
- Generally **don't run a single cluster spanning datacenters over a high-latency link**: writes incur very high replication latency, and availability suffers when the inter-DC network fails.

## Related pages

- [Kafka Connect: running workers](../connect/overview-and-running.md)
- [Multi-tenancy and geo-replication](quotas-and-multi-tenancy.md)
- [Hardware, OS and deployment](hardware-os-and-deployment.md)
