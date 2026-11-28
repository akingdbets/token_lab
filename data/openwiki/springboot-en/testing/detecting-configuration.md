---
type: guide
title: "Detecting Test Configuration"
description: "Spring Boot Detecting Test Configuration: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","testing"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-a98875ac417452e7afd8faa9
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Detecting Test Configuration

If you are familiar with the Spring Test Framework, you may be used to using `@ContextConfiguration(classes=…​)` in order to specify which Spring `@Configuration` to load. Alternatively, you might have often used nested `@Configuration` classes within your test.

When testing Spring Boot applications, this is often not required. Spring Boot’s `@*Test` annotations search for your primary configuration automatically whenever you do not explicitly define one.

The search algorithm works up from the package that contains the test until it finds a class annotated with `@SpringBootApplication` or `@SpringBootConfiguration`. As long as you [structured your code](https://docs.spring.io/spring-boot/4.2.0/reference/using/structuring-your-code.html) in a sensible way, your main configuration is usually found.

> **Note:** If you use a [test annotation to test a more specific slice of your application](https://docs.spring.io/spring-boot/4.2.0/reference/testing/spring-boot-applications.html#testing.spring-boot-applications.autoconfigured-tests), you should avoid adding configuration settings that are specific to a particular area on the [main method’s application class](https://docs.spring.io/spring-boot/4.2.0/reference/testing/spring-boot-applications.html#testing.spring-boot-applications.user-configuration-and-slicing).
>
> The underlying component scan configuration of `@SpringBootApplication` defines exclude filters that are used to make sure slicing works as expected. If you are using an explicit `@ComponentScan` directive on your `@SpringBootApplication`\-annotated class, be aware that those filters will be disabled. If you are using slicing, you should define them again.

If you want to customize the primary configuration, you can use a nested `@TestConfiguration` class. Unlike a nested `@Configuration` class, which would be used instead of your application’s primary configuration, a nested `@TestConfiguration` class is used in addition to your application’s primary configuration.

> **Note:** Spring’s test framework caches application contexts between tests. Therefore, as long as your tests share the same configuration (no matter how it is discovered), the potentially time-consuming process of loading the context happens only once.

## Related topics

- [Testing With a Mock Environment](mock-environment.md)
- [Testing Spring Boot Applications](test-foundations.md)
