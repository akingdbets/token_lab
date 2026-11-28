---
type: guide
title: "API Versioning"
description: "Spring Boot API Versioning: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","web"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-d4b0796f5d6d502198d9c96b
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# API Versioning

Spring MVC supports API versioning which can be used to evolve an HTTP API over time. The same `@Controller` path can be mapped multiple times to support different versions of the API.

For more details see [Spring Framework’s reference documentation](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc#L457).

Once mappings have been added, you additionally need to configure Spring MVC so that it is able to use any version information sent with a request. Typically, versions are sent as HTTP headers, query parameters, media type parameters, or as part of the path.

To configure Spring MVC, you can either use a `WebMvcConfigurer` bean and override the `configureApiVersioning(…​)` method, or you can use properties.

For example, the following will use an `X-Version` HTTP header to obtain version information and default to `1.0.0` when no header is sent.

```yaml
spring:
  mvc:
    apiversion:
      default: 1.0.0
      use:
        header: X-Version
```

> **Note:** If your setup requires multiple strategies, such as header and query parameter, consider declaring the order programmatically by overriding the `configureApiVersioning` method.

For more complete control, you can also define `ApiVersionResolver`, `ApiVersionParser` and `ApiVersionDeprecationHandler` beans which will be injected into the auto-configured Spring MVC configuration.

> **Tip:** API versioning is also supported with both `WebClient` and `RestClient`. See [io/rest-client.adoc](https://docs.spring.io/spring-boot/4.2.0/reference/io/rest-client.html#io.rest-client.apiversioning) for details.

## Related topics

- [Customizing Embedded Servlet Containers](embedded-server-customization.md)
- [CORS Support](cors.md)
