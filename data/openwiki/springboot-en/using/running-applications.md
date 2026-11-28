---
type: guide
title: "Running Your Application"
description: "Spring Boot Running Your Application: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","using"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-489b8580e15eb05a965b4c53
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/using/running-your-application.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Running Your Application

One of the biggest advantages of packaging your application as a jar and using an embedded HTTP server is that you can run your application as you would any other. The same applies to debugging Spring Boot applications. You do not need any special IDE plugins or extensions.

> **Note:** The options below are best suited for running an application locally for development. For production deployment, see [using/packaging-for-production.adoc](https://docs.spring.io/spring-boot/4.2.0/reference/using/packaging-for-production.html).

> **Note:** This section only covers jar-based packaging. If you choose to package your application as a war file, see your server and IDE documentation.

## Running From an IDE

You can run a Spring Boot application from your IDE as a Java application. However, you first need to import your project. Import steps vary depending on your IDE and build system. Most IDEs can import Maven projects directly. For example, Eclipse users can select `Import…​` → `Existing Maven Projects` from the `File` menu.

If you cannot directly import your project into your IDE, you may be able to generate IDE metadata by using a build plugin. Maven includes plugins for [Eclipse](https://maven.apache.org/plugins/maven-eclipse-plugin/) and [IntelliJ IDEA](https://maven.apache.org/plugins/maven-idea-plugin/). Gradle offers plugins for [various IDEs](https://docs.gradle.org/current/userguide/userguide.html).

> **Tip:** If you accidentally run a web application twice, you see a “Port already in use” error. Spring Tools users can use the `Relaunch` button rather than the `Run` button to ensure that any existing instance is closed.

## Running as a Packaged Application

If you use the Spring Boot Maven or Gradle plugins to create an executable jar, you can run your application using `java -jar`, as shown in the following example:

```shell
$ java -jar target/myapplication-0.0.1-SNAPSHOT.jar
```

It is also possible to run a packaged application with remote debugging support enabled. Doing so lets you attach a debugger to your packaged application, as shown in the following example:

```shell
$ java -agentlib:jdwp=server=y,transport=dt_socket,address=8000,suspend=n \
       -jar target/myapplication-0.0.1-SNAPSHOT.jar
```

## Using the Maven Plugin

The Spring Boot Maven plugin includes a `run` goal that can be used to quickly compile and run your application. Applications run in an exploded form, as they do in your IDE. The following example shows a typical Maven command to run a Spring Boot application:

```shell
$ mvn spring-boot:run
```

You might also want to use the `MAVEN_OPTS` operating system environment variable, as shown in the following example:

```shell
$ export MAVEN_OPTS=-Xmx1024m
```

## Using the Gradle Plugin

The Spring Boot Gradle plugin also includes a `bootRun` task that can be used to run your application in an exploded form. The `bootRun` task is added whenever you apply the `org.springframework.boot` and `java` plugins and is shown in the following example:

```shell
$ gradle bootRun
```

You might also want to use the `JAVA_OPTS` operating system environment variable, as shown in the following example:

```shell
$ export JAVA_OPTS=-Xmx1024m
```

## Hot Swapping

Since Spring Boot applications are plain Java applications, JVM hot-swapping should work out of the box. JVM hot swapping is somewhat limited with the bytecode that it can replace. For a more complete solution, [JRebel](https://www.jrebel.com/products/jrebel) can be used.

The `spring-boot-devtools` module also includes support for quick application restarts. See the [hotswapping.adoc](https://docs.spring.io/spring-boot/4.2.0/how-to/hotswapping.html) section in “How-to Guides” for details.

## Related topics

- [Packaging Your Application for Production](production-packaging.md)
- [Using the @SpringBootApplication Annotation](application-annotation.md)
