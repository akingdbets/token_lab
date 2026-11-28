---
type: guide
title: "Spring MVC Auto-configuration"
description: "Spring Boot Spring MVC Auto-configuration: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","web"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-d4b0796f5d6d502198d9c96b
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Spring MVC Auto-configuration

Spring Boot provides auto-configuration for Spring MVC that works well with most applications. It replaces the need for `@EnableWebMvc` and the two cannot be used together. In addition to Spring MVC’s defaults, the auto-configuration provides the following features:

-   Inclusion of `ContentNegotiatingViewResolver` and `BeanNameViewResolver` beans.

-   Support for serving static resources, including support for WebJars (covered [later in this document](https://docs.spring.io/spring-boot/4.2.0/reference/web/servlet.html#web.servlet.spring-mvc.static-content)).

-   Automatic registration of `Converter`, `GenericConverter`, and `Formatter` beans.

-   Support for `HttpMessageConverters` (covered [later in this document](https://docs.spring.io/spring-boot/4.2.0/reference/web/servlet.html#web.servlet.spring-mvc.message-converters)).

-   Automatic registration of `MessageCodesResolver` (covered [later in this document](https://docs.spring.io/spring-boot/4.2.0/reference/web/servlet.html#web.servlet.spring-mvc.message-codes)).

-   Static `index.html` support.

-   Automatic use of a `ConfigurableWebBindingInitializer` bean (covered [later in this document](https://docs.spring.io/spring-boot/4.2.0/reference/web/servlet.html#web.servlet.spring-mvc.binding-initializer)).


If you want to keep those Spring Boot MVC customizations and make more [MVC customizations](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc#L33) (interceptors, formatters, view controllers, and other features), you can add your own `@Configuration` class of type `WebMvcConfigurer` but **without** `@EnableWebMvc`.

If you want to provide custom instances of `RequestMappingHandlerMapping`, `RequestMappingHandlerAdapter`, or `ExceptionHandlerExceptionResolver`, and still keep the Spring Boot MVC customizations, you can declare a bean of type `WebMvcRegistrations` and use it to provide custom instances of those components. The custom instances will be subject to further initialization and configuration by Spring MVC. To participate in, and if desired, override that subsequent processing, a `WebMvcConfigurer` should be used.

If you do not want to use the auto-configuration and want to take complete control of Spring MVC, add your own `@Configuration` annotated with `@EnableWebMvc`. Alternatively, add your own `@Configuration`\-annotated `DelegatingWebMvcConfiguration` as described in the `@EnableWebMvc` API documentation.

## Related topics

- [Spring MVC Conversion Service](conversion-service.md)
- [The Spring Web MVC Framework](controllers-and-routing.md)
