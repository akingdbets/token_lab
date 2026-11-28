---
type: guide
title: "Configure a DataSource"
description: "Spring Boot Configure a DataSource: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","data"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-6fe6686d5e12e76fb6684799
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Configure a DataSource

Java’s `DataSource` interface provides a standard method of working with database connections. Traditionally, a `DataSource` uses a `URL` along with some credentials to establish a database connection.

> **Tip:** See the [data-access.adoc](https://docs.spring.io/spring-boot/4.2.0/how-to/data-access.html#howto.data-access.configure-custom-datasource) section of the “How-to Guides” for more advanced examples, typically to take full control over the configuration of the DataSource.

## Embedded Database Support

It is often convenient to develop applications by using an in-memory embedded database. Obviously, in-memory databases do not provide persistent storage. You need to populate your database when your application starts and be prepared to throw away data when your application ends.

> **Tip:** The “How-to Guides” section includes a [section on how to initialize a database](https://docs.spring.io/spring-boot/4.2.0/how-to/data-initialization.html).

Spring Boot can auto-configure embedded [H2](https://www.h2database.com), [HSQL](https://hsqldb.org/), and [Derby](https://db.apache.org/derby/) (deprecated) databases. You need not provide any connection URLs. You need only include a build dependency to the embedded database that you want to use. If there are multiple embedded databases on the classpath, set the `spring.datasource.embedded-database-connection` configuration property to control which one is used. Setting the property to `none` disables auto-configuration of an embedded database.

> **Note:** If you are using this feature in your tests, you may notice that the same database is reused by your whole test suite regardless of the number of application contexts that you use. If you want to make sure that each context has a separate embedded database, you should set `spring.datasource.generate-unique-name` to `true`.

For example, the typical POM dependencies would be as follows:

```xml
<dependency>
	<groupId>org.springframework.boot</groupId>
	<artifactId>spring-boot-starter-data-jpa</artifactId>
</dependency>
<dependency>
	<groupId>org.hsqldb</groupId>
	<artifactId>hsqldb</artifactId>
	<scope>runtime</scope>
</dependency>
```

> **Note:** You need a dependency on `spring-jdbc` for an embedded database to be auto-configured. In this example, it is pulled in transitively through `spring-boot-starter-data-jpa`.

> **Tip:** If, for whatever reason, you do configure the connection URL for an embedded database, take care to ensure that the database’s automatic shutdown is disabled. If you use H2, you should use `DB_CLOSE_ON_EXIT=FALSE` to do so. If you use HSQLDB, you should ensure that `shutdown=true` is not used. Disabling the database’s automatic shutdown lets Spring Boot control when the database is closed, thereby ensuring that it happens once access to the database is no longer needed.

## Connection to a Production Database

Production database connections can also be auto-configured by using a pooling `DataSource`.

## DataSource Configuration

DataSource configuration is controlled by external configuration properties in `spring.datasource.*`. For example, you might declare the following section in `application.properties`:

```yaml
spring:
  datasource:
    url: "jdbc:mysql://localhost/test"
    username: "dbuser"
    password: "dbpass"
```

> **Note:** You should at least specify the URL by setting the `spring.datasource.url` property. Otherwise, Spring Boot tries to auto-configure an embedded database.

> **Tip:** Spring Boot can deduce the JDBC driver class for most databases from the URL. If you need to specify a specific class, you can use the `spring.datasource.driver-class-name` property.

> **Note:** For a pooling `DataSource` to be created, we need to be able to verify that a valid `Driver` class is available, so we check for that before doing anything. In other words, if you set `spring.datasource.driver-class-name=com.mysql.jdbc.Driver`, then that class has to be loadable.

See `DataSourceProperties` API documentation for more of the supported options. These are the standard options that work regardless of [the actual implementation](https://docs.spring.io/spring-boot/4.2.0/reference/data/sql.html#data.sql.datasource.connection-pool). It is also possible to fine-tune implementation-specific settings by using their respective prefix (`spring.datasource.hikari.*`, `spring.datasource.tomcat.*`, `spring.datasource.dbcp2.*`, and `spring.datasource.oracleucp.*`). See the documentation of the connection pool implementation you are using for more details.

For instance, if you use the [Tomcat connection pool](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/data/sql.adoc#L9), you could customize many additional settings, as shown in the following example:

```yaml
spring:
  datasource:
    tomcat:
      max-wait: 10000
      max-active: 50
      test-on-borrow: true
```

This will set the pool to wait 10000ms before throwing an exception if no connection is available, limit the maximum number of connections to 50 and validate the connection before borrowing it from the pool.

## Supported Connection Pools

Spring Boot uses the following algorithm for choosing a specific implementation:

1.  We prefer [HikariCP](https://github.com/brettwooldridge/HikariCP) for its performance and concurrency. If HikariCP is available, we always choose it.

2.  Otherwise, if the Tomcat pooling `DataSource` is available, we use it.

3.  Otherwise, if [Commons DBCP2](https://commons.apache.org/proper/commons-dbcp/) is available, we use it.

4.  If none of HikariCP, Tomcat, and DBCP2 are available and if Oracle UCP is available, we use it.


> **Note:** If you use the `spring-boot-starter-jdbc` or `spring-boot-starter-data-jpa` starters, you automatically get a dependency to HikariCP.

You can bypass that algorithm completely and specify the connection pool to use by setting the `spring.datasource.type` property. This is especially important if you run your application in a Tomcat container, as `tomcat-jdbc` is provided by default.

Additional connection pools can always be configured manually, using `DataSourceBuilder`. If you define your own `DataSource` bean, auto-configuration does not occur. The following connection pools are supported by `DataSourceBuilder`:

-   HikariCP

-   Tomcat pooling `DataSource`

-   Commons DBCP2

-   Oracle UCP & `OracleDataSource`

-   Spring Framework’s `SimpleDriverDataSource`

-   H2 `JdbcDataSource`

-   PostgreSQL `PGSimpleDataSource`

-   C3P0

-   Vibur


## Connection to a JNDI DataSource

If you deploy your Spring Boot application to an Application Server, you might want to configure and manage your DataSource by using your Application Server’s built-in features and access it by using JNDI.

The `spring.datasource.jndi-name` property can be used as an alternative to the `spring.datasource.url`, `spring.datasource.username`, and `spring.datasource.password` properties to access the `DataSource` from a specific JNDI location. For example, the following section in `application.properties` shows how you can access a JBoss AS defined `DataSource`:

```yaml
spring:
  datasource:
    jndi-name: "java:jboss/datasources/customers"
```

## Lazy Connection Proxy

When a pooled `DataSource` is auto-configured, it can be wrapped in a proxy that fetches JDBC connections as late as possible by setting `spring.datasource.connection-fetch` to `lazy`, as shown in the following example:

```yaml
spring:
  datasource:
    connection-fetch: "lazy"
```

With this feature enabled, JDBC Connections are only fetched from the pool when actually necessary. JDBC transaction control can happen without fetching a Connection from the pool or communicating with the database; this will be done lazily on the first creation of a JDBC Statement. To get access to the target auto-configured `DataSource`, use `DataSource.unwrap`.

> **Tip:** If you are wrapping the target `DataSource` in a `TransactionAwareDataSourceProxy`, make sure to do so with a `BeanPostProcessor` that has a positive order.

See `LazyConnectionDataSourceProxy` for more details.

## Related topics

- [Using JdbcTemplate](jdbc-template.md)
- [Validation](../validation/method-validation.md)
