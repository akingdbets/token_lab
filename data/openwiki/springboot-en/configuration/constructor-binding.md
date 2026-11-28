---
type: guide
title: "Constructor Binding"
description: "Spring Boot Constructor Binding: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","configuration"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-deacd1ecca3e4f7f16fc0899
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/features/external-config.adoc
  - id: openwiki-source-c312ec7ce47c60a2de984b86
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/features/externalconfig/typesafeconfigurationproperties/constructorbinding/defaultvalues/nonnull/MyProperties.java
  - id: openwiki-source-1ff95cc9b9338cb038ebb607
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/features/externalconfig/typesafeconfigurationproperties/constructorbinding/MyProperties.java
  - id: openwiki-source-3e7e3a9cf40c35e366b71ae6
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/features/externalconfig/typesafeconfigurationproperties/constructorbinding/primaryconstructor/MyProperties.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Constructor Binding

The example in the previous section can be rewritten in an immutable fashion as shown in the following example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.features.externalconfig.typesafeconfigurationproperties.constructorbinding;

import java.net.InetAddress;
import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties("my.service")
public class MyProperties {

	// @fold:on // fields...
	private final boolean enabled;

	private final InetAddress remoteAddress;

	private final Security security;

	// @fold:off

	public MyProperties(boolean enabled, InetAddress remoteAddress, Security security) {
		this.enabled = enabled;
		this.remoteAddress = remoteAddress;
		this.security = security;
	}

	// @fold:on // getters...
	public boolean isEnabled() {
		return this.enabled;
	}

	public InetAddress getRemoteAddress() {
		return this.remoteAddress;
	}

	public Security getSecurity() {
		return this.security;
	}
	// @fold:off

	public static class Security {

		// @fold:on // fields...
		private final String username;

		private final String password;

		private final List<String> roles;

		// @fold:off

		public Security(String username, String password, @DefaultValue("USER") List<String> roles) {
			this.username = username;
			this.password = password;
			this.roles = roles;
		}

		// @fold:on // getters...
		public String getUsername() {
			return this.username;
		}

		public String getPassword() {
			return this.password;
		}

		public List<String> getRoles() {
			return this.roles;
		}
		// @fold:off

	}

}
```

In this setup, the presence of a single parameterized constructor implies that constructor binding should be used. This means that the binder will find a constructor with the parameters that you wish to have bound. If your class has multiple constructors, the `@ConstructorBinding` annotation can be used to specify which constructor to use for constructor binding.

To opt-out of constructor binding for a class, the parameterized constructor must be annotated with `@Autowired` or made `private`. Kotlin developers can use an empty primary constructor to opt-out of constructor binding.

For example:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.features.externalconfig.typesafeconfigurationproperties.constructorbinding.primaryconstructor;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("my")
public class MyProperties {

	// @fold:on // fields...
	final MyBean myBean;

	private String name;

	// @fold:off

	@Autowired
	public MyProperties(MyBean myBean) {
		this.myBean = myBean;
	}

	// @fold:on // getters / setters...

	public String getName() {
		return this.name;
	}

	public void setName(String name) {
		this.name = name;
	}

	// @fold:off

}
```

Constructor binding can be used with records. Unless your record has multiple constructors, there is no need to use `@ConstructorBinding`.

Nested members of a constructor bound class (such as `Security` in the example above) will also be bound through their constructor.

> **Note:** To use constructor binding the class must be enabled using `@EnableConfigurationProperties` or configuration property scanning. You cannot use constructor binding with beans that are created by the regular Spring mechanisms (for example `@Component` beans, beans created by using `@Bean` methods or beans loaded by using `@Import`)

> **Note:** To use constructor binding the class must be compiled with `-parameters`. This will happen automatically if you use Spring Boot’s Gradle plugin or if you use Maven and `spring-boot-starter-parent`.

> **Note:** The use of `Optional` with `@ConfigurationProperties` is not recommended as it is primarily intended for use as a return type. As such, it is not well-suited to configuration property injection. If you do declare an `Optional` constructor-bound property and it has no value, an empty `Optional` will be bound.

> **Tip:** To use a reserved keyword in the name of a property, such as `my.service.import`, use the `@Name` annotation on the constructor parameter.

## @DefaultValue and Binding

Default values can be specified using `@DefaultValue` on constructor parameters and record components. Property placeholders in the annotation’s `String` value are replaced and the conversion service is applied to coerce it to the target type of a missing property.

In the `MyProperties` example above, you can see the nested `Security` class uses `@DefaultValue("USER")` for the `roles` parameter. This means that if `security` properties are defined, but `roles` is not, the default of `"USER"` will be bound.

For example, the following properties:

```yaml
my:
  service:
    enabled: true
    security:
      username: admin
```

Will be bound as `new MyProperties(true, null, new Security("admin", null, List.of("USER")))`

If the `security` property is not present at all, then the `Security` instance will be `null`.

For example, the following properties:

```yaml
my:
  service:
    enabled: true
```

Will be bound as `new MyProperties(true, null, null)`

> **Note:** You can define an empty `security` property if you want to trigger binding with fully default `Security` instance.
>
> For YAML, you can use the following syntax:
>
> ```yaml
> my:
>   service:
>     enabled: true
>     security: {}
> ```
>
> With `Properties` you can use:
>
> ```properties
> my.service.enabled=true
> my.service.security=
> ```
>
> Will be bound as `new MyProperties(true, null, new Security(null, null, List.of("USER")))`

If you want to always bind a non-null instance of `Security`, even when properties are missing, you can use an empty `@DefaultValue` annotation:

```java
	public MyProperties(boolean enabled, InetAddress remoteAddress, @DefaultValue Security security) {
		this.enabled = enabled;
		this.remoteAddress = remoteAddress;
		this.security = security;
	}
```

> **Tip:** When using Kotlin, you will need to declare the `username` and `password` parameters as nullable since they do not have default values

## Related topics

- [Enabling @ConfigurationProperties-annotated Types](enabling-properties.md)
- [JavaBean Properties Binding](java-bean-binding.md)
