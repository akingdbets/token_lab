---
type: guide
title: "Using JdbcTemplate"
description: "Spring Boot Using JdbcTemplate: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","data"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-6fe6686d5e12e76fb6684799
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc
  - id: openwiki-source-29883ca029d44507b3ede24e
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/data/sql/jdbctemplate/MyBean.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Using JdbcTemplate

Spring’s `JdbcTemplate` and `NamedParameterJdbcTemplate` classes are auto-configured, and you can autowire them directly into your own beans, as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.data.sql.jdbctemplate;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class MyBean {

	private final JdbcTemplate jdbcTemplate;

	public MyBean(JdbcTemplate jdbcTemplate) {
		this.jdbcTemplate = jdbcTemplate;
	}

	public void doSomething() {
		/* @chomp:line this.jdbcTemplate ... */ this.jdbcTemplate.execute("delete from customer");
	}

}
```

You can customize some properties of the template by using the `spring.jdbc.template.*` properties, as shown in the following example:

```yaml
spring:
  jdbc:
    template:
      max-rows: 500
```

If tuning of SQL exceptions is required, you can define your own `SQLExceptionTranslator` bean so that it is associated with the auto-configured `JdbcTemplate`.

> **Note:** The `NamedParameterJdbcTemplate` reuses the same `JdbcTemplate` instance behind the scenes. If more than one `JdbcTemplate` is defined and no primary candidate exists, the `NamedParameterJdbcTemplate` is not auto-configured.

## Related topics

- [JPA and Spring Data JPA](jpa-and-repositories.md)
- [Configure a DataSource](datasources.md)
