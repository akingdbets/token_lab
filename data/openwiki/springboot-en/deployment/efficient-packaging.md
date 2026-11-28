---
type: guide
title: "Efficient Deployments"
description: "Spring Boot Efficient Deployments: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","deployment"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-23b9f93ca0bc05189f9f8f6d
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/packaging/efficient.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Efficient Deployments

## Unpacking the Executable jar

You can run your application using the executable jar, but loading the classes from nested jars has a small startup cost. Depending on the size of the jar, running the application from an exploded structure is faster and recommended in production. Certain PaaS implementations may also choose to extract archives before they run. For example, Cloud Foundry operates this way.

Spring Boot supports extracting your application to a directory using different layouts. The default layout is the most efficient, and it is [AOT cache](https://docs.spring.io/spring-boot/4.2.0/reference/packaging/aot-cache.html#packaging.aot-cache.aot-cache) (and [CDS](https://docs.spring.io/spring-boot/4.2.0/reference/packaging/aot-cache.html#packaging.aot-cache.cds)) friendly.

In this layout, the libraries are extracted to a `lib/` folder, and the application jar contains the application classes and a manifest which references the libraries in the `lib/` folder.

To unpack the executable jar, run this command:

```shell
$ java -Djarmode=tools -jar my-app.jar extract
```

And then in production, you can run the extracted jar:

```shell
$ java -jar my-app/my-app.jar
```

After startup, you should not expect any differences in execution time between running an executable jar and running an extracted jar.

> **Note:** An executable war can be extracted in the same way. The result is a jar, for example `my-app/my-app.jar`, that is meant to be run with `java -jar`. Content from the root of the war, such as static files and JSPs from `src/main/webapp`, is moved to `META-INF/resources/` in the extracted jar.

> **Tip:** Run `java -Djarmode=tools -jar my-app.jar help extract` to see all possible options.

## Related topics

- [Dockerfiles](dockerfiles.md)
- [Testcontainers](../testing/testcontainers.md)
