---
type: configuration-guide
title: Connect Single Message Transforms and Predicates
description: How to configure Kafka Connect single message transforms (SMTs) with transforms/transforms.$alias.type, a worked HoistField + InsertField example, the list of built-in transformations, and how predicates (TopicNameMatches, HasHeaderKey, RecordIsTombstone) with the implicit predicate and negate properties apply transforms conditionally, including filtering with Filter.
tags: [connect, smt, transformations, predicates, configuration]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-0cfab4979b85f5c875d630fd
    resource: repo://docs/kafka-connect/user-guide.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Connect Single Message Transforms and Predicates

**Transformations** (single message transforms, SMTs) make lightweight, **message-at-a-time** modifications in a connector — handy for data massaging and event routing. They run in the Connect worker between the connector and Kafka: for source connectors after the task produces a record, for sink connectors before records reach the task. Heavier processing belongs in [Kafka Streams](../streams/introduction-and-quickstart.md).

## Configuring a transformation chain

In the connector configuration:

| Property | Meaning |
| --- | --- |
| `transforms` | List of aliases, in the order the transformations are applied. |
| `transforms.$alias.type` | Fully qualified class name of the transformation. |
| `transforms.$alias.$transformationSpecificConfig` | Transformation-specific settings. |

Many built-in transforms come in `$Key` and `$Value` variants (e.g. `HoistField$Value`), choosing whether they act on the record key or value.

## Example: wrap lines and add a static field

Using the file source connector with **schemaless JSON** — set `key.converter.schemas.enable` and `value.converter.schemas.enable` to `false` in `connect-standalone.properties`. Then `connect-file-source.properties`:

```properties
name=local-file-source
connector.class=FileStreamSource
tasks.max=1
file=test.txt
topic=connect-test
transforms=MakeMap, InsertSource
transforms.MakeMap.type=org.apache.kafka.connect.transforms.HoistField$Value
transforms.MakeMap.field=line
transforms.InsertSource.type=org.apache.kafka.connect.transforms.InsertField$Value
transforms.InsertSource.static.field=data_source
transforms.InsertSource.static.value=test-file-source
```

- `MakeMap` (**HoistField**) wraps each line string in a map under the field `line`.
- `InsertSource` (**InsertField**) adds `data_source=test-file-source`.

Output before:

```text
"foo"
"bar"
"hello world"
```

After:

```json
{"line":"foo","data_source":"test-file-source"}
{"line":"bar","data_source":"test-file-source"}
{"line":"hello world","data_source":"test-file-source"}
```

## Included transformations

Package `org.apache.kafka.connect.transforms`:

| Transformation | What it does |
| --- | --- |
| `Cast` | Cast fields or the entire key/value to a specific type. |
| `DropHeaders` | Remove headers by name. |
| `ExtractField` | Extract one field from a Struct/Map and keep only it. |
| `Filter` | Remove messages from further processing; used with a predicate to filter selectively. |
| `Flatten` | Flatten a nested data structure. |
| `HeaderFrom` | Copy or move key/value fields into record headers. |
| `HoistField` | Wrap the whole event as a single field inside a Struct or Map. |
| `InsertField` | Add a field from static data or record metadata. |
| `InsertHeader` | Add a header with static data. |
| `MaskField` | Replace a field with a valid null value for its type (0, empty string, …) or a custom replacement (non-empty string or numeric only). |
| `RegexRouter` | Change the record's topic from the original topic, a regex and a replacement string. |
| `ReplaceField` | Filter or rename fields. |
| `SetSchemaMetadata` | Modify the schema name or version. |
| `TimestampConverter` | Convert timestamps between formats. |
| `TimestampRouter` | Change the topic based on original topic and timestamp — e.g. sinks writing to per-time tables/indexes. |
| `ValueToKey` | Replace the key with fields taken from the value. |

Per-transform options are generated in `connect_transforms.html`. Example routing all topics to a prefixed name:

```properties
transforms=Route
transforms.Route.type=org.apache.kafka.connect.transforms.RegexRouter
transforms.Route.regex=(.*)
transforms.Route.replacement=mirror-$1
```

Custom SMTs implement `org.apache.kafka.connect.transforms.Transformation` and need a ServiceLoader manifest for `service_load` discovery (see [connector development](connector-development.md#packaging-for-plugin-discovery)).

## Predicates

Predicates make a transformation apply **only to records that satisfy a condition**. Combined with `Filter` they selectively drop records.

| Property | Meaning |
| --- | --- |
| `predicates` | Set of predicate aliases. |
| `predicates.$alias.type` | Fully qualified predicate class. |
| `predicates.$alias.$predicateSpecificConfig` | Predicate settings. |

Every transformation has two **implicit** properties:

- `predicate` — alias of the predicate that gates it.
- `negate` — reverse the predicate's result.

Built-in predicates (`org.apache.kafka.connect.transforms.predicates`):

| Predicate | Matches |
| --- | --- |
| `TopicNameMatches` | Records whose topic matches the Java regex `pattern`. |
| `HasHeaderKey` | Records with a header of the given key. |
| `RecordIsTombstone` | Tombstones (null value). |

### Example: drop one topic, transform all but another

Goal: drop everything in topic `foo`; apply `ExtractField` (field `other_field`) to all topics **except** `bar`.

```properties
transforms=Filter,Extract
transforms.Filter.type=org.apache.kafka.connect.transforms.Filter
transforms.Filter.predicate=IsFoo

transforms.Extract.type=org.apache.kafka.connect.transforms.ExtractField$Key
transforms.Extract.field=other_field
transforms.Extract.predicate=IsBar
transforms.Extract.negate=true

predicates=IsFoo,IsBar
predicates.IsFoo.type=org.apache.kafka.connect.transforms.predicates.TopicNameMatches
predicates.IsFoo.pattern=foo

predicates.IsBar.type=org.apache.kafka.connect.transforms.predicates.TopicNameMatches
predicates.IsBar.pattern=bar
```

`Filter` gated by `IsFoo` removes `foo` records; `Extract` gated by `IsBar` with `negate=true` runs on everything not in `bar`.

Drop tombstones:

```properties
transforms=DropTombstones
transforms.DropTombstones.type=org.apache.kafka.connect.transforms.Filter
transforms.DropTombstones.predicate=IsTombstone
predicates=IsTombstone
predicates.IsTombstone.type=org.apache.kafka.connect.transforms.predicates.RecordIsTombstone
```

Per-predicate options are generated in `connect_predicates.html`.

## Errors in transforms

By default an exception in a transformation (or converter) fails the task. Use `errors.tolerance`, `errors.log.enable` and `errors.deadletterqueue.topic.name` to tolerate, log or route bad records — see [error reporting](rest-api-and-operations.md#error-reporting-and-dead-letter-queues).

## Related pages

- [Connect overview and workers](overview-and-running.md)
- [REST API and operations](rest-api-and-operations.md)
- [Developing connectors](connector-development.md)
