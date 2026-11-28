---
type: guide
title: "Testing With a Running Server"
description: "Spring Boot Testing With a Running Server: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","testing"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-a98875ac417452e7afd8faa9
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc
  - id: openwiki-source-8930949ae62236691a3ad207
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/withrunningserver/MyRandomPortRestTestClientAssertJTests.java
  - id: openwiki-source-d78c1e43d1f570cffb3b5d08
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/withrunningserver/MyRandomPortRestTestClientTests.java
  - id: openwiki-source-7032075b950858ba9a64c2d9
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/withrunningserver/MyRandomPortWebTestClientTests.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Testing With a Running Server

If you need to start a full running server, we recommend that you use random ports. If you use `@SpringBootTest(webEnvironment=WebEnvironment.RANDOM_PORT)`, an available port is picked at random each time your test runs.

The `@LocalServerPort` annotation can be used to [inject the actual port used](https://docs.spring.io/spring-boot/4.2.0/how-to/webserver.html#howto.webserver.discover-port) into your test.

Tests that need to make REST calls to the started server can autowire a [`RestTestClient`](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc#L173) by annotating the test class with `@AutoConfigureRestTestClient`.

The configured client resolves relative links to the running server and comes with a dedicated API for verifying responses, as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.withrunningserver;

import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.resttestclient.autoconfigure.AutoConfigureRestTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.test.web.servlet.client.RestTestClient;

@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@AutoConfigureRestTestClient
class MyRandomPortRestTestClientTests {

	@Test
	void exampleTest(@Autowired RestTestClient restClient) {
		// @formatter:off
		restClient
			.get().uri("/")
			.exchange()
			.expectStatus().isOk()
			.expectBody(String.class).isEqualTo("Hello World");
		// @formatter:on
	}

}
```

If you prefer to use AssertJ, dedicated assertions are available from `RestTestClientResponse`, as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.withrunningserver;

import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.resttestclient.autoconfigure.AutoConfigureRestTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.test.web.servlet.client.RestTestClient;
import org.springframework.test.web.servlet.client.RestTestClient.ResponseSpec;
import org.springframework.test.web.servlet.client.assertj.RestTestClientResponse;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@AutoConfigureRestTestClient
class MyRandomPortRestTestClientAssertJTests {

	@Test
	void exampleTest(@Autowired RestTestClient restClient) {
		// @formatter:off
		ResponseSpec spec = restClient.get().uri("/").exchange();
		RestTestClientResponse response = RestTestClientResponse.from(spec);
		assertThat(response).hasStatusOk().bodyText().isEqualTo("Hello World");
		// @formatter:on
	}

}
```

If you have `spring-webflux` on the classpath, you can also autowire a [`WebTestClient`](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc#L173) by annotating the test class with `@AutoConfigureWebTestClient`.

`WebTestClient` provides a similar API, as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.withrunningserver;

import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.boot.webtestclient.autoconfigure.AutoConfigureWebTestClient;
import org.springframework.test.web.reactive.server.WebTestClient;

@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@AutoConfigureWebTestClient
class MyRandomPortWebTestClientTests {

	@Test
	void exampleTest(@Autowired WebTestClient webClient) {
		// @formatter:off
		webClient
			.get().uri("/")
			.exchange()
			.expectStatus().isOk()
			.expectBody(String.class).isEqualTo("Hello World");
		// @formatter:on
	}

}
```

> **Tip:** `WebTestClient` can also be used with a [mock environment](https://docs.spring.io/spring-boot/4.2.0/reference/testing/spring-boot-applications.html#testing.spring-boot-applications.with-mock-environment), removing the need for a running server, by annotating your test class with `@AutoConfigureWebTestClient` from `spring-boot-webflux-test`.

> **Note:** For certain [sliced tests](https://docs.spring.io/spring-boot/4.2.0/reference/testing/spring-boot-applications.html#testing.spring-boot-applications.autoconfigured-tests) you may need to use the `@AutoConfigureWebServer` annotation to auto-configure an embedded web server.

## Related topics

- [Auto-configured JSON Tests](json-tests.md)
- [Testing With a Mock Environment](mock-environment.md)
