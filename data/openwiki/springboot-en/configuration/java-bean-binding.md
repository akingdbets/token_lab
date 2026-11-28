---
type: guide
title: "JavaBean Properties Binding"
description: "Spring Boot JavaBean Properties Binding: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","configuration"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-deacd1ecca3e4f7f16fc0899
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/features/external-config.adoc
  - id: openwiki-source-a064bebbb00bd2bc35b81e8a
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/features/externalconfig/typesafeconfigurationproperties/javabeanbinding/MyProperties.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# JavaBean Properties Binding

It is possible to bind a bean declaring standard JavaBean properties as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.features.externalconfig.typesafeconfigurationproperties.javabeanbinding;

import java.net.InetAddress;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("my.service")
public class MyProperties {

	private boolean enabled;

	private InetAddress remoteAddress;

	private final Security security = new Security();

	// @fold:on // getters / setters...
	public boolean isEnabled() {
		return this.enabled;
	}

	public void setEnabled(boolean enabled) {
		this.enabled = enabled;
	}

	public InetAddress getRemoteAddress() {
		return this.remoteAddress;
	}

	public void setRemoteAddress(InetAddress remoteAddress) {
		this.remoteAddress = remoteAddress;
	}

	public Security getSecurity() {
		return this.security;
	}
	// @fold:off

	public static class Security {

		private String username;

		private String password;

		private List<String> roles = new ArrayList<>(Collections.singleton("USER"));

		// @fold:on // getters / setters...
		public String getUsername() {
			return this.username;
		}

		public void setUsername(String username) {
			this.username = username;
		}

		public String getPassword() {
			return this.password;
		}

		public void setPassword(String password) {
			this.password = password;
		}

		public List<String> getRoles() {
			return this.roles;
		}

		public void setRoles(List<String> roles) {
			this.roles = roles;
		}
		// @fold:off

	}

}
```

The preceding POJO defines the following properties:

-   `my.service.enabled`, with a value of `false` by default.

-   `my.service.remote-address`, with a type that can be coerced from `String`.

-   `my.service.security.username`, with a nested "security" object whose name is determined by the name of the property. In particular, the type is not used at all there and could have been `SecurityProperties`.

-   `my.service.security.password`.

-   `my.service.security.roles`, with a collection of `String` that defaults to `USER`.


> **Tip:** To use a reserved keyword in the name of a property, such as `my.service.import`, use the `@Name` annotation on the property’s field.

> **Note:** The properties that map to `@ConfigurationProperties` classes available in Spring Boot, which are configured through properties files, YAML files, environment variables, and other mechanisms, are public API but the accessors (getters/setters) of the class itself are not meant to be used directly.

> **Note:** Such arrangement relies on a default empty constructor and getters and setters are usually mandatory, since binding is through standard Java Beans property descriptors, just like in Spring MVC. A setter may be omitted in the following cases:
>
> -   Pre-initialized Maps and Collections, as long as they are initialized with a mutable implementation (like the `roles` field in the preceding example).
>
> -   Pre-initialized nested POJOs (like the `Security` field in the preceding example). If you want the binder to create the instance on the fly by using its default constructor, you need a setter.
>
>
> Some people use Project Lombok to add getters and setters automatically. Make sure that Lombok does not generate any particular constructor for such a type, as it is used automatically by the container to instantiate the object.
>
> Finally, only standard Java Bean properties are considered and binding on static properties is not supported.

## Related topics

- [Constructor Binding](constructor-binding.md)
- [Working With YAML](yaml.md)
