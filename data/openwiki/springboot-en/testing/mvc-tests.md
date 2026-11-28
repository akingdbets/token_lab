---
type: guide
title: "Auto-configured Spring MVC Tests"
description: "Spring Boot Auto-configured Spring MVC Tests: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","testing"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-a98875ac417452e7afd8faa9
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/testing/spring-boot-applications.adoc
  - id: openwiki-source-7e970e709cae6d006ae336c5
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/springmvctests/MockTransportTests.java
  - id: openwiki-source-cbe8d867bbfe9da0233a8923
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/springmvctests/MyControllerTests.java
  - id: openwiki-source-7d3ba8f54740217a8ef9f283
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing/springbootapplications/springmvctests/MyHtmlUnitTests.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Auto-configured Spring MVC Tests

To test whether Spring MVC controllers are working as expected, use the `@WebMvcTest` annotation from the `spring-boot-webmvc-test` module. `@WebMvcTest` auto-configures the Spring MVC infrastructure and limits scanned beans to `@Controller`, `@ControllerAdvice`, `@JacksonComponent`, `@JsonComponent` (deprecated), `Converter`, `GenericConverter`, `Filter`, `HandlerInterceptor`, `WebMvcConfigurer`, `WebMvcRegistrations`, and `HandlerMethodArgumentResolver`. Regular `@Component` and `@ConfigurationProperties` beans are not scanned when the `@WebMvcTest` annotation is used. `@EnableConfigurationProperties` can be used to include `@ConfigurationProperties` beans.

> **Tip:** A list of the auto-configuration settings that are enabled by `@WebMvcTest` can be [found in the appendix](https://docs.spring.io/spring-boot/4.2.0/appendix/test-auto-configuration/index.html).

> **Tip:** If you need to register extra components, such as a `JacksonModule`, you can import additional configuration classes by using `@Import` on your test.

Often, `@WebMvcTest` is limited to a single controller and is used in combination with `@MockitoBean` to provide mock implementations for required collaborators.

`@WebMvcTest` also auto-configures `MockMvc`. Mock MVC offers a powerful way to quickly test MVC controllers without needing to start a full HTTP server. If AssertJ is available, the AssertJ support provided by `MockMvcTester` is auto-configured as well.

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.springmvctests;

import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.assertj.MockMvcTester;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;

@WebMvcTest(UserVehicleController.class)
class MyControllerTests {

	@Autowired
	private MockMvcTester mvc;

	@MockitoBean
	private UserVehicleService userVehicleService;

	@Test
	void testExample() {
		// @formatter:off
		given(this.userVehicleService.getVehicleDetails("sboot"))
			.willReturn(new VehicleDetails("Honda", "Civic"));
		assertThat(this.mvc.get().uri("/sboot/vehicle").accept(MediaType.TEXT_PLAIN))
			.hasStatusOk()
			.hasBodyTextEqualTo("Honda Civic");
		// @formatter:on
	}

}
```

If you’d like to use `RestTestClient` in your tests, annotate your test class with `@AutoConfigureRestTestClient`. A `RestTestClient` that uses the Mock MVC infrastructure will then be auto-configured.

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.springmvctests;

import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.restclient.test.autoconfigure.AutoConfigureRestClient;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.client.RestTestClient;

import static org.mockito.BDDMockito.given;

@WebMvcTest(UserVehicleController.class)
@AutoConfigureRestClient
class MockTransportTests {

	@Autowired
	private RestTestClient restClient;

	@MockitoBean
	private UserVehicleService userVehicleService;

	@Test
	void testExample() {
		// @formatter:off
		given(this.userVehicleService.getVehicleDetails("sboot"))
			.willReturn(new VehicleDetails("Honda", "Civic"));
		this.restClient.get().uri("/sboot/vehicle").accept(MediaType.TEXT_PLAIN)
				.exchangeSuccessfully()
				.expectBody(String.class)
				.isEqualTo("Honda Civic");
		// @formatter:on
	}

}
```

> **Tip:** You can also auto-configure `MockMvc` and `MockMvcTester` in a non-`@WebMvcTest` (such as `@SpringBootTest`) by annotating it with `@AutoConfigureMockMvc`. The following example uses `MockMvcTester`:

> **Tip:** If you need to configure elements of the auto-configuration (for example, when servlet filters should be applied) you can use attributes in the `@AutoConfigureMockMvc` annotation.

If you use HtmlUnit and Selenium, auto-configuration also provides an HtmlUnit `WebClient` bean and/or a Selenium `WebDriver` bean. The following example uses HtmlUnit:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.testing.springbootapplications.springmvctests;

import org.htmlunit.WebClient;
import org.htmlunit.html.HtmlPage;
import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;

@WebMvcTest(UserVehicleController.class)
class MyHtmlUnitTests {

	@Autowired
	private WebClient webClient;

	@MockitoBean
	private UserVehicleService userVehicleService;

	@Test
	void testExample() throws Exception {
		given(this.userVehicleService.getVehicleDetails("sboot")).willReturn(new VehicleDetails("Honda", "Civic"));
		HtmlPage page = this.webClient.getPage("/sboot/vehicle.html");
		assertThat(page.getBody().getTextContent()).isEqualTo("Honda Civic");
	}

}
```

> **Note:** By default, Spring Boot puts `WebDriver` beans in a special “scope” to ensure that the driver exits after each test and that a new instance is injected. If you do not want this behavior, you can add `@Scope(ConfigurableBeanFactory.SCOPE_SINGLETON)` to your `WebDriver` `@Bean` definition.

> **Warning:** The `webDriver` scope created by Spring Boot will replace any user defined scope of the same name. If you define your own `webDriver` scope you may find it stops working when you use `@WebMvcTest`.

If you have Spring Security on the classpath, `@WebMvcTest` will also scan `WebSecurityConfigurer` beans. Instead of disabling security completely for such tests, you can use Spring Security’s test support. More details on how to use Spring Security’s `MockMvc` support can be found in this [testing.adoc](https://docs.spring.io/spring-boot/4.2.0/how-to/testing.html#howto.testing.with-spring-security) “How-to Guides” section.

> **Tip:** Sometimes writing Spring MVC tests is not enough; Spring Boot can help you run [full end-to-end tests with an actual server](https://docs.spring.io/spring-boot/4.2.0/reference/testing/spring-boot-applications.html#testing.spring-boot-applications.with-running-server).

## Related topics

- [Auto-configured Data JPA Tests](jpa-tests.md)
- [Auto-configured JSON Tests](json-tests.md)
