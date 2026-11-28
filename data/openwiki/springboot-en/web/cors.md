---
type: guide
title: "CORS Support"
description: "Spring Boot CORS Support: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","web"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-d4b0796f5d6d502198d9c96b
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc
  - id: openwiki-source-fb684b24a637a36ead21dd3a
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/web/servlet/springmvc/cors/MyCorsConfiguration.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# CORS Support

[Cross-origin resource sharing](https://en.wikipedia.org/wiki/Cross-origin_resource_sharing) (CORS) is a [W3C specification](https://www.w3.org/TR/cors/) implemented by [most browsers](https://caniuse.com/#feat=cors) that lets you specify in a flexible way what kind of cross-domain requests are authorized, instead of using some less secure and less powerful approaches such as IFRAME or JSONP.

As of version 4.2, Spring MVC [supports CORS](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc#L444). Using [controller method CORS configuration](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc#L444) with `@CrossOrigin` annotations in your Spring Boot application does not require any specific configuration. [Global CORS configuration](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc#L444) can be defined by registering a `WebMvcConfigurer` bean with a customized `addCorsMappings(CorsRegistry)` method, as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.web.servlet.springmvc.cors;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration(proxyBeanMethods = false)
public class MyCorsConfiguration {

	@Bean
	public WebMvcConfigurer corsConfigurer() {
		return new WebMvcConfigurer() {

			@Override
			public void addCorsMappings(CorsRegistry registry) {
				registry.addMapping("/api/**");
			}

		};
	}

}
```

## Related topics

- [API Versioning](api-versioning.md)
- [Error Handling](error-handling.md)
