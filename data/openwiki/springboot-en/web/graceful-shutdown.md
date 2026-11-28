---
type: guide
title: "Graceful Shutdown"
description: "Spring Boot Graceful Shutdown: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","web"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-0bb7da3664e4e4e16c6b7b89
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/graceful-shutdown.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Graceful Shutdown

Graceful shutdown is enabled by default with all three embedded web servers (Jetty, Reactor Netty, and Tomcat) and with both reactive and servlet-based web applications. It occurs as part of closing the application context and is performed in the earliest phase of stopping `SmartLifecycle` beans. This stop processing uses a timeout which provides a grace period during which existing requests will be allowed to complete but no new requests will be permitted.

To configure the timeout period, configure the `spring.lifecycle.timeout-per-shutdown-phase` property, as shown in the following example:

```yaml
spring:
  lifecycle:
    timeout-per-shutdown-phase: "20s"
```

> **Important:** Shutdown in your IDE may be immediate rather than graceful if it does not send a proper `SIGTERM` signal. See the documentation of your IDE for more details.

## Rejecting Requests During the Grace Period

The exact way in which new requests are not permitted varies depending on the web server that is being used. Implementations may stop accepting requests at the network layer, or they may return a response with a specific HTTP status code or HTTP header. The use of persistent connections can also change the way that requests stop being accepted.

> **Tip:** To learn more about the specific method used with your web server, see the `shutDownGracefully` API documentation for `TomcatWebServer.shutDownGracefully(GracefulShutdownCallback)`, `NettyWebServer.shutDownGracefully(GracefulShutdownCallback)`, or `JettyWebServer.shutDownGracefully(GracefulShutdownCallback)`.

Jetty, Reactor Netty, and Tomcat will stop accepting new requests at the network layer.

## Disabling Graceful Shutdown

To disable graceful shutdown, configure the `server.shutdown` property, as shown in the following example:

```yaml
server:
  shutdown: "immediate"
```

## Related topics

- [Spring Security](../security/web-security.md)
- [Customizing Embedded Servlet Containers](embedded-server-customization.md)
