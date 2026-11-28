---
type: guide
title: "Using R2DBC"
description: "Spring Boot Using R2DBC: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","data"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-6fe6686d5e12e76fb6684799
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc
  - id: openwiki-source-0fa8cc19031f1a4421cb2e2f
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/data/sql/r2dbc/MyPostgresR2dbcConfiguration.java
  - id: openwiki-source-ed0af53a96376e04ab5a087a
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/data/sql/r2dbc/MyR2dbcConfiguration.java
  - id: openwiki-source-2e5d2a95e54db273e8eb4053
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/data/sql/r2dbc/repositories/CityRepository.java
  - id: openwiki-source-7ca2db85f3947bfab6213c24
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/data/sql/r2dbc/usingdatabaseclient/MyBean.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Using R2DBC

The Reactive Relational Database Connectivity ([R2DBC](https://r2dbc.io)) project brings reactive programming APIs to relational databases. R2DBC’s `Connection` provides a standard method of working with non-blocking database connections. Connections are provided by using a `ConnectionFactory`, similar to a `DataSource` with jdbc.

`ConnectionFactory` configuration is controlled by external configuration properties in `spring.r2dbc.*`. For example, you might declare the following section in `application.properties`:

```yaml
spring:
  r2dbc:
    url: "r2dbc:postgresql://localhost/test"
    username: "dbuser"
    password: "dbpass"
```

> **Tip:** You do not need to specify a driver class name, since Spring Boot obtains the driver from R2DBC’s Connection Factory discovery.

> **Note:** At least the url should be provided. Information specified in the URL takes precedence over individual properties, that is `name`, `username`, `password` and pooling options.

> **Tip:** The “How-to Guides” section includes a [section on how to initialize a database](https://docs.spring.io/spring-boot/4.2.0/how-to/data-initialization.html#howto.data-initialization.using-basic-sql-scripts).

To customize the connections created by a `ConnectionFactory`, that is, set specific parameters that you do not want (or cannot) configure in your central database configuration, you can use a `ConnectionFactoryOptionsBuilderCustomizer` `@Bean`. The following example shows how to manually override the database port while the rest of the options are taken from the application configuration:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.data.sql.r2dbc;

import io.r2dbc.spi.ConnectionFactoryOptions;

import org.springframework.boot.r2dbc.autoconfigure.ConnectionFactoryOptionsBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class MyR2dbcConfiguration {

	@Bean
	public ConnectionFactoryOptionsBuilderCustomizer connectionFactoryPortCustomizer() {
		return (builder) -> builder.option(ConnectionFactoryOptions.PORT, 5432);
	}

}
```

The following examples show how to set some PostgreSQL connection options:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.data.sql.r2dbc;

import java.util.HashMap;
import java.util.Map;

import io.r2dbc.postgresql.PostgresqlConnectionFactoryProvider;

import org.springframework.boot.r2dbc.autoconfigure.ConnectionFactoryOptionsBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class MyPostgresR2dbcConfiguration {

	@Bean
	public ConnectionFactoryOptionsBuilderCustomizer postgresCustomizer() {
		Map<String, String> options = new HashMap<>();
		options.put("lock_timeout", "30s");
		options.put("statement_timeout", "60s");
		return (builder) -> builder.option(PostgresqlConnectionFactoryProvider.OPTIONS, options);
	}

}
```

When a `ConnectionFactory` bean is available, the regular JDBC `DataSource` auto-configuration backs off. If you want to retain the JDBC `DataSource` auto-configuration, and are comfortable with the risk of using the blocking JDBC API in a reactive application, add `@Import(DataSourceAutoConfiguration.class)` on a `@Configuration` class in your application to re-enable it.

## Embedded Database Support

Similarly to [the JDBC support](https://docs.spring.io/spring-boot/4.2.0/reference/data/sql.html#data.sql.datasource.embedded), Spring Boot can automatically configure an embedded database for reactive usage. You need not provide any connection URLs. You need only include a build dependency to the embedded database that you want to use, as shown in the following example:

```xml
<dependency>
	<groupId>io.r2dbc</groupId>
	<artifactId>r2dbc-h2</artifactId>
	<scope>runtime</scope>
</dependency>
```

> **Note:** If you are using this feature in your tests, you may notice that the same database is reused by your whole test suite regardless of the number of application contexts that you use. If you want to make sure that each context has a separate embedded database, you should set `spring.r2dbc.generate-unique-name` to `true`.

## Using DatabaseClient

A `DatabaseClient` bean is auto-configured, and you can autowire it directly into your own beans, as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.data.sql.r2dbc.usingdatabaseclient;

import java.util.Map;

import reactor.core.publisher.Flux;

import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Component;

@Component
public class MyBean {

	private final DatabaseClient databaseClient;

	public MyBean(DatabaseClient databaseClient) {
		this.databaseClient = databaseClient;
	}

	// @fold:on // ...
	public Flux<Map<String, Object>> someMethod() {
		return this.databaseClient.sql("select * from user").fetch().all();
	}
	// @fold:off

}
```

## Spring Data R2DBC Repositories

[Spring Data R2DBC](https://spring.io/projects/spring-data-relational) repositories are interfaces that you can define to access data. Queries are created automatically from your method names. For example, a `CityRepository` interface might declare a `findAllByState(String state)` method to find all the cities in a given state.

For more complex queries, you can annotate your method with Spring Data’s `@Query` annotation.

Spring Data repositories usually extend from the `Repository` or `CrudRepository` interfaces. If you use auto-configuration, the [auto-configuration packages](https://docs.spring.io/spring-boot/4.2.0/reference/using/auto-configuration.html#using.auto-configuration.packages) are searched for repositories.

The following example shows a typical Spring Data repository interface definition:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.data.sql.r2dbc.repositories;

import reactor.core.publisher.Mono;

import org.springframework.data.repository.Repository;

public interface CityRepository extends Repository<City, Long> {

	Mono<City> findByNameAndStateAllIgnoringCase(String name, String state);

}
```

> **Tip:** We have barely scratched the surface of Spring Data R2DBC. For complete details, see the [Spring Data R2DBC reference documentation](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc#L494).

## Related topics

- [Testing Spring Boot Applications](../testing/test-foundations.md)
- [JPA and Spring Data JPA](jpa-and-repositories.md)
