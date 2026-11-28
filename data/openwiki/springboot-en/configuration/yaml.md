---
type: guide
title: "Working With YAML"
description: "Spring Boot Working With YAML: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","configuration"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-deacd1ecca3e4f7f16fc0899
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/features/external-config.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Working With YAML

[YAML](https://yaml.org) is a superset of JSON and, as such, is a convenient format for specifying hierarchical configuration data. The `SpringApplication` class automatically supports YAML as an alternative to properties whenever you have the [SnakeYAML](https://github.com/snakeyaml/snakeyaml) library on your classpath.

> **Note:** If you use starters, SnakeYAML is automatically provided by `spring-boot-starter`.

## Mapping YAML to Properties

YAML documents need to be converted from their hierarchical format to a flat structure that can be used with the Spring `Environment`. For example, consider the following YAML document:

```yaml
environments:
  dev:
    url: "https://dev.example.com"
    name: "Developer Setup"
  prod:
    url: "https://another.example.com"
    name: "My Cool App"
```

In order to access these properties from the `Environment`, they would be flattened as follows:

```properties
environments.dev.url=https://dev.example.com
environments.dev.name=Developer Setup
environments.prod.url=https://another.example.com
environments.prod.name=My Cool App
```

Likewise, YAML lists also need to be flattened. They are represented as property keys with `[index]` dereferencers. For example, consider the following YAML:

```yaml
 my:
  servers:
  - "dev.example.com"
  - "another.example.com"
```

The preceding example would be transformed into these properties:

```properties
my.servers[0]=dev.example.com
my.servers[1]=another.example.com
```

> **Tip:** Properties that use the `[index]` notation can be bound to Java `List` or `Set` objects using Spring Boot’s `Binder` class. For more details see the [features/external-config.adoc](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.typesafe-configuration-properties) section below.

> **Warning:** YAML files cannot be loaded by using the `@PropertySource` or `@TestPropertySource` annotations. So, in the case that you need to load values that way, you need to use a properties file.

## Directly Loading YAML

Spring Framework provides two convenient classes that can be used to load YAML documents. The `YamlPropertiesFactoryBean` loads YAML as `Properties` and the `YamlMapFactoryBean` loads YAML as a `Map`.

You can also use the `YamlPropertySourceLoader` class if you want to load YAML as a Spring `PropertySource`.

## Related topics

- [JavaBean Properties Binding](java-bean-binding.md)
- [Property Placeholders](placeholders.md)
