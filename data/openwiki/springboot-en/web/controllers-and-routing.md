---
type: guide
title: "The Spring Web MVC Framework"
description: "Spring Boot The Spring Web MVC Framework: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","web"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-d4b0796f5d6d502198d9c96b
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc
  - id: openwiki-source-939356a1f1bf2f5c1a4dddf6
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/web/servlet/springmvc/MyRestController.java
  - id: openwiki-source-44aa4792eb2760169dd4e93a
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/web/servlet/springmvc/MyRoutingConfiguration.java
  - id: openwiki-source-0af2c3d46c57b2f957a14a2e
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/web/servlet/springmvc/MyUserHandler.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# The “Spring Web MVC Framework”

The [Spring Web MVC framework](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc#L8) (often referred to as “Spring MVC”) is a rich “model view controller” web framework. Spring MVC lets you create special `@Controller` or `@RestController` beans to handle incoming HTTP requests. Methods in your controller are mapped to HTTP by using `@RequestMapping` annotations.

The following code shows a typical `@RestController` that serves JSON data:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.web.servlet.springmvc;

import java.util.List;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/users")
public class MyRestController {

	private final UserRepository userRepository;

	private final CustomerRepository customerRepository;

	public MyRestController(UserRepository userRepository, CustomerRepository customerRepository) {
		this.userRepository = userRepository;
		this.customerRepository = customerRepository;
	}

	@GetMapping("/{userId}")
	public User getUser(@PathVariable Long userId) {
		return this.userRepository.findById(userId).get();
	}

	@GetMapping("/{userId}/customers")
	public List<Customer> getUserCustomers(@PathVariable Long userId) {
		return this.userRepository.findById(userId).map(this.customerRepository::findByUser).get();
	}

	@DeleteMapping("/{userId}")
	public void deleteUser(@PathVariable Long userId) {
		this.userRepository.deleteById(userId);
	}

}
```

“WebMvc.fn”, the functional variant, separates the routing configuration from the actual handling of the requests, as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.web.servlet.springmvc;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.MediaType;
import org.springframework.web.servlet.function.RequestPredicate;
import org.springframework.web.servlet.function.RouterFunction;
import org.springframework.web.servlet.function.ServerResponse;

import static org.springframework.web.servlet.function.RequestPredicates.accept;
import static org.springframework.web.servlet.function.RouterFunctions.route;

@Configuration(proxyBeanMethods = false)
public class MyRoutingConfiguration {

	private static final RequestPredicate ACCEPT_JSON = accept(MediaType.APPLICATION_JSON);

	@Bean
	public RouterFunction<ServerResponse> routerFunction(MyUserHandler userHandler) {
		// @formatter:off
		return route()
				.GET("/{user}", ACCEPT_JSON, userHandler::getUser)
				.GET("/{user}/customers", ACCEPT_JSON, userHandler::getUserCustomers)
				.DELETE("/{user}", ACCEPT_JSON, userHandler::deleteUser)
				.build();
		// @formatter:on
	}

}
```

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.web.servlet.springmvc;

import org.springframework.stereotype.Component;
import org.springframework.web.servlet.function.ServerRequest;
import org.springframework.web.servlet.function.ServerResponse;

@Component
public class MyUserHandler {

	public ServerResponse getUser(ServerRequest request) {
		/**/ return ServerResponse.ok().build();
	}

	public ServerResponse getUserCustomers(ServerRequest request) {
		/**/ return ServerResponse.ok().build();
	}

	public ServerResponse deleteUser(ServerRequest request) {
		/**/ return ServerResponse.ok().build();
	}

}
```

Spring MVC is part of the core Spring Framework, and detailed information is available in the [reference documentation](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc#L8). There are also several guides that cover Spring MVC available at [https://spring.io/guides](https://spring.io/guides).

> **Tip:** You can define as many `RouterFunction` beans as you like to modularize the definition of the router. Beans can be ordered if you need to apply a precedence.

## Related topics

- [Spring MVC Auto-configuration](mvc-auto-configuration.md)
- [Log Levels](../configuration/logging-levels.md)
