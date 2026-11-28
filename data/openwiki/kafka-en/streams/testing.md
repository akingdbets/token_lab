---
type: testing-guide
title: Testing Kafka Streams Applications
description: Testing Kafka Streams topologies without a broker using kafka-streams-test-utils — TopologyTestDriver with TestInputTopic and TestOutputTopic, triggering stream-time and wall-clock punctuations, pre-populating and inspecting state stores, a full max-aggregator test example, and unit-testing individual processors with MockProcessorContext (captured forwards, commits, record metadata, stores and punctuators).
tags: [streams, testing, topologytestdriver, test-utils, unit-testing, java]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-18483d7627c6bbd312e7afc2
    resource: repo://docs/streams/developer-guide/testing.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Testing Kafka Streams Applications

Kafka provides a **test-utils** artifact to test Streams code without running a Kafka cluster:

```xml
<dependency>
    <groupId>org.apache.kafka</groupId>
    <artifactId>kafka-streams-test-utils</artifactId>
    <version>4.3.0</version>
    <scope>test</scope>
</dependency>
```

Two tools: **`TopologyTestDriver`** for whole topologies (DSL or Processor API), and **`MockProcessorContext`** for unit-testing a single `Processor`.

## TopologyTestDriver

The driver simulates the Streams runtime: it takes records you pipe in, processes them through the topology as if fetched from input topics, captures output records and lets you query embedded state stores.

```java
// Processor API
Topology topology = new Topology();
topology.addSource("sourceProcessor", "input-topic");
topology.addProcessor("processor", ..., "sourceProcessor");
topology.addSink("sinkProcessor", "output-topic", "processor");
// or using DSL
StreamsBuilder builder = new StreamsBuilder();
builder.stream("input-topic").filter(...).to("output-topic");
Topology topology = builder.build();

// create test driver
TopologyTestDriver testDriver = new TopologyTestDriver(topology);
```

### Input and output

```java
TestInputTopic<String, Long> inputTopic =
    testDriver.createInputTopic("input-topic", stringSerde.serializer(), longSerde.serializer());
inputTopic.pipeInput("key", 42L);            // also: values only, KeyValue lists, explicit timestamps

TestOutputTopic<String, Long> outputTopic =
    testDriver.createOutputTopic("output-topic", stringSerde.deserializer(), longSerde.deserializer());
assertThat(outputTopic.readKeyValue(), equalTo(new KeyValue<>("key", 42L)));
```

`TestOutputTopic` has helpers to read just values, key-values, full records, or collections (lists/maps), and `isEmpty()`.

### Punctuations and time

- **Event-time (stream-time) punctuations** fire automatically based on the timestamps of piped records (`pipeInput(key, value, Instant)`).
- **Wall-clock punctuations** fire when you advance the driver's mocked clock:

```java
testDriver.advanceWallClockTime(Duration.ofSeconds(20));
```

### State stores

Access stores before a test to pre-populate them, and after to verify updates:

```java
KeyValueStore store = testDriver.getKeyValueStore("store-name");
```

Always close the driver to release resources:

```java
testDriver.close();
```

### Full example: max value per key

A processor keeps the max per key in a store and only emits on punctuation (every 60 s of wall-clock or 10 s of stream time):

```java
private TopologyTestDriver testDriver;
private TestInputTopic<String, Long> inputTopic;
private TestOutputTopic<String, Long> outputTopic;
private KeyValueStore<String, Long> store;

private Serde<String> stringSerde = new Serdes.StringSerde();
private Serde<Long> longSerde = new Serdes.LongSerde();

@Before
public void setup() {
    Topology topology = new Topology();
    topology.addSource("sourceProcessor", "input-topic");
    topology.addProcessor("aggregator", new CustomMaxAggregatorSupplier(), "sourceProcessor");
    topology.addStateStore(
        Stores.keyValueStoreBuilder(
            Stores.inMemoryKeyValueStore("aggStore"),
            Serdes.String(),
            Serdes.Long()).withLoggingDisabled(), // need to disable logging to allow store pre-populating
        "aggregator");
    topology.addSink("sinkProcessor", "result-topic", "aggregator");

    Properties props = new Properties();
    props.setProperty(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
    props.setProperty(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.Long().getClass().getName());
    testDriver = new TopologyTestDriver(topology, props);

    inputTopic = testDriver.createInputTopic("input-topic", stringSerde.serializer(), longSerde.serializer());
    outputTopic = testDriver.createOutputTopic("result-topic", stringSerde.deserializer(), longSerde.deserializer());

    // pre-populate store
    store = testDriver.getKeyValueStore("aggStore");
    store.put("a", 21L);
}

@After
public void tearDown() {
    testDriver.close();
}

@Test
public void shouldNotUpdateStoreForSmallerValue() {
    inputTopic.pipeInput("a", 1L);
    assertThat(store.get("a"), equalTo(21L));
    assertThat(outputTopic.readKeyValue(), equalTo(new KeyValue<>("a", 21L)));
    assertThat(outputTopic.isEmpty(), is(true));
}

@Test
public void shouldUpdateStoreForNewKey() {
    inputTopic.pipeInput("b", 21L);
    assertThat(store.get("b"), equalTo(21L));
    assertThat(outputTopic.readKeyValue(), equalTo(new KeyValue<>("a", 21L)));
    assertThat(outputTopic.readKeyValue(), equalTo(new KeyValue<>("b", 21L)));
    assertThat(outputTopic.isEmpty(), is(true));
}

@Test
public void shouldPunctuateIfEvenTimeAdvances() {
    final Instant recordTime = Instant.now();
    inputTopic.pipeInput("a", 1L, recordTime);
    assertThat(outputTopic.readKeyValue(), equalTo(new KeyValue<>("a", 21L)));

    inputTopic.pipeInput("a", 1L, recordTime);              // stream time unchanged -> no punctuation
    assertThat(outputTopic.isEmpty(), is(true));

    inputTopic.pipeInput("a", 1L, recordTime.plusSeconds(10L));  // +10 s stream time -> punctuation
    assertThat(outputTopic.readKeyValue(), equalTo(new KeyValue<>("a", 21L)));
    assertThat(outputTopic.isEmpty(), is(true));
}

@Test
public void shouldPunctuateIfWallClockTimeAdvances() {
    testDriver.advanceWallClockTime(Duration.ofSeconds(60));
    assertThat(outputTopic.readKeyValue(), equalTo(new KeyValue<>("a", 21L)));
    assertThat(outputTopic.isEmpty(), is(true));
}
```

The processor (`init` schedules `PunctuationType.WALL_CLOCK_TIME` every 60 s and `PunctuationType.STREAM_TIME` every 10 s, each calling `flushStore()` which forwards all store entries; `process` keeps the max). Note the store's **changelog is disabled** so it can be pre-populated.

## Unit testing processors with MockProcessorContext

A `Processor` forwards results to its context instead of returning them, so `MockProcessorContext` captures forwarded data for assertions ([Processor API](processor-api.md)).

```java
final Processor<String, String, String, Long> processorUnderTest = ...;
final MockProcessorContext<String, Long> context = new MockProcessorContext<>();
processorUnderTest.init(context);

// with configuration / default serdes
final Properties props = new Properties();
props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass());
props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.Long().getClass());
props.put("some.other.config", "some config value");
final MockProcessorContext<String, Long> configured = new MockProcessorContext<>(props);
```

**Captured forwards and commits:**

```java
processorUnderTest.process(new Record<>("key", "value", 0L));

final Iterator<CapturedForward<? extends String, ? extends Long>> forwarded = context.forwarded().iterator();
assertEquals(forwarded.next().record(), new Record<>(..., ...));
assertFalse(forwarded.hasNext());

context.resetForwards();                       // clear captures for longer scenarios
assertEquals(context.forwarded().size(), 0);

// forwards to a specific child
final List<CapturedForward<? extends String, ? extends Long>> captures = context.forwarded("childProcessorName");

assertTrue(context.committed());               // did the processor call commit()?
context.resetCommit();
```

**Record metadata:** set what the context reports (it keeps returning these until changed):

```java
context.setRecordMetadata("topicName", /*partition*/ 0, /*offset*/ 0L);
```

**State stores:** register simple **in-memory** stores — the mock doesn't manage changelogs or state directories:

```java
final KeyValueStore<String, Integer> store =
    Stores.keyValueStoreBuilder(
            Stores.inMemoryKeyValueStore("myStore"),
            Serdes.String(),
            Serdes.Integer()
        )
        .withLoggingDisabled() // Changelog is not supported by MockProcessorContext.
        .build();
store.init(context, store);
context.register(store, /*deprecated parameter*/ false, /*parameter unused in mock*/ null);
```

**Punctuators:** the mock captures but does **not** run scheduled punctuators; invoke them yourself:

```java
final MockProcessorContext.CapturedPunctuator capturedPunctuator = context.scheduledPunctuators().get(0);
final long interval = capturedPunctuator.getIntervalMs();
final PunctuationType type = capturedPunctuator.getType();
final boolean cancelled = capturedPunctuator.cancelled();
final Punctuator punctuator = capturedPunctuator.getPunctuator();
punctuator.punctuate(/*timestamp*/ 0L);
```

For automatic punctuation firing, wrap the processor in a small topology and use `TopologyTestDriver`.

## Tips

- Use explicit names for processors and stores in tests and production so assertions (and upgrades) don't depend on generated names ([naming](topology-naming-and-description.md)).
- `Topology#describe()` is useful to assert or print topology structure.
- For integration tests against a real cluster, run Kafka in [Docker](../getting-started/docker.md).

## Related pages

- [Writing a Streams application](writing-an-application.md)
- [Processor API](processor-api.md)
- [Streams DSL](dsl-api.md)
