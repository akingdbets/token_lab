---
type: guide
title: "Writing the Code"
description: "Spring Boot Writing the Code: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","quickstart"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-705947f18f1cf2fe396303f5
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/tutorial/pages/first-application/index.adoc
  - id: openwiki-source-f8f1c77c6388103889ff97f1
    resource: repo://upstream/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/gettingstarted/firstapplication/code/MyApplication.java
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Writing the Code

To finish our application, we need to create a single Java file. By default, Maven and Gradle compile sources from `src/main/java`, so you need to create that directory structure and then add a file named `src/main/java/com/example/MyApplication.java` to contain the following code:

```java
/*
 * Copyright 2012-present the original author or authors.
 */

package org.springframework.boot.docs.gettingstarted.firstapplication.code;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@SpringBootApplication
public class MyApplication {

	@RequestMapping("/")
	String home() {
		return "Hello World!";
	}

	public static void main(String[] args) {
		SpringApplication.run(MyApplication.class, args);
	}

}
```

Although there is not much code here, quite a lot is going on. We step through the important parts in the next few sections.

## The @RestController and @RequestMapping Annotations

The first annotation on our `MyApplication` class is `@RestController`. This is known as a _stereotype_ annotation. It provides hints for people reading the code and for Spring that the class plays a specific role. In this case, our class is a web `@Controller`, so Spring considers it when handling incoming web requests.

The `@RequestMapping` annotation provides “routing” information. It tells Spring that any HTTP request with the `/` path should be mapped to the `home` method. The `@RestController` annotation tells Spring to render the resulting string directly back to the caller.

> **Tip:** The `@RestController` and `@RequestMapping` annotations are Spring MVC annotations (they are not specific to Spring Boot). See the [MVC section](https://github.com/spring-projects/spring-boot/blob/3a36e91f4d92d2e5986092baf8fa1e4848098f01/documentation/spring-boot-docs/src/docs/antora/modules/tutorial/pages/first-application/index.adoc#L272) in the Spring Reference Documentation for more details.

## The @SpringBootApplication Annotation

The second class-level annotation is `@SpringBootApplication`. This annotation is known as a _meta-annotation_, it combines `@SpringBootConfiguration`, `@EnableAutoConfiguration` and `@ComponentScan`.

Of those, the annotation we’re most interested in here is `@EnableAutoConfiguration`. `@EnableAutoConfiguration` tells Spring Boot to “guess” how you want to configure Spring, based on the jar dependencies that you have added. Since `spring-boot-starter-webmvc` added Tomcat and Spring MVC, the auto-configuration assumes that you are developing a web application and sets up Spring accordingly.

Starters and Auto-configuration

Auto-configuration is designed to work well with starters, but the two concepts are not directly tied. You are free to pick and choose jar dependencies outside of the starters. Spring Boot still does its best to auto-configure your application.

## The “main” Method

The final part of our application is the `main` method. This is a standard method that follows the Java convention for an application entry point. Our main method delegates to Spring Boot’s `SpringApplication` class by calling `run`. `SpringApplication` bootstraps our application, starting Spring, which, in turn, starts the auto-configured Tomcat web server. We need to pass `MyApplication.class` as an argument to the `run` method to tell `SpringApplication` which is the primary Spring component. The `args` array is also passed through to expose any command-line arguments.

## Find a task

- [Controller and request/response handling](web/controllers-and-routing.md)
- [Validation](validation/method-validation.md)
- [Security](security/web-security.md)
- [External configuration](configuration/property-precedence.md)
- [Dependency injection](using/dependency-injection.md)
- [Testing](testing/test-foundations.md)
- [Database access](data/datasources.md)
- [Error handling](web/error-handling.md)
- [Deployment](deployment/dockerfiles.md)
- [Operations](operations/actuator-enabling.md)

## Related topics

- [Structuring Your Code](using/project-structure.md)
- [Enabling Production-ready Features](operations/actuator-enabling.md)
