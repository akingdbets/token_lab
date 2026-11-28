---
type: guide
title: "Testing With a Mock Environment"
description: "Spring Boot Testing With a Mock Environment: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","testing"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-a98875ac417452e7afd8faa9
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc
  - id: openwiki-source-6bddb9600f34fa55ecb96444
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/withmockenvironment/MyMockMvcTests.java
  - id: openwiki-source-3efc382a1bad232aaf724bf8
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/withmockenvironment/MyMockWebTestClientTests.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Testing With a Mock Environment

By default, `@SpringBootTest` does not start the server but instead sets up a mock environment for testing web endpoints.

With Spring MVC, we can query our web endpoints using [`MockMvc`](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc#L138). The following integrations are available:

-   The regular [`MockMvc`](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc#L138) that uses Hamcrest.

-   [`MockMvcTester`](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc#L138) that wraps `MockMvc` and uses AssertJ.

-   [`RestTestClient`](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc#L138) where `MockMvc` is plugged in as the server to handle requests with.

-   [`WebTestClient`](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc#L138) where `MockMvc` is plugged in as the server to handle requests with.


The following example showcases the available integrations:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.withmockenvironment;

import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.resttestclient.autoconfigure.AutoConfigureRestTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.webtestclient.autoconfigure.AutoConfigureWebTestClient;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.assertj.MockMvcTester;
import org.springframework.test.web.servlet.client.RestTestClient;
import org.springframework.test.web.servlet.client.RestTestClient.ResponseSpec;
import org.springframework.test.web.servlet.client.assertj.RestTestClientResponse;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@AutoConfigureRestTestClient
@AutoConfigureWebTestClient
class MyMockMvcTests {

	@Test
	void testWithMockMvc(@Autowired MockMvc mvc) throws Exception {
		// @formatter:off
		mvc.perform(get("/"))
				.andExpect(status().isOk())
				.andExpect(content().string("Hello World"));
		// @formatter:on
	}

	@Test // If AssertJ is on the classpath, you can use MockMvcTester
	void testWithMockMvcTester(@Autowired MockMvcTester mvc) {
		// @formatter:off
		assertThat(mvc.get().uri("/"))
				.hasStatusOk()
				.hasBodyTextEqualTo("Hello World");
		// @formatter:on
	}

	@Test
	void testWithRestTestClient(@Autowired RestTestClient restClient) {
		// @formatter:off
		restClient
				.get().uri("/")
				.exchange()
				.expectStatus().isOk()
				.expectBody(String.class).isEqualTo("Hello World");
		// @formatter:on
	}

	@Test // If you prefer AssertJ, dedicated assertions are available
	void testWithRestTestClientAssertJ(@Autowired RestTestClient restClient) {
		// @formatter:off
		ResponseSpec spec = restClient.get().uri("/").exchange();
		RestTestClientResponse response = RestTestClientResponse.from(spec);
		assertThat(response).hasStatusOk()
				.bodyText().isEqualTo("Hello World");
		// @formatter:on
	}

	@Test // If Spring WebFlux is on the classpath
	void testWithWebTestClient(@Autowired WebTestClient webClient) {
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

> **Tip:** If you want to focus only on the web layer and not start a complete `ApplicationContext`, consider [using `@WebMvcTest` instead](https://docs.spring.io/spring-boot/4.2.0/reference/testing/spring-boot-applications.html#testing.spring-boot-applications.spring-mvc-tests).

With Spring WebFlux endpoints, you can use [`WebTestClient`](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc#L138) as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.withmockenvironment;

import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webtestclient.autoconfigure.AutoConfigureWebTestClient;
import org.springframework.test.web.reactive.server.WebTestClient;

@SpringBootTest
@AutoConfigureWebTestClient
class MyMockWebTestClientTests {

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

> **Tip:** Testing within a mocked environment is usually faster than running with a full servlet container. However, since mocking occurs at the Spring MVC layer, code that relies on lower-level servlet container behavior cannot be directly tested with MockMvc.
>
> For example, Spring Boot’s error handling is based on the “error page” support provided by the servlet container. This means that, whilst you can test your MVC layer throws and handles exceptions as expected, you cannot directly test that a specific [custom error page](https://docs.spring.io/spring-boot/4.2.0/reference/web/servlet.html#web.servlet.spring-mvc.error-handling.error-pages) is rendered. If you need to test these lower-level concerns, you can start a fully running server as described in the next section.

## Related topics

- [Testing With a Running Server](running-server.md)
- [Detecting Test Configuration](detecting-configuration.md)
