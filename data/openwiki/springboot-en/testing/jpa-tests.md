---
type: guide
title: "Auto-configured Data JPA Tests"
description: "Spring Boot Auto-configured Data JPA Tests: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","testing"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-a98875ac417452e7afd8faa9
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc
  - id: openwiki-source-a2e40a73ce34caa3c17197a0
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/autoconfiguredspringdatajpa/MyNonTransactionalTests.java
  - id: openwiki-source-fc03f5eb8ad3f8096c75dfba
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/autoconfiguredspringdatajpa/withdb/MyRepositoryTests.java
  - id: openwiki-source-0f6c35af204a08ddd5cdeeee
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/autoconfiguredspringdatajpa/withoutdb/MyRepositoryTests.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Auto-configured Data JPA Tests

You can use the `@DataJpaTest` annotation from the `spring-boot-data-jpa-test` module to test Data JPA applications. By default, it scans for `@Entity` classes and configures Spring Data JPA repositories. If an embedded database is available on the classpath, it configures one as well. SQL queries are logged by default by setting the `spring.jpa.show-sql` property to `true`. This can be disabled using the `showSql` attribute of the annotation.

Regular `@Component` and `@ConfigurationProperties` beans are not scanned when the `@DataJpaTest` annotation is used. `@EnableConfigurationProperties` can be used to include `@ConfigurationProperties` beans.

> **Tip:** A list of the auto-configuration settings that are enabled by `@DataJpaTest` can be [found in the appendix](https://docs.spring.io/spring-boot/4.2.0/appendix/test-auto-configuration/index.html).

By default, data JPA tests are transactional and roll back at the end of each test. See the [relevant section](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc#L536) in the Spring Framework Reference Documentation for more details. If that is not what you want, you can disable transaction management for a test or for the whole class as follows:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.autoconfiguredspringdatajpa;

import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@DataJpaTest
@Transactional(propagation = Propagation.NOT_SUPPORTED)
class MyNonTransactionalTests {

	// ...

}
```

Data JPA tests may also inject a `TestEntityManager` bean, which provides an alternative to the standard JPA `EntityManager` that is specifically designed for tests.

> **Tip:** `TestEntityManager` can also be auto-configured to any of your Spring-based test class by adding `@AutoConfigureTestEntityManager`. When doing so, make sure that your test is running in a transaction, for instance by adding `@Transactional` on your test class or method.

A `JdbcTemplate` is also available if you need that. The following example shows the `@DataJpaTest` annotation in use:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.autoconfiguredspringdatajpa.withoutdb;

import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jpa.test.autoconfigure.TestEntityManager;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
class MyRepositoryTests {

	@Autowired
	private TestEntityManager entityManager;

	@Autowired
	private UserRepository repository;

	@Test
	void testExample() {
		this.entityManager.persist(new User("sboot", "1234"));
		User user = this.repository.findByUsername("sboot");
		assertThat(user.getUsername()).isEqualTo("sboot");
		assertThat(user.getEmployeeNumber()).isEqualTo("1234");
	}

}
```

In-memory embedded databases generally work well for tests, since they are fast and do not require any installation. If, however, you prefer to run tests against a real database you can use the `@AutoConfigureTestDatabase` annotation, as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.autoconfiguredspringdatajpa.withdb;

import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase.Replace;

@DataJpaTest
@AutoConfigureTestDatabase(replace = Replace.NONE)
class MyRepositoryTests {

	// ...

}
```

## Related topics

- [Testcontainers](testcontainers.md)
- [Auto-configured Spring MVC Tests](mvc-tests.md)
