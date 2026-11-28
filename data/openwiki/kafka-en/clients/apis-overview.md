---
type: api-guide
title: Kafka APIs Overview
description: The six core Kafka APIs (Producer, Consumer, Share Consumer, Streams, Connect, Admin), their Maven artifacts and entry classes, and the KIP-1265 Internal API Checker that flags use of non-public Kafka classes.
tags: [apis, clients, maven, build, internal-api-checker]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T05:22:57.903Z
sources:
  - id: openwiki-source-f45042d05f4d591a882525b6
    resource: repo://docs/apis/_index.md
  - id: openwiki-source-df5d3a649c8c322bd6d99abd
    resource: repo://docs/apis/internal-api-checker.md
generated: { by: "claude-code", at: "2026-11-28T05:22:57.903Z" }
---

# Kafka APIs Overview

Kafka includes six core APIs:

| API | Purpose | Entry point | Maven artifact |
| --- | --- | --- | --- |
| Producer API | Send streams of data to topics | `org.apache.kafka.clients.producer.KafkaProducer` | `org.apache.kafka:kafka-clients` |
| Consumer API | Read streams of data from topics | `org.apache.kafka.clients.consumer.KafkaConsumer` | `org.apache.kafka:kafka-clients` |
| Share Consumer API | Applications in a *share group* cooperatively consume and process data from topics | `org.apache.kafka.clients.consumer.KafkaShareConsumer` | `org.apache.kafka:kafka-clients` |
| Streams API | Transform streams of data from input topics to output topics | `org.apache.kafka.streams.KafkaStreams` | `org.apache.kafka:kafka-streams` (optional Scala DSL: `kafka-streams-scala_2.13`) |
| Connect API | Implement connectors that pull from a source system into Kafka or push from Kafka into a sink system | `org.apache.kafka.connect` packages | `connect-api` (most users run pre-built connectors instead) |
| Admin API | Manage and inspect topics, brokers, ACLs and other objects | `org.apache.kafka.clients.admin.Admin` | `org.apache.kafka:kafka-clients` |

Kafka exposes all its functionality over a language-independent [binary protocol](../reference/protocol-and-internals.md). Only the Java clients are maintained in the main Kafka project; clients for other languages are independent open-source projects.

## Maven dependencies

Producer, Consumer, Share Consumer and Admin all come from one artifact:

```xml
<dependency>
	<groupId>org.apache.kafka</groupId>
	<artifactId>kafka-clients</artifactId>
	<version>4.3.1</version>
</dependency>
```

Kafka Streams:

```xml
<dependency>
	<groupId>org.apache.kafka</groupId>
	<artifactId>kafka-streams</artifactId>
	<version>4.3.1</version>
</dependency>
```

Kafka Streams DSL for Scala 2.13:

```xml
<dependency>
	<groupId>org.apache.kafka</groupId>
	<artifactId>kafka-streams-scala_2.13</artifactId>
	<version>4.3.1</version>
</dependency>
```

> **Deprecation:** `kafka-streams-scala` is deprecated as of Kafka 4.3 and will be removed in Kafka 5.0. Migrate to the Java Streams API used directly from Scala — see [Streams data types and Serdes](../streams/serdes-and-datatypes.md) for the migration guide.

(The `4.3.1` versions are the ones printed in the documentation snippets; use the version that matches your deployment.)

Where to go next for each API:

- [Producer](producer.md), [Consumer](consumer.md), [Consumer groups and rebalance protocols](consumer-groups-and-rebalance.md)
- [Share groups and the share consumer](share-groups.md)
- [Admin API](admin-api.md)
- [Kafka Streams introduction](../streams/introduction-and-quickstart.md)
- [Kafka Connect](../connect/overview-and-running.md) and [connector development](../connect/connector-development.md)

## Internal API Checker (KIP-1265)

Kafka marks its supported public surface with `@InterfaceAudience.Public`. [KIP-1265](https://cwiki.apache.org/confluence/display/KAFKA/KIP-1265%3A+Mechanism+for+automatic+detection+of+internal+API+usage) ships a **build-time bytecode checker** that flags references from your compiled classes to Kafka classes that are *not* public. Use it in connectors, Streams applications or any project depending on `org.apache.kafka:*` to catch internal-API usage that would silently break on upgrade. Because it scans bytecode, it works for Java, Scala, Kotlin and other JVM languages and catches fully-qualified references, wildcard imports and generated code that a grep on `import` lines would miss.

### Gradle

```groovy
plugins {
    id 'org.apache.kafka.internal-api-checker' version '<kafka version>'
}
```

- Registers the task `kafkaInternalApiChecker` in the `verification` group and hooks it onto `check`, so `./gradlew check` fails on any unsuppressed internal reference.
- Defaults: scans `sourceSets.main.output.classesDirs`; builds the public surface from the `org.apache.kafka:*` artifacts on `compileClasspath` and `testCompileClasspath`. A Kafka version bump invalidates the task.

Overrides (only when defaults don't fit):

```groovy
kafkaInternalApiChecker {
    enabled         = true                  // default
    failOnViolation = true                  // default
    classDirs.from(files('extra-classes'))  // extend the bytecode roots
    // kafkaDependencyJars.setFrom(configurations.myKafkaBundle)
}
```

Skip for a single invocation:

```bash
./gradlew check -PkafkaInternalApiChecker.skip
```

### Maven

```xml
<plugin>
  <groupId>org.apache.kafka</groupId>
  <artifactId>kafka-internal-api-checker-maven-plugin</artifactId>
  <version><!-- kafka version --></version>
  <executions>
    <execution>
      <phase>verify</phase>
      <goals><goal>verify</goal></goals>
    </execution>
  </executions>
</plugin>
```

The mojo binds to `verify` and reads `${project.build.outputDirectory}` by default.

### Reports and suppressions

Each run writes `build/reports/kafka-internal-api-usage.txt` (`target/` for Maven), grouping violations by type and class and listing suppressions separately for audit.

Intentional internal references can be suppressed with `@SuppressKafkaInternalApiUsage` (from `kafka-clients`, package `org.apache.kafka.common.annotation`) on a class, method or field, with a reason:

```java
import org.apache.kafka.common.annotation.SuppressKafkaInternalApiUsage;

public class MyConnector implements SinkConnector {

    @SuppressKafkaInternalApiUsage("KIP-XYZ: replace with public API once finalised")
    private final InternalKafkaHelper helper = new InternalKafkaHelper();
}
```

### Version requirement and rules

- The checker reads audience annotations from the **Kafka libraries on your compile classpath**, not from the plugin's own version. If you depend on a Kafka release that predates KIP-1265, it sees zero public APIs and flags *every* `org.apache.kafka.*` reference (even `KafkaProducer` or `Topology`). Upgrade `kafka-clients`, `kafka-streams`, `connect-api`, `kafka-tools-api`, … to at least the checker's release before enabling `failOnViolation = true`, or set `failOnViolation = false` to report only while migrating.
- A class is public if it carries `@InterfaceAudience.Public`, or is nested in a class whose nearest annotated enclosing class is public. Classes outside `org.apache.kafka.*` are out of scope.
- A `@Deprecated` *internal* class is still flagged on the consumer (your) side.
- Known blind spots: parameter annotations, type-use annotations, class literals that appear only inside annotation values, and inlined compile-time constants (`public static final` primitives/Strings) — a "0 violations" report does not strictly exclude these.

## Related pages

- [Admin API](admin-api.md)
- [Producer](producer.md)
- [Consumer](consumer.md)
- [Share groups](share-groups.md)
