---
type: guide
title: "Spring MVC Conversion Service"
description: "Spring Boot Spring MVC Conversion Service: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","web"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-d4b0796f5d6d502198d9c96b
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Spring MVC Conversion Service

Spring MVC uses a different `ConversionService` to the one used to convert values from your `application.properties` or `application.yaml` file. It means that `Period`, `Duration` and `DataSize` converters are not available and that `@DurationUnit` and `@DataSizeUnit` annotations will be ignored.

If you want to customize the `ConversionService` used by Spring MVC, you can provide a `WebMvcConfigurer` bean with an `addFormatters` method. From this method you can register any converter that you like, or you can delegate to the static methods available on `ApplicationConversionService`.

Conversion can also be customized using the `spring.mvc.format.*` configuration properties. When not configured, the following defaults are used:

| Property | `DateTimeFormatter` | Formats |
| --- | --- | --- |
| `spring.mvc.format.date` | `ofLocalizedDate(FormatStyle.SHORT)` | `java.util.Date` and `LocalDate` |
| `spring.mvc.format.time` | `ofLocalizedTime(FormatStyle.SHORT)` | java.time’s `LocalTime` and `OffsetTime` |
| `spring.mvc.format.date-time` | `ofLocalizedDateTime(FormatStyle.SHORT)` | java.time’s `LocalDateTime`, `OffsetDateTime`, and `ZonedDateTime` |

## Related topics

- [HttpMessageConverters](message-converters.md)
- [Spring MVC Auto-configuration](mvc-auto-configuration.md)
