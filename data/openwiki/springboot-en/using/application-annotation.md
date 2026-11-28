---
type: guide
title: "Using the @SpringBootApplication Annotation"
description: "Spring Boot Using the @SpringBootApplication Annotation: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","using"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-00b828a79c03242951b9d05c
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/using/using-the-springbootapplication-annotation.adoc
  - id: openwiki-source-edaac55cd2ac367cffd15c0a
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/using/usingthespringbootapplicationannotation/individualannotations/MyApplication.java
  - id: openwiki-source-3c54528a4adb0c2544a03193
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/using/usingthespringbootapplicationannotation/springapplication/MyApplication.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Using the @SpringBootApplication Annotation

Many Spring Boot developers like their apps to use auto-configuration, component scan and be able to define extra configuration on their "application class". A single `@SpringBootApplication` annotation can be used to enable those three features, that is:

-   `@EnableAutoConfiguration`: enable [Spring Boot’s auto-configuration mechanism](https://docs.spring.io/spring-boot/4.2.0/reference/using/auto-configuration.html)

-   `@ComponentScan`: enable `@Component` scan on the package where the application is located (see [the best practices](https://docs.spring.io/spring-boot/4.2.0/reference/using/structuring-your-code.html))

-   `@SpringBootConfiguration`: enable registration of extra beans in the context or the import of additional configuration classes. An alternative to Spring’s standard `@Configuration` that aids [configuration detection](https://docs.spring.io/spring-boot/4.2.0/reference/testing/spring-boot-applications.html#testing.spring-boot-applications.detecting-configuration) in your integration tests.


```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.using.usingthespringbootapplicationannotation.springapplication;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

// Same as @SpringBootConfiguration @EnableAutoConfiguration @ComponentScan
@SpringBootApplication
public class MyApplication {

	public static void main(String[] args) {
		SpringApplication.run(MyApplication.class, args);
	}

}
```

> **Note:** `@SpringBootApplication` also provides aliases to customize the attributes of `@EnableAutoConfiguration` and `@ComponentScan`.

> **Note:** None of these features are mandatory and you may choose to replace this single annotation by any of the features that it enables. For instance, you may not want to use component scan or configuration properties scan in your application:
>
> ```java
> /*
>  * Copyright 2012-present the original author or authors.
>  */
>
> package org.springframework.boot.docs.using.usingthespringbootapplicationannotation.individualannotations;
>
> import org.springframework.boot.SpringApplication;
> import org.springframework.boot.SpringBootConfiguration;
> import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
> import org.springframework.context.annotation.Import;
>
> @SpringBootConfiguration(proxyBeanMethods = false)
> @EnableAutoConfiguration
> @Import({ SomeConfiguration.class, AnotherConfiguration.class })
> public class MyApplication {
>
> 	public static void main(String[] args) {
> 		SpringApplication.run(MyApplication.class, args);
> 	}
>
> }
> ```
>
> In this example, `MyApplication` is just like any other Spring Boot application except that `@Component`\-annotated classes and `@ConfigurationProperties`\-annotated classes are not detected automatically and the user-defined beans are imported explicitly (see `@Import`).

## Related topics

- [Running Your Application](running-applications.md)
- [Spring Beans and Dependency Injection](dependency-injection.md)
