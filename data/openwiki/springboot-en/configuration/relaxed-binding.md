---
type: guide
title: "Relaxed Binding"
description: "Spring Boot Relaxed Binding: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","configuration"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-deacd1ecca3e4f7f16fc0899
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/features/external-config.adoc
  - id: openwiki-source-8499816c730be58de1f8e7f9
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/features/externalconfig/typesafeconfigurationproperties/relaxedbinding/mapsfromenvironmentvariables/MyMapsProperties.java
  - id: openwiki-source-7d3d42583cfcb1d01a8d346d
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/features/externalconfig/typesafeconfigurationproperties/relaxedbinding/MyPersonProperties.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Relaxed Binding

Spring Boot uses some relaxed rules for binding `Environment` properties to `@ConfigurationProperties` beans, so there does not need to be an exact match between the `Environment` property name and the bean property name. Common examples where this is useful include dash-separated environment properties (for example, `context-path` binds to `contextPath`), and capitalized environment properties (for example, `PORT` binds to `port`).

As an example, consider the following `@ConfigurationProperties` class:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.features.externalconfig.typesafeconfigurationproperties.relaxedbinding;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("my.main-project.person")
public class MyPersonProperties {

	private String firstName;

	public String getFirstName() {
		return this.firstName;
	}

	public void setFirstName(String firstName) {
		this.firstName = firstName;
	}

}
```

With the preceding code, the following properties names can all be used:

| Property | Note |
| --- | --- |
| `my.main-project.person.first-name` | Kebab case, which is recommended for use in `.properties` and YAML files. |
| `my.main-project.person.firstName` | Standard camel case syntax. |
| `my.main-project.person.first_name` | Underscore notation, which is an alternative format for use in `.properties` and YAML files. |
| `MY_MAINPROJECT_PERSON_FIRSTNAME` | Upper case format, which is recommended when using system environment variables. |

> **Note:** The `prefix` value for the annotation _must_ be in kebab case (lowercase and separated by `-`, such as `my.main-project.person`).

| Property Source | Simple | List |
| --- | --- | --- |
| Properties Files | Camel case, kebab case, or underscore notation | Standard list syntax using `[ ]` or comma-separated values |
| YAML Files | Camel case, kebab case, or underscore notation | Standard YAML list syntax or comma-separated values |
| Environment Variables | Upper case format with underscore as the delimiter (see [features/external-config.adoc](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.typesafe-configuration-properties.relaxed-binding.environment-variables)). | Numeric values surrounded by underscores (see [features/external-config.adoc](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.typesafe-configuration-properties.relaxed-binding.environment-variables)) |
| System properties | Camel case, kebab case, or underscore notation | Standard list syntax using `[ ]` or comma-separated values |

> **Tip:** We recommend that, when possible, properties are stored in lower-case kebab format, such as `my.person.first-name=Rod`.

## Binding Maps

When binding to `Map` properties you may need to use a special bracket notation so that the original `key` value is preserved. If the key is not surrounded by `[]`, any characters that are not alpha-numeric, `-` or `.` are removed.

For example, consider binding the following properties to a `Map<String,String>`:

```yaml
my:
  map:
    "[/key1]": "value1"
    "[/key2]": "value2"
    "/key3": "value3"
```

> **Note:** For YAML files, the brackets need to be surrounded by quotes for the keys to be parsed properly.

The properties above will bind to a `Map` with `/key1`, `/key2` and `key3` as the keys in the map. The slash has been removed from `key3` because it was not surrounded by square brackets.

When binding to scalar values, keys with `.` in them do not need to be surrounded by `[]`. Scalar values include enums and all types in the `java.lang` package except for `Object`. Binding `a.b=c` to `Map<String, String>` will preserve the `.` in the key and return a Map with the entry `{"a.b"="c"}`. For any other types you need to use the bracket notation if your `key` contains a `.`. For example, binding `a.b=c` to `Map<String, Object>` will return a Map with the entry `{"a"={"b"="c"}}` whereas `[a.b]=c` will return a Map with the entry `{"a.b"="c"}`.

## Binding From Environment Variables

Most operating systems impose strict rules around the names that can be used for environment variables. For example, Linux shell variables can contain only letters (`a` to `z` or `A` to `Z`), numbers (`0` to `9`) or the underscore character (`_`). By convention, Unix shell variables will also have their names in UPPERCASE.

Spring Boot’s relaxed binding rules are, as much as possible, designed to be compatible with these naming restrictions.

To convert a property name in the canonical-form to an environment variable name you can follow these rules:

-   Replace dots (`.`) with underscores (`_`).

-   Remove any dashes (`-`).

-   Convert to uppercase.


For example, the configuration property `spring.main.log-startup-info` would be an environment variable named `SPRING_MAIN_LOGSTARTUPINFO`.

Environment variables can also be used when binding to object lists. To bind to a `List`, the element number should be surrounded with underscores in the variable name.

For example, the configuration property `my.service[0].other` would use an environment variable named `MY_SERVICE_0_OTHER`.

Support for binding from environment variables is applied to the `systemEnvironment` property source and to any additional property source whose name ends with `-systemEnvironment`.

## Binding Maps From Environment Variables

When Spring Boot binds an environment variable to a property class, it lowercases the environment variable name before binding. Most of the time this detail isn’t important, except when binding to `Map` properties.

The keys in the `Map` are always in lowercase, as seen in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.features.externalconfig.typesafeconfigurationproperties.relaxedbinding.mapsfromenvironmentvariables;

import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("my.props")
public class MyMapsProperties {

	private final Map<String, String> values = new LinkedHashMap<>();

	public Map<String, String> getValues() {
		return this.values;
	}

}
```

When setting `MY_PROPS_VALUES_KEY=value`, the `values` `Map` contains a `{"key"="value"}` entry.

Only the environment variable **name** is lower-cased, not the value. When setting `MY_PROPS_VALUES_KEY=VALUE`, the `values` `Map` contains a `{"key"="VALUE"}` entry.

## Caching

Relaxed binding uses a cache to improve performance. By default, this caching is only applied to immutable property sources. To customize this behavior, for example to enable caching for mutable property sources, use `ConfigurationPropertyCaching`.

## Related topics

- [@ConfigurationProperties Validation](properties-validation.md)
- [Enabling @ConfigurationProperties-annotated Types](enabling-properties.md)
