---
type: api-guide
title: Streams Data Types and Serdes
description: How Kafka Streams serializes keys and values — default Serdes in StreamsConfig vs explicit Serdes on Consumed/Produced/Grouped/Materialized, built-in Serdes (String, Long, Bytes, UUID, List, …), JSON, windowed Serdes and their CLI deserializer properties, deprecated windowed configs, writing custom Serdes, deserialization error handling, and migrating from the deprecated kafka-streams-scala library to the Java API.
tags: [streams, serdes, serialization, data-types, scala, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-0403bcff2b9c0905450fa767
    resource: repo://docs/streams/developer-guide/datatypes.md
  - id: openwiki-source-54e8dd1dfa769f8e61545e79
    resource: repo://docs/streams/developer-guide/scala-migration.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Streams Data Types and Serdes

Every Streams application needs **Serdes** (serializer/deserializer pairs) for record keys and values whenever data is materialized — in `stream()`, `table()`, `to()`, `repartition()`, `groupByKey()`, `groupBy()` and state stores. Provide them as **defaults** in configuration, **explicitly** on API calls, or both. Kafka itself treats keys and values as opaque bytes ([protocol](../reference/protocol-and-internals.md#messages-and-record-batches)).

## Default Serdes

`default.key.serde` and `default.value.serde` **default to `null`**, so either set them or always pass Serdes explicitly:

```java
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.StreamsConfig;

Properties settings = new Properties();
// Default serde for keys of data records (here: built-in serde for String type)
settings.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
// Default serde for values of data records (here: built-in serde for Long type)
settings.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.Long().getClass().getName());
```

## Overriding defaults

Pass Serdes via `Consumed`, `Produced`, `Grouped`, `Joined`, `Materialized`, `Repartitioned`:

```java
final Serde<String> stringSerde = Serdes.String();
final Serde<Long> longSerde = Serdes.Long();

// keys: region (String), values: user count (Long)
KStream<String, Long> userCountByRegion = ...;
userCountByRegion.to("RegionCountsTopic", Produced.with(stringSerde, longSerde));

// override only the value Serde, keep the default for keys
userCountByRegion.to("RegionCountsTopic", Produced.valueSerde(Serdes.Long()));
```

You **must** specify Serdes explicitly whenever the actual types differ from the configured defaults — e.g. after `count()` produces `Long` values while the default value Serde is `String`.

### Bad records

Corrupt or ill-formatted records make deserializers throw. Since 1.0 you can handle them with a `DeserializationExceptionHandler` (`deserialization.exception.handler`; built-ins `LogAndFailExceptionHandler` (default) and `LogAndContinueExceptionHandler`) — see [Configuration](configuration.md#error-handling).

## Built-in Serdes

### Primitive and basic types (`kafka-clients`, package `org.apache.kafka.common.serialization`)

| Type | Serde |
| --- | --- |
| `byte[]` | `Serdes.ByteArray()`, `Serdes.Bytes()` |
| `ByteBuffer` | `Serdes.ByteBuffer()` |
| `Double` | `Serdes.Double()` |
| `Integer` | `Serdes.Integer()` |
| `Long` | `Serdes.Long()` |
| `String` | `Serdes.String()` |
| `UUID` | `Serdes.UUID()` |
| `Void` | `Serdes.Void()` |
| `List` | `Serdes.ListSerde()` (configure `default.list.key/value.serde.type` and `.inner` for defaults) |
| `Boolean` | `Serdes.Boolean()` |

**Tip:** `org.apache.kafka.common.utils.Bytes` wraps `byte[]` with proper **equality and ordering** — prefer it over raw `byte[]` (e.g. as store keys).

### JSON

The Streams examples include a basic JSON Serde (`PageViewTypedDemo`), built with `Serdes.serdeFrom(serializer, deserializer)` from JSON serializer/deserializer inner classes. Production apps commonly use their own JSON/Avro/Protobuf Serdes (often with a schema registry — not part of Kafka).

### Windowed Serdes (`kafka-streams`, package `org.apache.kafka.streams.kstream`)

- Serdes: `WindowedSerdes.TimeWindowedSerde<T>`, `WindowedSerdes.SessionWindowedSerde<T>`
- Serializers: `TimeWindowedSerializer<T>`, `SessionWindowedSerializer<T>`
- Deserializers: `TimeWindowedDeserializer<T>`, `SessionWindowedDeserializer<T>`

```java
// Time windowed serde - factory method / constructor (window size 500 ms)
Serde<Windowed<String>> timeWindowedSerde = WindowedSerdes.timeWindowedSerdeFrom(String.class, 500L);
Serde<Windowed<String>> timeWindowedSerde2 = new WindowedSerdes.TimeWindowedSerde<>(Serdes.String(), 500L);

// Session windowed serde
Serde<Windowed<String>> sessionWindowedSerde = WindowedSerdes.sessionWindowedSerdeFrom(String.class);
Serde<Windowed<String>> sessionWindowedSerde2 = new WindowedSerdes.SessionWindowedSerde<>(Serdes.String());

// Individual serializer / deserializer
TimeWindowedSerializer<String> serializer = new TimeWindowedSerializer<>(Serdes.String().serializer());
TimeWindowedDeserializer<String> deserializer = new TimeWindowedDeserializer<>(Serdes.String().deserializer(), 500L);
```

Reading windowed keys with console tools:

```bash
# time windowed keys
bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic windowed-counts --from-beginning \
  --formatter-property print.key=true \
  --formatter-property key.deserializer=org.apache.kafka.streams.kstream.TimeWindowedDeserializer \
  --formatter-property key.deserializer.windowed.inner.deserializer.class=org.apache.kafka.common.serialization.StringDeserializer \
  --formatter-property key.deserializer.window.size.ms=500

# session windowed keys
  --formatter-property key.deserializer=org.apache.kafka.streams.kstream.SessionWindowedDeserializer \
  --formatter-property key.deserializer.windowed.inner.deserializer.class=org.apache.kafka.common.serialization.StringDeserializer
```

**Deprecated configs:** `StreamsConfig.WINDOWED_INNER_CLASS_SERDE` (→ `TimeWindowedSerializer.WINDOWED_INNER_SERIALIZER_CLASS` / `TimeWindowedDeserializer.WINDOWED_INNER_DESERIALIZER_CLASS`) and `StreamsConfig.WINDOW_SIZE_MS_CONFIG` (→ `TimeWindowedDeserializer.WINDOW_SIZE_MS_CONFIG`); pass parameters to the constructors instead.

## Custom Serdes

1. Implement `org.apache.kafka.common.serialization.Serializer<T>`.
2. Implement `org.apache.kafka.common.serialization.Deserializer<T>`.
3. Implement `org.apache.kafka.common.serialization.Serde<T>` — manually, or with `Serdes.serdeFrom(serializer, deserializer)`.

```java
public class Order { /* fields */ }

public class OrderSerializer implements Serializer<Order> {
    @Override
    public byte[] serialize(String topic, Order data) {
        return data == null ? null : toJsonBytes(data);
    }
}

public class OrderDeserializer implements Deserializer<Order> {
    @Override
    public Order deserialize(String topic, byte[] bytes) {
        return bytes == null ? null : fromJsonBytes(bytes);
    }
}

Serde<Order> orderSerde = Serdes.serdeFrom(new OrderSerializer(), new OrderDeserializer());
KStream<String, Order> orders = builder.stream("orders", Consumed.with(Serdes.String(), orderSerde));
```

Handle `null` (tombstones) in both directions. Existing Serdes in `org.apache.kafka.common.serialization` are good references.

## Scala: migrating off kafka-streams-scala

> **Deprecation:** `kafka-streams-scala` is **deprecated as of Kafka 4.3 and will be removed in Kafka 5.0** (KIP-1244). Use the Java Streams API directly from Scala.

With the Scala DSL, Serdes came from **implicit** instances for common types (configuring defaults wasn't supported). With the Java API:

1. Use **Java types and classes** directly (`org.apache.kafka.streams.StreamsBuilder`, `org.apache.kafka.streams.kstream.*`) instead of the Scala wrappers.
2. **Configure Serdes explicitly** — defaults in `StreamsConfig` and/or explicit `Produced`/`Consumed` arguments.

Before (deprecated wrapper):

```scala
import org.apache.kafka.streams.scala.ImplicitConversions._
import org.apache.kafka.streams.scala._
import org.apache.kafka.streams.scala.kstream._
import org.apache.kafka.streams.scala.serialization.Serdes._

val builder = new StreamsBuilder  // Scala wrapper
<!-- openwiki: broken internal link ["input-topic"] file ""input-topic"" does not exist. Fix the href or restore the target, then delete this comment. -->
val textLines: KStream[String, String] = builder.stream[String, String]("input-topic")
val wordCounts: KTable[String, Long] = textLines
  .flatMapValues(line => line.toLowerCase.split("\\W+"))
  .groupBy((_, word) => word)
  .count()
wordCounts.toStream.to("output-topic")
```

After (Java API from Scala):

```scala
import java.util.Properties
import org.apache.kafka.streams.{KafkaStreams, StreamsBuilder, StreamsConfig}
import org.apache.kafka.streams.kstream.{KStream, KTable, Produced}
import org.apache.kafka.common.serialization.Serdes
import scala.jdk.CollectionConverters._

object WordCountJava extends App {
  val props = new Properties()
  props.put(StreamsConfig.APPLICATION_ID_CONFIG, "wordcount")
  props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092")
  // Configure default serdes
  props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, classOf[Serdes.StringSerde])
  props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, classOf[Serdes.StringSerde])

  val builder = new StreamsBuilder  // Java StreamsBuilder
<!-- openwiki: broken internal link ["input-topic"] file ""input-topic"" does not exist. Fix the href or restore the target, then delete this comment. -->
  val textLines = builder.stream[String, String]("input-topic")

  val wordCounts = textLines
    .flatMapValues(_.toLowerCase.split("\\W+"))
    .groupBy((_, word) => word)
    .count()

  wordCounts.toStream.to("output-topic", Produced.`with`(Serdes.String(), Serdes.Long()))

  val streams = new KafkaStreams(builder.build(), props)
  streams.start()
}
```

Note `Produced.\`with\`(...)` (backticks because `with` is a Scala keyword) and the explicit `Long` value Serde for counts.

## Related pages

- [Streams DSL](dsl-api.md)
- [Configuration](configuration.md)
- [Writing a Streams application](writing-an-application.md)
