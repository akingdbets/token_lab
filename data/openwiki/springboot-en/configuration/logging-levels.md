---
type: guide
title: "Log Levels"
description: "Spring Boot Log Levels: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","configuration"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-46d6427b7638cc5a7d54f14b
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/features/logging.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Log Levels

All the supported logging systems can have the logger levels set in the Spring `Environment` (for example, in `application.properties`) by using `logging.level.<logger-name>=<level>` where `level` is one of TRACE, DEBUG, INFO, WARN, ERROR, FATAL, or OFF. The `root` logger can be configured by using `logging.level.root`.

The following example shows potential logging settings in `application.properties`:

```yaml
logging:
  level:
    root: "warn"
    org.springframework.web: "debug"
    org.hibernate: "error"
```

It is also possible to set logging levels using environment variables. For example, `LOGGING_LEVEL_ORG_SPRINGFRAMEWORK_WEB=DEBUG` will set `org.springframework.web` to `DEBUG`.

> **Note:** The above approach will only work for package level logging. Since relaxed binding [always converts environment variables to lowercase](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.typesafe-configuration-properties.relaxed-binding.maps-from-environment-variables), it is not possible to configure logging for an individual class in this way. If you need to configure logging for a class, you can use [the `SPRING_APPLICATION_JSON`](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.application-json) variable.

## Related topics

- [The Spring Web MVC Framework](../web/controllers-and-routing.md)
- [JSON](json.md)
