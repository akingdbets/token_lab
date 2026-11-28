---
type: guide
title: "Customizing Embedded Servlet Containers"
description: "Spring Boot Customizing Embedded Servlet Containers: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","web"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-d4b0796f5d6d502198d9c96b
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/web/servlet.adoc
  - id: openwiki-source-8241cf6ed272f89918482123
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/web/servlet/embeddedcontainer/customizing/programmatic/MyTomcatWebServerFactoryCustomizer.java
  - id: openwiki-source-579d2907f2e2136a2b3c53b6
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/web/servlet/embeddedcontainer/customizing/programmatic/MyWebServerFactoryCustomizer.java
  - id: openwiki-source-0ad224a69e1b78ac6017469a
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/web/servlet/embeddedcontainer/customizing/samesite/MySameSiteConfiguration.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Customizing Embedded Servlet Containers

Common servlet container settings can be configured by using Spring `Environment` properties. Usually, you would define the properties in your `application.properties` or `application.yaml` file.

Common server settings include:

-   Network settings: Listen port for incoming HTTP requests (`server.port`), interface address to bind to (`server.address`), and so on.

-   Session settings: Whether the session is persistent (`server.servlet.session.persistent`), session timeout (`server.servlet.session.timeout`), location of session data (`server.servlet.session.store-dir`), and session-cookie configuration (`server.servlet.session.cookie.*`).

-   Error management: Location of the error page (`spring.web.error.path`) and so on.

-   [SSL](https://docs.spring.io/spring-boot/4.2.0/how-to/webserver.html#howto.webserver.configure-ssl)

-   [HTTP compression](https://docs.spring.io/spring-boot/4.2.0/how-to/webserver.html#howto.webserver.enable-response-compression)


Spring Boot tries as much as possible to expose common settings, but this is not always possible. For those cases, dedicated namespaces offer server-specific customizations (see `server.tomcat`). For instance, [access logs](https://docs.spring.io/spring-boot/4.2.0/how-to/webserver.html#howto.webserver.configure-access-logs) can be configured with specific features of the embedded servlet container.

> **Tip:** See the `ServerProperties` class for a complete list.

## SameSite Cookies

The `SameSite` cookie attribute can be used by web browsers to control if and how cookies are submitted in cross-site requests. The attribute is particularly relevant for modern web browsers which have started to change the default value that is used when the attribute is missing.

If you want to change the `SameSite` attribute of your session cookie, you can use the `server.servlet.session.cookie.same-site` property. This property is supported by auto-configured Tomcat and Jetty servers. It is also used to configure Spring Session servlet based `SessionRepository` beans.

For example, if you want your session cookie to have a `SameSite` attribute of `None`, you can add the following to your `application.properties` or `application.yaml` file:

```yaml
server:
  servlet:
    session:
      cookie:
        same-site: "none"
```

If you want to change the `SameSite` attribute on other cookies added to your `HttpServletResponse`, you can use a `CookieSameSiteSupplier`. The `CookieSameSiteSupplier` is passed a `Cookie` and may return a `SameSite` value, or `null`.

There are a number of convenience factory and filter methods that you can use to quickly match specific cookies. For example, adding the following bean will automatically apply a `SameSite` of `Lax` for all cookies with a name that matches the regular expression `myapp.*`.

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.web.servlet.embeddedcontainer.customizing.samesite;

import org.springframework.boot.web.server.servlet.CookieSameSiteSupplier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class MySameSiteConfiguration {

	@Bean
	public CookieSameSiteSupplier applicationCookieSameSiteSupplier() {
		return CookieSameSiteSupplier.ofLax().whenHasNameMatching("myapp.*");
	}

}
```

## Character Encoding

The character encoding behavior of the embedded servlet container for request and response handling can be configured using the `server.servlet.encoding.*` configuration properties.

When a request’s `Accept-Language` header indicates a locale for the request it will be automatically mapped to a charset by the servlet container. Each container provides default locale to charset mappings and you should verify that they meet your application’s needs. When they do not, use the `server.servlet.encoding.mapping` configuration property to customize the mappings, as shown in the following example:

```yaml
server:
  servlet:
    encoding:
      mapping:
        ko: "UTF-8"
```

In the preceding example, the `ko` (Korean) locale has been mapped to `UTF-8`. This is equivalent to a `<locale-encoding-mapping-list>` entry in a `web.xml` file of a traditional war deployment.

## Programmatic Customization

If you need to programmatically configure your embedded servlet container, you can register a Spring bean that implements the `WebServerFactoryCustomizer` interface. `WebServerFactoryCustomizer` provides access to the `ConfigurableServletWebServerFactory`, which includes numerous customization setter methods. The following example shows programmatically setting the port:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.web.servlet.embeddedcontainer.customizing.programmatic;

import org.springframework.boot.web.server.WebServerFactoryCustomizer;
import org.springframework.boot.web.server.servlet.ConfigurableServletWebServerFactory;
import org.springframework.stereotype.Component;

@Component
public class MyWebServerFactoryCustomizer implements WebServerFactoryCustomizer<ConfigurableServletWebServerFactory> {

	@Override
	public void customize(ConfigurableServletWebServerFactory server) {
		server.setPort(9000);
	}

}
```

`TomcatServletWebServerFactory`, and `JettyServletWebServerFactory` are dedicated variants of `ConfigurableServletWebServerFactory` that have additional customization setter methods for Tomcat, and Jetty respectively. The following example shows how to customize `TomcatServletWebServerFactory` that provides access to Tomcat-specific configuration options:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.web.servlet.embeddedcontainer.customizing.programmatic;

import java.time.Duration;

import org.springframework.boot.tomcat.servlet.TomcatServletWebServerFactory;
import org.springframework.boot.web.server.WebServerFactoryCustomizer;
import org.springframework.stereotype.Component;

@Component
public class MyTomcatWebServerFactoryCustomizer implements WebServerFactoryCustomizer<TomcatServletWebServerFactory> {

	@Override
	public void customize(TomcatServletWebServerFactory server) {
		server.addConnectorCustomizers((connector) -> connector.setAsyncTimeout(Duration.ofSeconds(20).toMillis()));
	}

}
```

## Customizing ConfigurableServletWebServerFactory Directly

For more advanced use cases that require you to extend from `ServletWebServerFactory`, you can expose a bean of such type yourself.

Setters are provided for many configuration options. Several protected method “hooks” are also provided should you need to do something more exotic. See the `ConfigurableServletWebServerFactory` API documentation for details.

> **Note:** Auto-configured customizers are still applied on your custom factory, so use that option carefully.

## Related topics

- [Graceful Shutdown](graceful-shutdown.md)
- [API Versioning](api-versioning.md)
