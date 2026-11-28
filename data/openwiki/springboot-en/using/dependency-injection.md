---
type: guide
title: "Spring Beans and Dependency Injection"
description: "Spring Boot Spring Beans and Dependency Injection: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","using"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-ed849d375eeae9ee0e1d0628
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/using/spring-beans-and-dependency-injection.adoc
  - id: openwiki-source-b8b55822c7cc6b617cbec7b4
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/using/springbeansanddependencyinjection/multipleconstructors/MyAccountService.java
  - id: openwiki-source-e87aa111530302495e962ac1
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/using/springbeansanddependencyinjection/singleconstructor/MyAccountService.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Spring Beans and Dependency Injection

You are free to use any of the standard Spring Framework techniques to define your beans and their injected dependencies. We generally recommend using constructor injection to wire up dependencies and `@ComponentScan` to find beans.

If you structure your code as suggested above (locating your application class in a top package), you can add `@ComponentScan` without any arguments or use the `@SpringBootApplication` annotation which implicitly includes it. All of your application components (`@Component`, `@Service`, `@Repository`, `@Controller`, and others) are automatically registered as Spring Beans.

The following example shows a `@Service` Bean that uses constructor injection to obtain a required `RiskAssessor` bean:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.using.springbeansanddependencyinjection.singleconstructor;

import org.springframework.stereotype.Service;

@Service
public class MyAccountService implements AccountService {

	@SuppressWarnings("unused")
	private final RiskAssessor riskAssessor;

	public MyAccountService(RiskAssessor riskAssessor) {
		this.riskAssessor = riskAssessor;
	}

	// ...

}
```

If a bean has more than one constructor, you will need to mark the one you want Spring to use with `@Autowired`:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.using.springbeansanddependencyinjection.multipleconstructors;

import java.io.PrintStream;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class MyAccountService implements AccountService {

	@SuppressWarnings("unused")
	private final RiskAssessor riskAssessor;

	@SuppressWarnings("unused")
	private final PrintStream out;

	@Autowired
	public MyAccountService(RiskAssessor riskAssessor) {
		this.riskAssessor = riskAssessor;
		this.out = System.out;
	}

	public MyAccountService(RiskAssessor riskAssessor, PrintStream out) {
		this.riskAssessor = riskAssessor;
		this.out = out;
	}

	// ...

}
```

> **Tip:** Notice how using constructor injection lets the `riskAssessor` field be marked as `final`, indicating that it cannot be subsequently changed.

## Related topics

- [Using the @SpringBootApplication Annotation](application-annotation.md)
- [Auto-configuration](auto-configuration.md)
