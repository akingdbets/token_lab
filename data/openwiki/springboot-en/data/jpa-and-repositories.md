---
type: guide
title: "JPA and Spring Data JPA"
description: "Spring Boot JPA and Spring Data JPA: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","data"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-6fe6686d5e12e76fb6684799
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc
  - id: openwiki-source-f3ce239861bb4a52ffa39f98
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/data/sql/jpaandspringdata/entityclasses/City.java
  - id: openwiki-source-2fcfb137da9305290bc00f17
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/data/sql/jpaandspringdata/enversrepositories/CountryRepository.java
  - id: openwiki-source-f6c69db53ba9b7dadb77cede
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/data/sql/jpaandspringdata/repositories/CityRepository.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# JPA and Spring Data JPA

The Java Persistence API is a standard technology that lets you “map” objects to relational databases. The `spring-boot-starter-data-jpa` POM provides a quick way to get started. It provides the following key dependencies:

-   Hibernate: One of the most popular JPA implementations.

-   Spring Data JPA: Helps you to implement JPA-based repositories.

-   Spring ORM: Core ORM support from the Spring Framework.


> **Tip:** We do not go into too many details of JPA or [Spring Data](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc#L224) here. You can follow the [Accessing Data with JPA](https://spring.io/guides/gs/accessing-data-jpa/) guide from [https://spring.io](https://spring.io) and read the [Spring Data JPA](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc#L224) and [Hibernate](https://hibernate.org/orm/documentation/) reference documentation.

## Entity Classes

Traditionally, JPA “Entity” classes are specified in a `persistence.xml` file. With Spring Boot, this file is not necessary and “Entity Scanning” is used instead. By default the [auto-configuration packages](https://docs.spring.io/spring-boot/4.2.0/reference/using/auto-configuration.html#using.auto-configuration.packages) are scanned.

Any classes annotated with `@Entity`, `@Embeddable`, or `@MappedSuperclass` are considered. A typical entity class resembles the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.data.sql.jpaandspringdata.entityclasses;

import java.io.Serializable;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;

@Entity
public class City implements Serializable {

	@Id
	@GeneratedValue
	private Long id;

	@Column(nullable = false)
	private String name;

	@Column(nullable = false)
	private String state;

	// ... additional members, often include @OneToMany mappings

	protected City() {
		// no-args constructor required by JPA spec
		// this one is protected since it should not be used directly
	}

	public City(String name, String state) {
		this.name = name;
		this.state = state;
	}

	public String getName() {
		return this.name;
	}

	public String getState() {
		return this.state;
	}

	// ... etc

}
```

> **Tip:** You can customize entity scanning locations by using the `@EntityScan` annotation. See the [data-access.adoc](https://docs.spring.io/spring-boot/4.2.0/how-to/data-access.html#howto.data-access.separate-entity-definitions-from-spring-configuration) section of the “How-to Guides”.

## Spring Data JPA Repositories

[Spring Data JPA](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc#L224) repositories are interfaces that you can define to access data. JPA queries are created automatically from your method names. For example, a `CityRepository` interface might declare a `findAllByState(String state)` method to find all the cities in a given state.

For more complex queries, you can annotate your method with Spring Data’s `Query` annotation.

Spring Data repositories usually extend from the `Repository` or `CrudRepository` interfaces. If you use auto-configuration, the [auto-configuration packages](https://docs.spring.io/spring-boot/4.2.0/reference/using/auto-configuration.html#using.auto-configuration.packages) are searched for repositories.

> **Tip:** You can customize the locations to look for repositories using `@EnableJpaRepositories`.

The following example shows a typical Spring Data repository interface definition:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.data.sql.jpaandspringdata.repositories;

import org.springframework.boot.docs.data.sql.jpaandspringdata.entityclasses.City;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.repository.Repository;

public interface CityRepository extends Repository<City, Long> {

	Page<City> findAll(Pageable pageable);

	City findByNameAndStateAllIgnoringCase(String name, String state);

}
```

Spring Data JPA repositories support three different modes of bootstrapping: default, deferred, and lazy. To enable deferred or lazy bootstrapping, set the `spring.data.jpa.repositories.bootstrap-mode` property to `deferred` or `lazy` respectively. When using deferred bootstrapping, the auto-configured `EntityManagerFactoryBuilder` requires a bootstrap executor and will use the context’s `AsyncTaskExecutor`, if one can be determined. If more than one exists, the one named `applicationTaskExecutor` will be used.

> **Note:** When using deferred or lazy bootstrapping, make sure to defer any access to the JPA infrastructure after the application context bootstrap phase. You can use `SmartInitializingSingleton` to invoke any initialization that requires the JPA infrastructure. For JPA components (such as converters) that are created as Spring beans, use `ObjectProvider` to delay the resolution of dependencies, if any.

> **Tip:** We have barely scratched the surface of Spring Data JPA. For complete details, see the [Spring Data JPA reference documentation](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc#L224).

## Spring Data Envers Repositories

If the [`spring-data-envers`](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc#L224) module from Spring Data JPA is available, JPA repositories are auto-configured to support typical Envers queries.

To use Spring Data Envers, make sure your repository extends from `RevisionRepository` as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.data.sql.jpaandspringdata.enversrepositories;

import org.springframework.boot.docs.data.sql.jpaandspringdata.entityclasses.Country;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.history.RevisionRepository;

public interface CountryRepository extends RevisionRepository<Country, Long, Integer>, Repository<Country, Long> {

	Page<Country> findAll(Pageable pageable);

}
```

> **Note:** For more details, check the [Spring Data Envers reference documentation](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc#L224).

## Creating and Dropping JPA Databases

By default, JPA databases are automatically created **only** if you use an embedded database, that is H2, HSQL, or Derby (deprecated). You can explicitly configure JPA settings by using `spring.jpa.*` properties. For example, to create and drop tables you can add the following line to your `application.properties`:

```yaml
spring:
  jpa:
    hibernate.ddl-auto: "create-drop"
```

> **Note:** Hibernate’s own internal property name for this (if you happen to remember it better) is `hibernate.hbm2ddl.auto`. You can set it, along with other Hibernate native properties, by using `spring.jpa.properties.*` (the prefix is stripped before adding them to the entity manager). The following line shows an example of setting JPA properties for Hibernate:

```yaml
spring:
  jpa:
    properties:
      hibernate:
        "globally_quoted_identifiers": "true"
```

The line in the preceding example passes a value of `true` for the `hibernate.globally_quoted_identifiers` property to the Hibernate entity manager.

By default, the DDL execution (or validation) is deferred until the `ApplicationContext` has started.

## Open EntityManager in View

If you are running a web application, Spring Boot by default registers `OpenEntityManagerInViewInterceptor` to apply the “Open EntityManager in View” pattern, to allow for lazy loading in web views. If you do not want this behavior, you should set `spring.jpa.open-in-view` to `false` in your `application.properties`.

## Related topics

- [Using R2DBC](r2dbc.md)
- [Using JdbcTemplate](jdbc-template.md)
