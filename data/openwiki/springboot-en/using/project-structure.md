---
type: guide
title: "Structuring Your Code"
description: "Spring Boot Structuring Your Code: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","using"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-7c32e1b3843b88bf54c7fe02
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/using/structuring-your-code.adoc
  - id: openwiki-source-39b70b7d839a29fdc0f5b2e4
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/using/structuringyourcode/locatingthemainclass/MyApplication.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Structuring Your Code

Spring Boot does not require any specific code layout to work. However, there are some best practices that help.

> **Tip:** If you wish to enforce a structure based on domains, take a look at [Spring Modulith](https://spring.io/projects/spring-modulith#overview).

## Using the “default” Package

When a class does not include a `package` declaration, it is considered to be in the “default package”. The use of the “default package” is generally discouraged and should be avoided. It can cause particular problems for Spring Boot applications that use the `@ComponentScan`, `@ConfigurationPropertiesScan`, `@EntityScan`, or `@SpringBootApplication` annotations, since every class from every jar is read.

> **Tip:** We recommend that you follow Java’s recommended package naming conventions and use a reversed domain name (for example, `com.example.project`).

## Locating the Main Application Class

We generally recommend that you locate your main application class in a root package above other classes. The [`@SpringBootApplication` annotation](https://docs.spring.io/spring-boot/4.2.0/reference/using/using-the-springbootapplication-annotation.html) is often placed on your main class, and it implicitly defines a base “search package” for certain items. For example, if you are writing a JPA application, the package of the `@SpringBootApplication` annotated class is used to search for `@Entity` items. Using a root package also allows component scan to apply only on your project.

> **Tip:** If you do not want to use `@SpringBootApplication`, the `@EnableAutoConfiguration` and `@ComponentScan` annotations that it imports defines that behavior so you can also use those instead.

The following listing shows a typical layout:

```
com
 +- example
     +- myapplication
         +- MyApplication.java
         |
         +- customer
         |   +- Customer.java
         |   +- CustomerController.java
         |   +- CustomerService.java
         |   +- CustomerRepository.java
         |
         +- order
             +- Order.java
             +- OrderController.java
             +- OrderService.java
             +- OrderRepository.java
```

The `MyApplication.java` file would declare the `main` method, along with the basic `@SpringBootApplication`, as follows:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.using.structuringyourcode.locatingthemainclass;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class MyApplication {

	public static void main(String[] args) {
		SpringApplication.run(MyApplication.class, args);
	}

}
```

## Related topics

- [Configuration Classes](configuration-classes.md)
- [Writing the Code](../quickstart.md)
