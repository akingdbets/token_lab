---
type: guide
title: "Property Placeholders"
description: "Spring Boot Property Placeholders: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","configuration"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-deacd1ecca3e4f7f16fc0899
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/features/external-config.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Property Placeholders

The values in `application.properties` and `application.yaml` are filtered through the existing `Environment` when they are used, so you can refer back to previously defined values (for example, from System properties or environment variables). The standard `${name}` property-placeholder syntax can be used anywhere within a value. Property placeholders can also specify a default value using a `:` to separate the default value from the property name, for example `${name:default}`.

The use of placeholders with and without defaults is shown in the following example:

```yaml
app:
  name: "MyApp"
  description: "${app.name} is a Spring Boot application written by ${username:Unknown}"
```

Assuming that the `username` property has not been set elsewhere, `app.description` will have the value `MyApp is a Spring Boot application written by Unknown`.

> **Note:** You should always refer to property names in the placeholder using their canonical form (kebab-case using only lowercase letters). This will allow Spring Boot to use the same logic as it does when [relaxed binding](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.typesafe-configuration-properties.relaxed-binding) `@ConfigurationProperties`.
>
> For example, `${demo.item-price}` will pick up `demo.item-price` and `demo.itemPrice` forms from the `application.properties` file, as well as `DEMO_ITEMPRICE` from the system environment. If you use `${demo.itemPrice}` instead, it will pick up the `demo.itemPrice` form from the `application.properties` file, as well as `DEMO_ITEMPRICE` from the system environment, but `demo.item-price` would not be considered.

> **Tip:** You can also use this technique to create “short” variants of existing Spring Boot properties. See the [properties-and-configuration.adoc](https://docs.spring.io/spring-boot/4.2.0/how-to/properties-and-configuration.html#howto.properties-and-configuration.short-command-line-arguments) section in “How-to Guides” for details.

## Related topics

- [Working With YAML](yaml.md)
- [Using Configuration Trees](imports-and-configtrees.md)
