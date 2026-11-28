---
type: guide
title: "Externalized Configuration"
description: "Spring Boot Externalized Configuration: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","configuration"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-deacd1ecca3e4f7f16fc0899
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/features/external-config.adoc
  - id: openwiki-source-2eb2b1d842ff17943198c737
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/features/externalconfig/MyBean.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Externalized Configuration

Spring Boot lets you externalize your configuration so that you can work with the same application code in different environments. You can use a variety of external configuration sources including Java properties files, YAML files, environment variables, and command-line arguments.

Property values can be injected directly into your beans by using the `@Value` annotation, accessed through Spring’s `Environment` abstraction, or be [bound to structured objects](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.typesafe-configuration-properties) through `@ConfigurationProperties`.

Spring Boot uses a very particular `PropertySource` order that is designed to allow sensible overriding of values. Later property sources can override the values defined in earlier ones.

Sources are considered in the following order:

1.  Default properties (specified by setting `SpringApplication.setDefaultProperties(Map)`).

2.  `@PropertySource` annotations on your `@Configuration` classes. Please note that such property sources are not added to the `Environment` until the application context is being refreshed. This is too late to configure certain properties such as `logging.*` and `spring.main.*` which are read before refresh begins.

3.  Config data (such as `application.properties` files).

4.  A `RandomValuePropertySource` that has properties only in `random.*`.

5.  OS environment variables.

6.  Java System properties (`System.getProperties()`).

7.  JNDI attributes from `java:comp/env`.

8.  `ServletContext` init parameters.

9.  `ServletConfig` init parameters.

10.  Properties from `SPRING_APPLICATION_JSON` (inline JSON embedded in an environment variable or system property).

11.  Command line arguments.

12.  `properties` attribute on your tests. Available on `@SpringBootTest` and the [test annotations for testing a particular slice of your application](https://docs.spring.io/spring-boot/4.2.0/reference/testing/spring-boot-applications.html#testing.spring-boot-applications.autoconfigured-tests).

13.  `@DynamicPropertySource` annotations in your tests.

14.  `@TestPropertySource` annotations on your tests.

15.  [Devtools global settings properties](https://docs.spring.io/spring-boot/4.2.0/reference/using/devtools.html#using.devtools.globalsettings) in the `$HOME/.config/spring-boot` directory when devtools is active.


Config data files are considered in the following order:

1.  [Application properties](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files) packaged inside your jar (`application.properties` and YAML variants).

2.  [Profile-specific application properties](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.profile-specific) packaged inside your jar (`application-{profile}.properties` and YAML variants).

3.  [Application properties](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files) outside of your packaged jar (`application.properties` and YAML variants).

4.  [Profile-specific application properties](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.profile-specific) outside of your packaged jar (`application-{profile}.properties` and YAML variants).


> **Note:** It is recommended to stick with one format for your entire application. If you have configuration files with both `.properties` and YAML format in the same location, `.properties` takes precedence.

> **Note:** If you use environment variables rather than system properties, most operating systems disallow period-separated key names, but you can use underscores instead (for example, `SPRING_CONFIG_NAME` instead of `spring.config.name`). See [features/external-config.adoc](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.typesafe-configuration-properties.relaxed-binding.environment-variables) for details.

> **Note:** If your application runs in a servlet container or application server, then JNDI properties (in `java:comp/env`) or servlet context initialization parameters can be used instead of, or as well as, environment variables or system properties.

To provide a concrete example, suppose you develop a `@Component` that uses a `name` property, as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.features.externalconfig;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class MyBean {

	@Value("${name}")
	private String name;

	// ...

}
```

On your application classpath (for example, inside your jar) you can have an `application.properties` file that provides a sensible default property value for `name`. When running in a new environment, an `application.properties` file can be provided outside of your jar that overrides the `name`. For one-off testing, you can launch with a specific command line switch (for example, `java -jar app.jar --name="Spring"`).

> **Tip:** The `env` and `configprops` endpoints can be useful in determining why a property has a particular value. You can use these two endpoints to diagnose unexpected property values. See the [Production ready features](https://docs.spring.io/spring-boot/4.2.0/reference/actuator/endpoints.html) section for details.

## Related topics

- [External Application Properties](config-files.md)
- [Packaging Your Application for Production](../using/production-packaging.md)
