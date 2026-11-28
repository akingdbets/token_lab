---
type: operations-guide
title: "Basic Operations: Topics, Brokers and Reassignment"
description: Everyday Kafka administration with the bin/ tools — creating, altering and deleting topics, graceful (controlled) shutdown, preferred leader balancing, rack-aware replica placement, expanding the cluster and moving partitions with kafka-reassign-partitions.sh (generate/execute/verify), decommissioning brokers and log directories with cordoning, increasing replication factor, and throttling replication traffic safely.
tags: [operations, topics, reassignment, kafka-reassign-partitions, decommission, throttling, rack-awareness]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-9d23e845134437133a436451
    resource: repo://docs/operations/basic-kafka-operations.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Basic Operations: Topics, Brokers and Reassignment

All tools live in `bin/` and print their options when run without arguments. Group operations are in [Managing groups](managing-groups.md); quotas in [Quotas and multi-tenancy](quotas-and-multi-tenancy.md); geo-replication in [MirrorMaker](geo-replication-mirrormaker.md).

## Adding and removing topics

Topics can be created manually or auto-created on first publish (tune defaults such as `num.partitions` and `default.replication.factor` if you rely on auto-creation).

```bash
$ bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic my_topic_name \
    --partitions 20 --replication-factor 3 --config x=y
```

- **Replication factor**: how many servers replicate each message. With 3, up to 2 servers can fail before data becomes inaccessible. Use **2 or 3** so machines can be bounced without interrupting consumption.
- **Partition count**: how many logs the topic is sharded into. Each partition must fit on one server (20 partitions → at most 20 servers handle the data and load, excluding replicas), and it caps consumer parallelism.
- Each partition is stored in a folder `<topic>-<partition>` under the log directory, so **topic names are limited to 249 characters**.
- `--config` values override broker defaults (see [Topic configuration](../configuration/topic-and-group-configuration.md)).

```bash
$ bin/kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic my_topic_name
```

## Modifying topics

```bash
# add partitions
$ bin/kafka-topics.sh --bootstrap-server localhost:9092 --alter --topic my_topic_name \
    --partitions 40

# add / remove configs
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name my_topic_name --alter --add-config x=y
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name my_topic_name --alter --delete-config x
```

- **Reducing partitions is not supported.**
- Adding partitions changes `hash(key) % number_of_partitions`, so keys may move to new partitions (existing data is not redistributed).
- Consumers with `auto.offset.reset=latest` may skip records produced to new partitions before they discover them; prefer `by_duration:<duration>` (e.g. `PT5S` for the consumer protocol, `PT6M` for classic). Details in [Topics, partitions and offsets](../concepts/topics-partitions-offsets.md#changing-the-partition-count).
- **Never** add partitions to `__consumer_offsets`, `__transaction_state`, `__share_group_state` or `__cluster_metadata`.

## Graceful shutdown

Kafka detects broker failure or shutdown and elects new leaders either way, but a **graceful** stop adds two optimizations:

1. All logs are synced to disk, so no log recovery (checksum validation of the log tail) is needed on restart.
2. Partitions led by the broker are migrated to other replicas before shutdown, cutting unavailability to a few milliseconds.

Log syncing happens on any stop except a hard kill; leadership migration needs:

```properties
controlled.shutdown.enable=true
```

Controlled shutdown only succeeds if **all** partitions on the broker have other live replicas (replication factor > 1 and at least one other replica alive).

## Balancing leadership

After a restart a broker is only a follower for its partitions. Kafka's **preferred replica** is the first in the replica list (for replicas `1,5,9`, broker 1). By default leadership is moved back automatically:

```properties
auto.leader.rebalance.enable=true
```

If disabled, restore it manually:

```bash
$ bin/kafka-leader-election.sh --bootstrap-server localhost:9092 --election-type preferred --all-topic-partitions
```

Monitor `kafka.controller:type=KafkaController,name=PreferredReplicaImbalanceCount`.

## Balancing replicas across racks

Rack awareness spreads a partition's replicas across racks (or AZs) so a whole-rack failure doesn't lose data:

```properties
broker.rack=my-rack-id
```

On topic creation, modification or redistribution, replicas span `min(#racks, replication-factor)` racks, and the number of leaders per broker stays constant regardless of rack distribution. **Use equal numbers of brokers per rack**: racks with fewer brokers get more replicas, more storage and more replication load.

## Expanding your cluster

New brokers (unique `node.id`, formatted with `kafka-storage.sh format`, see [KRaft setup](kraft-cluster-setup.md#formatting-new-nodes-for-an-existing-cluster)) get **no existing partitions** automatically — only new topics. Migrate data with `kafka-reassign-partitions.sh`. Migration is manually initiated but automated: the new broker is added as a follower, replicates the partition fully, joins the ISR, and then one old replica deletes its copy.

The tool does not analyze load — you decide what to move. Three mutually exclusive modes:

| Mode | Purpose |
| --- | --- |
| `--generate` | Given topics and target brokers, propose an assignment. |
| `--execute` | Start the reassignment in `--reassignment-json-file`. |
| `--verify` | Report status (completed, failed, in progress) of the last `--execute`; also clears throttles. |

### Move whole topics to new brokers

```bash
$ cat topics-to-move.json
{
  "topics": [
    { "topic": "foo1" },
    { "topic": "foo2" }
  ],
  "version": 1
}

$ bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 --topics-to-move-json-file topics-to-move.json --broker-list "5,6" --generate
Current partition replica assignment
{"version":1,
 "partitions":[{"topic":"foo1","partition":0,"replicas":[2,1],"log_dirs":["any"]}, ...]}

Proposed partition reassignment configuration
{"version":1,
 "partitions":[{"topic":"foo1","partition":0,"replicas":[6,5],"log_dirs":["any"]}, ...]}
```

**Save the current assignment for rollback**, save the proposal as `expand-cluster-reassignment.json`, then:

```bash
$ bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 --reassignment-json-file expand-cluster-reassignment.json --execute
...
Save this to use as the --reassignment-json-file option during rollback
Successfully started partition reassignments for foo1-0,foo1-1,foo1-2,foo2-0,foo2-1,foo2-2

$ bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 --reassignment-json-file expand-cluster-reassignment.json --verify
Status of partition reassignment:
Reassignment of partition [foo1,0] is completed
Reassignment of partition [foo1,1] is still in progress
...
```

The replication factor stays the same; afterwards `foo1` and `foo2` live only on brokers 5 and 6.

### Custom moves

Skip `--generate` and hand-craft the plan:

```bash
$ cat custom-reassignment.json
{"version":1,"partitions":[{"topic":"foo1","partition":0,"replicas":[5,6]},{"topic":"foo2","partition":1,"replicas":[2,3]}]}

$ bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 --reassignment-json-file custom-reassignment.json --execute
$ bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 --reassignment-json-file custom-reassignment.json --verify
```

Always pass the **same JSON file** to `--verify` as to `--execute`.

## Decommissioning brokers and log directories

### Decommissioning a broker

1. **Cordon** the broker via the Admin API so no new replicas are placed on it:

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config cordoned.log.dirs="*" --entity-type brokers --entity-name 1
Completed updating config for broker 1.
```

2. Reassign all its partitions to other brokers. The tool can't yet generate a decommission plan automatically, so write it yourself.
3. Shut the broker down and **unregister** it:

```bash
$ bin/kafka-cluster.sh unregister --bootstrap-server localhost:9092 --id 1
```

### Decommissioning a log directory

1. Cordon the directory:

```bash
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config cordoned.log.dirs=/data/dir1 --entity-type brokers --entity-name 1
```

2. Reassign its partitions to other directories or brokers (hand-crafted plan).
3. Shut the broker down.
4. Uncordon via the controller (the broker is offline):

```bash
$ bin/kafka-configs.sh --bootstrap-controller localhost:9093 --alter --delete-config cordoned.log.dirs --entity-type brokers --entity-name 1
Completed updating config for broker 1.
```

5. Remove the directory from `log.dirs` (e.g. `log.dirs=/data/dir1,/data/dir2` → `log.dirs=/data/dir2`) and restart the broker.

## Increasing replication factor

List the extra replicas in a custom plan:

```bash
$ cat increase-replication-factor.json
{"version":1,
 "partitions":[{"topic":"foo","partition":0,"replicas":[5,6,7]}]}

$ bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 --reassignment-json-file increase-replication-factor.json --execute
$ bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 --reassignment-json-file increase-replication-factor.json --verify
Reassignment of partition [foo,0] is completed

$ bin/kafka-topics.sh --bootstrap-server localhost:9092 --topic foo --describe
Topic:foo	PartitionCount:1	ReplicationFactor:3	Configs:
  Topic: foo	Partition: 0	Leader: 5	Replicas: 5,6,7	Isr: 5,6,7
```

## Limiting bandwidth during data migration

Throttle replication traffic so rebalancing, adding/removing brokers or disks doesn't hurt clients. The simplest and safest way is through the reassignment tool:

```bash
# at most 50 MB/s between brokers and 100 MB/s between disks on a broker
$ bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 --execute --reassignment-json-file bigger-cluster.json --throttle 50000000 --replica-alter-log-dirs-throttle 100000000
The inter-broker throttle limit was set to 50000000 B/s
The replica-alter-dir throttle limit was set to 100000000 B/s

# change during the rebalance
$ bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 --additional --execute --reassignment-json-file bigger-cluster.json --throttle 700000000

# verify — removes throttles once complete
$ bin/kafka-reassign-partitions.sh --bootstrap-server localhost:9092 --verify --reassignment-json-file bigger-cluster.json
...
Clearing broker-level throttles on brokers 1,2,3
Clearing topic-level throttles on topic my-topic
```

The tool sets five configs automatically:

- Broker-level (dynamic) rates: `leader.replication.throttled.rate`, `follower.replication.throttled.rate`, `replica.alter.log.dirs.io.max.bytes.per.second`.
- Topic-level replica lists: `leader.replication.throttled.replicas`, `follower.replication.throttled.replicas` (format `partition:broker,...`).

```bash
$ bin/kafka-configs.sh --describe --bootstrap-server localhost:9092 --entity-type brokers
Configs for brokers '2' are leader.replication.throttled.rate=700000000,follower.replication.throttled.rate=700000000,replica.alter.log.dirs.io.max.bytes.per.second=1000000000

$ bin/kafka-configs.sh --describe --bootstrap-server localhost:9092 --entity-type topics
Configs for topic 'my-topic' are leader.replication.throttled.replicas=1:102,0:101,
    follower.replication.throttled.replicas=1:101,0:102
```

By default the leader throttle covers all replicas existing before the move (any could be leader) and the follower throttle covers all move destinations: for replicas `101,102` → `102,103`, leader throttle on 101 and 102, follower throttle on 103. You can also edit these with `kafka-configs.sh --alter`.

### Safe use of throttles

1. **Remove throttles promptly** after completion by running `--verify`; otherwise normal replication stays throttled.
2. **Ensure progress:** replication can stall if `max(BytesInPerSec) > throttle`. Watch `kafka.server:type=FetcherLagMetrics,name=ConsumerLag,clientId=…,topic=…,partition=…` — it should steadily decrease; if not, raise the throttle.

Reassignment progress is also visible via `kafka.server:type=ReplicaManager,name=ReassigningPartitions` and `ReassignmentBytesInPerSec` / `ReassignmentBytesOutPerSec` ([metrics](../monitoring/broker-and-kraft-metrics.md)).

## Related pages

- [Replication, ISR and leader election](../concepts/replication.md)
- [Managing groups](managing-groups.md)
- [Quotas and multi-tenancy](quotas-and-multi-tenancy.md)
- [Admin API](../clients/admin-api.md)
