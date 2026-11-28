---
type: operations-guide
title: Managing Consumer and Share Groups with CLI Tools
description: Operating groups from the command line — checking consumer position and lag, listing all group types with kafka-groups.sh, describing (offsets, members, state), deleting and resetting offsets of consumer groups with kafka-consumer-groups.sh, managing share groups with kafka-share-groups.sh (start offset, members, reset, delete-offsets) and configuring share-group dead-letter queues.
tags: [operations, consumer-groups, share-groups, cli, offsets, kafka-consumer-groups]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-9d23e845134437133a436451
    resource: repo://docs/operations/basic-kafka-operations.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Managing Consumer and Share Groups with CLI Tools

Kafka ships one tool per group type plus a general lister:

| Tool | Class name in docs | Groups |
| --- | --- | --- |
| `bin/kafka-groups.sh` | GroupCommand | List groups of **all** types |
| `bin/kafka-consumer-groups.sh` | ConsumerGroupCommand | Consumer groups (classic and consumer protocol) |
| `bin/kafka-share-groups.sh` | ShareGroupCommand | Share groups |
| `bin/kafka-streams-groups.sh` | — | Streams groups (see [Streams rebalancing](../streams/running-and-rebalancing.md)) |

All tools print their options when run without arguments, and accept client security settings via `--command-config <file>`. Group concepts: [Consumer groups](../clients/consumer-groups-and-rebalance.md), [Share groups](../clients/share-groups.md).

## List all groups

```bash
$ bin/kafka-groups.sh --bootstrap-server localhost:9092 --list
GROUP                    TYPE                     PROTOCOL
my-consumer-group        Consumer                 consumer
my-share-group           Share                    share
```

## Consumer groups

### Checking consumer position and lag

```bash
$ bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group my-group
TOPIC                          PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG        CONSUMER-ID                                       HOST                           CLIENT-ID
my-topic                       0          2               4               2          consumer-1-029af89c-873c-4751-a720-cefd41a669d6   /127.0.0.1                     consumer-1
my-topic                       1          2               3               1          consumer-1-029af89c-873c-4751-a720-cefd41a669d6   /127.0.0.1                     consumer-1
my-topic                       2          2               3               1          consumer-2-42c1abd4-e3b2-425d-a8bb-e1ea49b29bb2   /127.0.0.1                     consumer-2
```

`CURRENT-OFFSET` is the committed offset, `LOG-END-OFFSET` the end of the partition, and `LAG` the difference.

**Authorization note:** for groups using the **consumer** protocol, the admin client needs **DESCRIBE** on all topics the members subscribe to; the classic protocol doesn't require DESCRIBE on all topics.

### List and describe

```bash
$ bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list
test-consumer-group
```

Describe options:

- `--offsets` — the default (same as plain `--describe`).
- `--members` — active members:

```bash
$ bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group my-group --members
CONSUMER-ID                                    HOST            CLIENT-ID       #PARTITIONS
consumer1-3fc8d6f1-581a-4472-bdf3-3515b4aee8c1 /127.0.0.1      consumer1       2
consumer4-117fe4d3-c6c1-4178-8ee9-eb4a3954bee0 /127.0.0.1      consumer4       1
consumer2-e76ea8c3-5d30-4299-9005-47eb41f3d3c4 /127.0.0.1      consumer2       3
consumer3-ecea43e4-1f01-479f-8349-f9130b75d8ee /127.0.0.1      consumer3       0
```

- `--members --verbose` — adds each member's assignment:

```bash
$ bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group my-group --members --verbose
CONSUMER-ID                                    HOST            CLIENT-ID       #PARTITIONS     ASSIGNMENT
consumer1-3fc8d6f1-581a-4472-bdf3-3515b4aee8c1 /127.0.0.1      consumer1       2               topic1(0), topic2(0)
consumer4-117fe4d3-c6c1-4178-8ee9-eb4a3954bee0 /127.0.0.1      consumer4       1               topic3(2)
consumer2-e76ea8c3-5d30-4299-9005-47eb41f3d3c4 /127.0.0.1      consumer2       3               topic2(1), topic3(0,1)
consumer3-ecea43e4-1f01-479f-8349-f9130b75d8ee /127.0.0.1      consumer3       0               -
```

- `--state` — coordinator, assignment strategy, state and member count:

```bash
$ bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group my-group --state
COORDINATOR (ID)          ASSIGNMENT-STRATEGY       STATE                #MEMBERS
localhost:9092 (0)        range                     Stable               4
```

### Delete groups

A group is deleted manually, or automatically when its last committed offset expires. Manual deletion only works when the group has **no active members**:

```bash
$ bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --delete --group my-group --group my-other-group
Deletion of requested consumer groups ('my-group', 'my-other-group') was successful.
```

### Reset offsets

`--reset-offsets` works on **one group at a time**, requires a scope (`--all-topics` or `--topic`, unless using `--from-file`), and the consumers must be **inactive** (KIP-122).

Execution modes:

| Option | Effect |
| --- | --- |
| `--dry-run` | Show what would be reset (**default**). |
| `--execute` | Perform the reset. |
| `--export` | Emit the plan as CSV. |

Scenarios:

| Option | Target |
| --- | --- |
| `--to-datetime <YYYY-MM-DDThh:mm:ss.sss>` | Offsets at a timestamp |
| `--to-earliest` / `--to-latest` | Log start / log end |
| `--shift-by <n>` | Current offset ± n |
| `--from-file <csv>` | Values from a CSV file |
| `--to-current` | Current offset |
| `--by-duration <PnDTnHnMnS>` | Offset at now minus duration |
| `--to-offset <n>` | A specific offset |

Out-of-range results are clamped to the available range (e.g. shifting by 15 when the end is 10 selects 10).

```bash
# preview (dry run is the default)
$ bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --reset-offsets --group my-group --topic topic1 --to-latest
TOPIC                          PARTITION  NEW-OFFSET
topic1                         0          0

# apply
$ bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --reset-offsets --group my-group --topic topic1 --to-earliest --execute

# rewind one hour on all topics
$ bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --reset-offsets --group my-group --all-topics --by-duration PT1H --execute
```

## Share groups

### List and describe

```bash
$ bin/kafka-share-groups.sh --bootstrap-server localhost:9092 --list
my-share-group

$ bin/kafka-share-groups.sh --bootstrap-server localhost:9092 --describe --group my-share-group
GROUP           TOPIC           PARTITION  START-OFFSET  LAG
my-share-group  topic1          0          4             0
```

The **start offset** is the earliest offset of in-flight records still being evaluated for delivery; some records after it may already be fully delivered. The admin client needs **DESCRIBE** on all topics used in the group.

Describe options: `--offsets` (default), `--members` and `--state`:

```bash
$ bin/kafka-share-groups.sh --bootstrap-server localhost:9092 --describe --group my-share-group --members
GROUP           CONSUMER-ID            HOST            CLIENT-ID              #PARTITIONS  ASSIGNMENT
my-share-group  94wrSQNmRda9Q6sk6jMO6Q /127.0.0.1      console-share-consumer 1            topic1:0
my-share-group  EfI0sha8QSKSrL_-I_zaTA /127.0.0.1      console-share-consumer 1            topic1:0

$ bin/kafka-share-groups.sh --bootstrap-server localhost:9092 --describe --group my-share-group --state
GROUP           COORDINATOR (ID)          STATE           #MEMBERS
my-share-group  localhost:9092  (1)       Stable          2
```

Note both members share partition `topic1:0`.

### Reset offsets

Same execution modes (`--dry-run`, `--execute`, `--export`) and scenarios `--to-datetime`, `--to-earliest`, `--to-latest`, `--from-file`, `--to-current`, `--to-offset`:

```bash
$ bin/kafka-share-groups.sh --bootstrap-server localhost:9092 --reset-offsets --group my-share-group --topic topic1 --to-latest --execute
GROUP           TOPIC           PARTITION  NEW-OFFSET
my-share-group  topic1          0          10
```

Seed a share group from an inactive consumer group's offsets:

```bash
$ bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --reset-offsets --group my-group --all-topics --to-current --dry-run --export > FILE.CSV

$ bin/kafka-share-groups.sh --bootstrap-server localhost:9092 --reset-offsets --group my-share-group --from-file FILE.CSV --execute
GROUP           TOPIC           PARTITION  NEW-OFFSET
my-share-group  topic1          0          10
```

### Delete offsets or groups

Only share groups **without active members** can be deleted.

```bash
$ bin/kafka-share-groups.sh --bootstrap-server localhost:9092 --delete-offsets --group my-share-group --topic topic1
TOPIC           STATUS
topic1          Successful

$ bin/kafka-share-groups.sh --bootstrap-server localhost:9092 --delete --group my-share-group
Deletion of requested share groups ('my-share-group') was successful.
```

### Dead-letter queues

Requires `share.version` ≥ 2. Configure with `kafka-configs.sh`:

```bash
$ bin/kafka-features.sh --bootstrap-server localhost:9092 describe | grep share.version

# DLQ topic for the group
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config "errors.deadletterqueue.topic.name=dlq.gs1dlqtopic" --entity-type groups --entity-name my-share-group

# allow auto-creation of DLQ topics (cluster-wide, default false)
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config "errors.deadletterqueue.auto.create.topics.enable=true" --entity-type brokers --entity-default

# mark a self-created topic as DLQ-capable
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config "errors.deadletterqueue.group.enable=true" --entity-type topics --entity-name dlq.gs1dlqtopic

# change the required DLQ name prefix (default "dlq.")
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config "errors.deadletterqueue.topic.name.prefix=com.mycompany.dlq." --entity-type brokers --entity-default

# copy source key/value into DLQ records (default: metadata only)
$ bin/kafka-configs.sh --bootstrap-server localhost:9092 --alter --add-config "errors.deadletterqueue.copy.record.enable=true" --entity-type groups --entity-name my-share-group
```

Details: [Share groups](../clients/share-groups.md#dead-letter-queues-dlq).

## Related pages

- [Consumer groups and rebalance protocols](../clients/consumer-groups-and-rebalance.md)
- [Share groups](../clients/share-groups.md)
- [Topic and group configuration](../configuration/topic-and-group-configuration.md)
- [Basic operations](topic-and-cluster-administration.md)
