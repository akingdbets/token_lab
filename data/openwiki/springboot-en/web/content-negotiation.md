---
type: guide
title: "Path Matching and Content Negotiation"
description: "Spring Boot Path Matching and Content Negotiation: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","web"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-d4b0796f5d6d502198d9c96b
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Path Matching and Content Negotiation

Spring MVC can map incoming HTTP requests to handlers by looking at the request path and matching it to the mappings defined in your application (for example, `@GetMapping` annotations on Controller methods).

Spring Boot chooses to disable suffix pattern matching by default, which means that requests like `"GET /projects/spring-boot.json"` will not be matched to `@GetMapping("/projects/spring-boot")` mappings. This is considered as a [best practice for Spring MVC applications](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc#L238). This feature was mainly useful in the past for HTTP clients which did not send proper "Accept" request headers; we needed to make sure to send the correct Content Type to the client. Nowadays, Content Negotiation is much more reliable.

There are other ways to deal with HTTP clients that do not consistently send proper "Accept" request headers. Instead of using suffix matching, we can use a query parameter to ensure that requests like `"GET /projects/spring-boot?format=json"` will be mapped to `@GetMapping("/projects/spring-boot")`:

```yaml
spring:
  mvc:
    contentnegotiation:
      favor-parameter: true
```

Or if you prefer to use a different parameter name:

```yaml
spring:
  mvc:
    contentnegotiation:
      favor-parameter: true
      parameter-name: "myparam"
```

Most standard media types are supported out-of-the-box, but you can also define new ones:

```yaml
spring:
  mvc:
    contentnegotiation:
      media-types:
        markdown: "text/markdown"
```

Spring Boot uses the `PathPatternParser` strategy for matching request paths to controllers. `PathPatternParser` is an [optimized implementation](https://spring.io/blog/2020/06/30/url-matching-with-pathpattern-in-spring-mvc) but restricts usage of [some path pattern variants](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc#L238). It is also incompatible with configuring the `DispatcherServlet` with a path prefix (`spring.mvc.servlet.path`).

Spring MVC will throw a `NoHandlerFoundException` if a handler is not found for a request. Note that, by default, the [serving of static content](https://docs.spring.io/spring-boot/4.2.0/reference/web/servlet.html#web.servlet.spring-mvc.static-content) is mapped to `/**` and will, therefore, provide a handler for all requests. If no static content is available, `ResourceHttpRequestHandler` will throw a `NoResourceFoundException`. For a `NoHandlerFoundException` to be thrown, set `spring.mvc.static-path-pattern` to a more specific value such as `/resources/**` or set `spring.web.resources.add-mappings` to `false` to disable serving of static content entirely.

## Related topics

- [Error Handling](error-handling.md)
- [Static Content](static-content.md)
