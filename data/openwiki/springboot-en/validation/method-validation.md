---
type: guide
title: "Validation"
description: "Spring Boot Validation: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","validation"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-2e9a3481e604700d24ca0809
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/io/validation.adoc
  - id: openwiki-source-feb1e58a61e13e935ea3dd47
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/io/validation/MyBean.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Validation

The method validation feature supported by Bean Validation 1.1 is automatically enabled as long as a JSR-303 implementation (such as Hibernate Validator, typically provided by `spring-boot-starter-validation`) is on the classpath. This lets bean methods be annotated with `jakarta.validation` constraints on their parameters and/or on their return value. Target classes with such annotated methods need to be annotated with the `@Validated` annotation at the type level for their methods to be searched for inline constraint annotations.

For instance, the following service triggers the validation of the first argument, making sure its size is between 8 and 10:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.io.validation;

import jakarta.validation.constraints.Size;

import org.springframework.stereotype.Service;
import org.springframework.validation.annotation.Validated;

@Service
@Validated
public class MyBean {

	public Archive findByCodeAndAuthor(@Size(min = 8, max = 10) String code, Author author) {
		return /**/ null;
	}

}
```

The application’s `MessageSource` is used when resolving `{parameters}` in constraint messages. This allows you to use [your application’s `messages.properties` files](https://docs.spring.io/spring-boot/4.2.0/reference/features/internationalization.html) for Bean Validation messages. Once the parameters have been resolved, message interpolation is completed using Bean Validation’s default interpolator.

To customize the `Configuration` used to build the `ValidatorFactory`, define a `ValidationConfigurationCustomizer` bean. When multiple customizer beans are defined, they are called in order based on their `@Order` annotation or `Ordered` implementation.

## Related topics

- [Configure a DataSource](../data/datasources.md)
- [Spring Security](../security/web-security.md)
