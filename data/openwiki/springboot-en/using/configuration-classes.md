---
type: guide
title: "Configuration Classes"
description: "Spring Boot Configuration Classes: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","using"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-0ad002b1a0db2e5f51ddb090
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/using/configuration-classes.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Configuration Classes

Spring Boot favors Java-based configuration. Although it is possible to use `SpringApplication` with XML sources, we generally recommend that your primary source be a single `@Configuration` class. Usually the class that defines the `main` method is a good candidate as the primary `@Configuration`.

> **Tip:** Many Spring configuration examples have been published on the Internet that use XML configuration. If possible, always try to use the equivalent Java-based configuration. Searching for `Enable*` annotations can be a good starting point.

## Importing Additional Configuration Classes

You need not put all your `@Configuration` into a single class. The `@Import` annotation can be used to import additional configuration classes. Alternatively, you can use `@ComponentScan` to automatically pick up all Spring components, including `@Configuration` classes.

## Importing XML Configuration

If you absolutely must use XML based configuration, we recommend that you still start with a `@Configuration` class. You can then use an `@ImportResource` annotation to load XML configuration files.

## Related topics

- [Auto-configuration](auto-configuration.md)
- [Structuring Your Code](project-structure.md)
