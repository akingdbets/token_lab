---
type: guide
title: "Testcontainers"
description: "Spring Boot Testcontainers: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","testing"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-7e7a32abb34ad5b683b1a3e0
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/testcontainers.adoc
  - id: openwiki-source-02cc898ee878d912dde29377
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/testcontainers/dynamicproperties/MyIntegrationTests.java
  - id: openwiki-source-7caa14cdcbfe827509573b8a
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/testcontainers/importingconfigurationinterfaces/MyContainers.java
  - id: openwiki-source-2d519b2677648e4a32d287f9
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/testcontainers/importingconfigurationinterfaces/MyTestConfiguration.java
  - id: openwiki-source-548b760ef4daaf33164a38ab
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/testcontainers/junitextension/MyIntegrationTests.java
  - id: openwiki-source-5058025f40bf5759eb2cc071
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/testcontainers/serviceconnections/MyIntegrationTests.java
  - id: openwiki-source-8d30eccfdd56812e6c5ad7e2
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/testcontainers/serviceconnections/MyRedisConfiguration.java
  - id: openwiki-source-e7f37947f6796b7b5d03886e
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/testcontainers/serviceconnections/ssl/MyElasticsearchWithSslIntegrationTests.java
  - id: openwiki-source-3e672c09f79d7d1e4c7f9d55
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/testcontainers/serviceconnections/ssl/MyRedisWithSslIntegrationTests.java
  - id: openwiki-source-bbc525a1f55503e2791afdf2
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/testcontainers/springbeans/MyIntegrationTests.java
  - id: openwiki-source-417ffd5782f062498a84ccaf
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/testcontainers/springbeans/MyTestConfiguration.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Testcontainers

The [Testcontainers](https://www.testcontainers.com/) library provides a way to manage services running inside Docker containers. It integrates with JUnit, allowing you to write a test class that can start up a container before any of the tests run. Testcontainers is especially useful for writing integration tests that talk to a real backend service such as MySQL, MongoDB, Cassandra and others.

In following sections we will describe some of the methods you can use to integrate Testcontainers with your tests.

## Using Spring Beans

The containers provided by Testcontainers can be managed by Spring Boot as beans.

To declare a container as a bean, add a `@Bean` method to your test configuration:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.testcontainers.springbeans;

import org.testcontainers.mongodb.MongoDBContainer;
import org.testcontainers.utility.DockerImageName;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;

@TestConfiguration(proxyBeanMethods = false)
class MyTestConfiguration {

	@Bean
	MongoDBContainer mongoDbContainer() {
		return new MongoDBContainer(DockerImageName.parse("mongo:5.0"));
	}

}
```

You can then inject and use the container by importing the configuration class in the test class:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.testcontainers.springbeans;

import org.junit.jupiter.api.Test;
import org.testcontainers.mongodb.MongoDBContainer;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;

@SpringBootTest
@Import(MyTestConfiguration.class)
class MyIntegrationTests {

	@Autowired
	private MongoDBContainer mongo;

	@Test
	void myTest() {
		/**/ System.out.println(this.mongo);
	}

}
```

> **Tip:** This method of managing containers is often used in combination with [service connection annotations](#service-connections).

## Using the JUnit Extension

Testcontainers provides a JUnit extension which can be used to manage containers in your tests. The extension is activated by applying the `@Testcontainers` annotation from Testcontainers to your test class.

You can then use the `@Container` annotation on static container fields.

The `@Testcontainers` annotation can be used on vanilla JUnit tests, or in combination with `@SpringBootTest`:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.testcontainers.junitextension;

import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.neo4j.Neo4jContainer;

import org.springframework.boot.test.context.SpringBootTest;

@Testcontainers
@SpringBootTest
class MyIntegrationTests {

	@Container
	static Neo4jContainer neo4j = new Neo4jContainer("neo4j:5");

	@Test
	void myTest() {
		/**/ System.out.println(neo4j);
	}

}
```

The example above will start up a Neo4j container before any of the tests are run. The lifecycle of the container instance is managed by Testcontainers, as described in [their official documentation](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/testcontainers.adoc#L1).

When using the JUnit extension, container instances are stopped after the test class has run (for static fields) or after each test method (for non-static fields). This can cause issues when used with Spring Boot tests, as Spring’s TestContext Framework may cache the `ApplicationContext` beyond that point and reuse it for another test class or method with the same configuration. If the cached application context contains beans that depend on a container that has already been stopped, later tests or bean destruction callbacks may fail. For this reason, you should prefer [managing containers as Spring beans](#using-spring-beans) or [importing container declarations](#importing-container-configuration-interfaces) when the application context should remain usable for as long as it is cached.

> **Note:** In most cases, you will additionally need to configure the application to connect to the service running in the container.

## Importing Container Configuration Interfaces

A common pattern with Testcontainers is to declare the container instances as static fields in an interface.

For example, the following interface declares two containers, one named `mongo` of type `MongoDBContainer` and another named `neo4j` of type `Neo4jContainer`:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.testcontainers.importingconfigurationinterfaces;

import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.mongodb.MongoDBContainer;
import org.testcontainers.neo4j.Neo4jContainer;

interface MyContainers {

	@Container
	MongoDBContainer mongoContainer = new MongoDBContainer("mongo:5.0");

	@Container
	Neo4jContainer neo4jContainer = new Neo4jContainer("neo4j:5");

}
```

When you have containers declared in this way, you can reuse their configuration in multiple tests by having the test classes implement the interface.

It’s also possible to use the same interface configuration in your Spring Boot tests. To do so, add `@ImportTestcontainers` to your test configuration class:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.testcontainers.importingconfigurationinterfaces;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.testcontainers.context.ImportTestcontainers;

@TestConfiguration(proxyBeanMethods = false)
@ImportTestcontainers(MyContainers.class)
class MyTestConfiguration {

}
```

## Lifecycle of Managed Containers

If you have used the annotations and extensions provided by Testcontainers, then the lifecycle of container instances is managed entirely by Testcontainers. Please refer to the [official Testcontainers documentation](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/testcontainers.adoc#L1) for the information.

When the containers are managed by Spring as beans, then their lifecycle is managed by Spring:

-   Container beans are created and started before all other beans.

-   Container beans are stopped after the destruction of all other beans.


This process ensures that any beans, which rely on functionality provided by the containers, can use those functionalities. It also ensures that they are cleaned up whilst the container is still available.

> **Tip:** When your application beans rely on functionality of containers, prefer configuring the containers as Spring beans to ensure the correct lifecycle behavior.

> **Note:** Having containers managed by Testcontainers instead of as Spring beans provides no guarantee of the order in which beans and containers will shutdown. It can happen that containers are shutdown before the beans relying on container functionality are cleaned up. This can lead to exceptions being thrown by client beans, for example, due to loss of connection. When the application context should remain usable for as long as it is cached, prefer managing containers as Spring beans or importing container declarations with `@ImportTestcontainers`.

Container beans are created and started once per application context managed by Spring’s TestContext Framework. For details about how the TestContext Framework manages the underlying application contexts and beans therein, please refer to the [Spring Framework documentation](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/testcontainers.adoc#L1).

Container beans are stopped as part of the TestContext Framework’s standard application context shutdown process. When the application context gets shutdown, the containers are shutdown as well. This usually happens after all tests using that specific cached application context have finished executing. It may also happen earlier, depending on the caching behavior configured in the TestContext Framework.

> **Note:** A single test container instance can, and often is, retained across execution of tests from multiple test classes.

## Service Connections

A service connection is a connection to any remote service. Spring Boot’s auto-configuration can consume the details of a service connection and use them to establish a connection to a remote service. When doing so, the connection details take precedence over any connection-related configuration properties.

When using Testcontainers, connection details can be automatically created for a service running in a container by annotating the container field in the test class.

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.testcontainers.serviceconnections;

import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.neo4j.Neo4jContainer;

import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;

@Testcontainers
@SpringBootTest
class MyIntegrationTests {

	@Container
	@ServiceConnection
	static Neo4jContainer neo4j = new Neo4jContainer("neo4j:5");

	@Test
	void myTest() {
		/**/ System.out.println(neo4j);
	}

}
```

Thanks to `@ServiceConnection`, the above configuration allows Neo4j-related beans in the application to communicate with Neo4j running inside the Testcontainers-managed Docker container. This is done by automatically defining a `Neo4jConnectionDetails` bean which is then used by the Neo4j auto-configuration, overriding any connection-related configuration properties.

> **Note:** You’ll need to add the `spring-boot-testcontainers` module as a test dependency in order to use service connections with Testcontainers.

Service connection annotations are processed by `ContainerConnectionDetailsFactory` classes registered with `spring.factories`. A `ContainerConnectionDetailsFactory` can create a `ConnectionDetails` bean based on a specific `Container` subclass, or the Docker image name.

The following service connection factories are provided in the `spring-boot-testcontainers` jar:

| Connection Details | Matched on |
| --- | --- |
| `ActiveMQConnectionDetails` | Containers named "symptoma/activemq" or `ActiveMQContainer` |
| `AmqpConnectionDetails` | Containers of types `RabbitMQContainer` or `ActiveMQContainer` or `ArtemisContainer` |
| `ArtemisConnectionDetails` | Containers of type `ArtemisContainer` |
| `CassandraConnectionDetails` | Containers of type `CassandraContainer` |
| `CouchbaseConnectionDetails` | Containers of type `CouchbaseContainer` |
| `ElasticsearchConnectionDetails` | Containers of type `ElasticsearchContainer` |
| `FlywayConnectionDetails` | Containers of type `JdbcDatabaseContainer` |
| `JdbcConnectionDetails` | Containers of type `JdbcDatabaseContainer` |
| `KafkaConnectionDetails` | Containers of type `KafkaContainer`, `ConfluentKafkaContainer` or `RedpandaContainer` |
| `LdapConnectionDetails` | Containers named "osixia/openldap" or of type `LLdapContainer` |
| `LiquibaseConnectionDetails` | Containers of type `JdbcDatabaseContainer` |
| `MongoConnectionDetails` | Containers of type `MongoDBContainer` or `MongoDBAtlasLocalContainer` |
| `Neo4jConnectionDetails` | Containers of type `Neo4jContainer` |
| `OtlpLoggingConnectionDetails` | Containers named "otel/opentelemetry-collector-contrib" or of type `LgtmStackContainer` |
| `OtlpMetricsConnectionDetails` | Containers named "otel/opentelemetry-collector-contrib" or of type `LgtmStackContainer` |
| `OtlpTracingConnectionDetails` | Containers named "otel/opentelemetry-collector-contrib" or of type `LgtmStackContainer` |
| `PulsarConnectionDetails` | Containers of type `PulsarContainer` |
| `R2dbcConnectionDetails` | Containers of type `ClickHouseContainer`, `MariaDBContainer`, `MSSQLServerContainer`, `MySQLContainer`, `OracleContainer (free)`, `OracleContainer (XE)` or `PostgreSQLContainer` |
| `RabbitConnectionDetails` | Containers of type `RabbitMQContainer` |
| `RabbitStreamConnectionDetails` | Containers of type `RabbitMQContainer` when the `@ServiceConnection` `type` attribute includes `RabbitStreamConnectionDetails` |
| `DataRedisConnectionDetails` | Containers of type `RedisContainer` or `RedisStackContainer`, or containers named "redis", "redis/redis-stack" or "redis/redis-stack-server" |
| `ZipkinConnectionDetails` | Containers named "openzipkin/zipkin" |

> **Tip:** By default, with the exception of `RabbitStreamConnectionDetails`, all applicable connection details beans will be created for a given `Container`. For example, a `PostgreSQLContainer` will create both `JdbcConnectionDetails` and `R2dbcConnectionDetails`.
>
> If you want to create only a subset of the applicable types, you can use the `type` attribute of `@ServiceConnection`.
>
> To create a `RabbitStreamConnectionDetails` bean from a `RabbitMQContainer`, you must opt in using the `type` attribute of `@ServiceConnection`. The container must also expose port 5552, or port 5551 when SSL is configured, for RabbitMQ Streams.

By default `Container.getDockerImageName().getRepository()` is used to obtain the name used to find connection details. The repository portion of the Docker image name ignores any registry and the version. This works as long as Spring Boot is able to get the instance of the `Container`, which is the case when using a `static` field like in the example above.

If you’re using a `@Bean` method, Spring Boot won’t call the bean method to get the Docker image name, because this would cause eager initialization issues. Instead, the return type of the bean method is used to find out which connection detail should be used. This works as long as you’re using typed containers such as `Neo4jContainer` or `RabbitMQContainer`. This stops working if you’re using `GenericContainer`, for example with Redis as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.testcontainers.serviceconnections;

import org.testcontainers.containers.GenericContainer;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Bean;

@TestConfiguration(proxyBeanMethods = false)
public class MyRedisConfiguration {

	@Bean
	@ServiceConnection(name = "redis")
	public GenericContainer<?> redisContainer() {
		return new GenericContainer<>("redis:7");
	}

}
```

Spring Boot can’t tell from `GenericContainer` which container image is used, so the `name` attribute from `@ServiceConnection` must be used to provide that hint.

You can also use the `name` attribute of `@ServiceConnection` to override which connection detail will be used, for example when using custom images. If you are using the Docker image `registry.mycompany.com/mirror/myredis`, you’d use `@ServiceConnection(name="redis")` to ensure `DataRedisConnectionDetails` are created.

### SSL with Service Connections

You can use the `@Ssl`, `@JksKeyStore`, `@JksTrustStore`, `@PemKeyStore` and `@PemTrustStore` annotations on a supported container to enable SSL support for that service connection. Please note that you still have to enable SSL on the service which is running inside the Testcontainer yourself, the annotations only configure SSL on the client side in your application.

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.testcontainers.serviceconnections.ssl;

import com.redis.testcontainers.RedisContainer;
import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.PemKeyStore;
import org.springframework.boot.testcontainers.service.connection.PemTrustStore;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.data.redis.core.RedisOperations;

@Testcontainers
@SpringBootTest
class MyRedisWithSslIntegrationTests {

	@Container
	@ServiceConnection
	@PemKeyStore(certificate = "classpath:client.crt", privateKey = "classpath:client.key")
	@PemTrustStore("classpath:ca.crt")
	static RedisContainer redis = new SecureRedisContainer("redis:latest");

	@Autowired
	@SuppressWarnings("unused")
	private RedisOperations<Object, Object> operations;

	@Test
	void testRedis() {
		// ...
	}

}
```

The above code uses the `@PemKeyStore` annotation to load the client certificate and key into the keystore and the `@PemTrustStore` annotation to load the CA certificate into the truststore. This will authenticate the client against the server, and the CA certificate in the truststore makes sure that the server certificate is valid and trusted.

The `SecureRedisContainer` in this example is a custom subclass of `RedisContainer` which copies certificates to the correct places and invokes `redis-server` with commandline parameters enabling SSL.

The SSL annotations are supported for the following service connections:

-   Cassandra

-   Couchbase

-   Elasticsearch

-   Kafka

-   LDAP

-   MongoDB

-   OpenTelemetry (OTLP logging, metrics, and tracing)

-   RabbitMQ

-   RabbitMQ Streams

-   Redis


The `ElasticsearchContainer` additionally supports automatic detection of server side SSL. To use this feature, annotate the container with `@Ssl`, as seen in the following example, and Spring Boot takes care of the client side SSL configuration for you:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.testcontainers.serviceconnections.ssl;

import org.junit.jupiter.api.Test;
import org.testcontainers.elasticsearch.ElasticsearchContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.elasticsearch.test.autoconfigure.DataElasticsearchTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.boot.testcontainers.service.connection.Ssl;
import org.springframework.data.elasticsearch.client.elc.ElasticsearchTemplate;

@Testcontainers
@DataElasticsearchTest
class MyElasticsearchWithSslIntegrationTests {

	@Ssl
	@Container
	@ServiceConnection
	static ElasticsearchContainer elasticsearch = new ElasticsearchContainer(
			"docker.elastic.co/elasticsearch/elasticsearch:8.17.2");

	@Autowired
	@SuppressWarnings("unused")
	private ElasticsearchTemplate elasticsearchTemplate;

	@Test
	void testElasticsearch() {
		// ...
	}

}
```

## Dynamic Properties

A slightly more verbose but also more flexible alternative to service connections is `@DynamicPropertySource`. A static `@DynamicPropertySource` method allows adding dynamic property values to the Spring Environment.

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.testcontainers.dynamicproperties;

import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.neo4j.Neo4jContainer;

import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@Testcontainers
@SpringBootTest
class MyIntegrationTests {

	@Container
	static Neo4jContainer neo4j = new Neo4jContainer("neo4j:5");

	@Test
	void myTest() {
		// ...
	}

	@DynamicPropertySource
	static void neo4jProperties(DynamicPropertyRegistry registry) {
		registry.add("spring.neo4j.uri", neo4j::getBoltUrl);
	}

}
```

The above configuration allows Neo4j-related beans in the application to communicate with Neo4j running inside the Testcontainers-managed Docker container.

## Related topics

- [Efficient Deployments](../deployment/efficient-packaging.md)
- [Auto-configured Data JPA Tests](jpa-tests.md)
