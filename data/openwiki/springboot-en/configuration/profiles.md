---
type: guide
title: "Profiles"
description: "Spring Boot Profiles: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","configuration"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-ad46491b3ea9d1db87e90583
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/features/profiles.adoc
  - id: openwiki-source-3f27a88b3e03962fe93c0e89
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/features/profiles/ProductionConfiguration.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Profiles

Spring Profiles provide a way to segregate parts of your application configuration and make it be available only in certain environments. Any `@Component`, `@Configuration` or `@ConfigurationProperties` can be marked with `@Profile` to limit when it is loaded, as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.features.profiles;

import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;

@Configuration(proxyBeanMethods = false)
@Profile("production")
public class ProductionConfiguration {

	// ...

}
```

> **Note:** If `@ConfigurationProperties` beans are registered through `@EnableConfigurationProperties` instead of automatic scanning, the `@Profile` annotation needs to be specified on the `@Configuration` class that has the `@EnableConfigurationProperties` annotation. In the case where `@ConfigurationProperties` are scanned, `@Profile` can be specified on the `@ConfigurationProperties` class itself.

You can use a `spring.profiles.active` `Environment` property to specify which profiles are active. You can specify the property in any of the ways described earlier in this chapter. For example, you could include it in your `application.properties`, as shown in the following example:

```yaml
spring:
  profiles:
    active: "dev,hsqldb"
```

You could also specify it on the command line by using the following switch: `--spring.profiles.active=dev,hsqldb`.

If no profile is active, a default profile is enabled. The name of the default profile is `default` and it can be tuned using the `spring.profiles.default` `Environment` property, as shown in the following example:

```yaml
spring:
  profiles:
    default: "none"
```

`spring.profiles.active` and `spring.profiles.default` can only be used in non-profile-specific documents. This means they cannot be included in [profile specific files](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.profile-specific) or [documents activated](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.activation-properties) by `spring.config.activate.on-profile`.

For example, the second document configuration is invalid:

```yaml
# this document is valid
spring:
  profiles:
    active: "prod"
---
# this document is invalid
spring:
  config:
    activate:
      on-profile: "prod"
  profiles:
    active: "metrics"
```

The `spring.profiles.active` property follows the same ordering rules as other properties. The highest `PropertySource` wins. This means that you can specify active profiles in `application.properties` and then **replace** them by using the command line switch.

> **Tip:** See [the “Externalized Configuration”](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.order) for more details on the order in which property sources are considered.

> **Note:** By default, profile names in Spring Boot may contain letters, numbers, or permitted characters (`-`, `_`, `.`, `+`, `@`). In addition, they can only start and end with a letter or number.
>
> This restriction helps to prevent common parsing issues. if, however, you prefer more flexible profile names you can set `spring.profiles.validate` to `false` in your `application.properties` or `application.yaml` file:
>
> ```yaml
> spring:
>   profiles:
>     validate: false
> ```

## Adding Active Profiles

Sometimes, it is useful to have properties that **add** to the active profiles rather than replace them. The `spring.profiles.include` property can be used to add active profiles on top of those activated by the `spring.profiles.active` property. The `SpringApplication` entry point also has a Java API for setting additional profiles. See the `setAdditionalProfiles()` method in `SpringApplication`.

For example, when an application with the following properties is run, the common and local profiles will be activated even when it runs using the `--spring.profiles.active` switch:

```yaml
spring:
  profiles:
    include:
      - "common"
      - "local"
```

> **Note:** Included profiles are added before any `spring.profiles.active` profiles.

> **Tip:** The `spring.profiles.include` property is processed for each property source, as such the usual [complex type merging rules](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.typesafe-configuration-properties.merging-complex-types) for lists do not apply.

> **Warning:** Similar to `spring.profiles.active`, `spring.profiles.include` can only be used in non-profile-specific documents. This means it cannot be included in [profile specific files](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.profile-specific) or [documents activated](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.activation-properties) by `spring.config.activate.on-profile`.

Profile groups, which are described in the [next section](https://docs.spring.io/spring-boot/4.2.0/reference/features/profiles.html#features.profiles.groups) can also be used to add active profiles if a given profile is active.

## Profile Groups

Occasionally the profiles that you define and use in your application are too fine-grained and become cumbersome to use. For example, you might have `proddb` and `prodmq` profiles that you use to enable database and messaging features independently.

To help with this, Spring Boot lets you define profile groups. A profile group allows you to define a logical name for a related group of profiles.

For example, we can create a `production` group that consists of our `proddb` and `prodmq` profiles.

```yaml
spring:
  profiles:
    group:
      production:
      - "proddb"
      - "prodmq"
```

Our application can now be started using `--spring.profiles.active=production` to activate the `production`, `proddb` and `prodmq` profiles in one hit.

> **Warning:** Similar to `spring.profiles.active` and `spring.profiles.include`, `spring.profiles.group` can only be used in non-profile-specific documents. This means it cannot be included in [profile specific files](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.profile-specific) or [documents activated](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.activation-properties) by `spring.config.activate.on-profile`.

## Programmatically Setting Profiles

You can programmatically set active profiles by calling `SpringApplication.setAdditionalProfiles(…​)` before your application runs. It is also possible to activate profiles by using Spring’s `ConfigurableEnvironment` interface.

## Profile-specific Configuration Files

Profile-specific variants of both `application.properties` (or `application.yaml`) and files referenced through `@ConfigurationProperties` are considered as files and loaded. See [features/external-config.adoc](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.profile-specific) for details.

## Related topics

- [JSON](json.md)
- [@ConfigurationProperties Validation](properties-validation.md)
