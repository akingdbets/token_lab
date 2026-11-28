---
type: guide
title: "Cloud Native Buildpacks"
description: "Spring Boot Cloud Native Buildpacks: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","deployment"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-41e76a5c72f27e7190beee4c
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/packaging/container-images/cloud-native-buildpacks.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Cloud Native Buildpacks

Docker images can be built directly from your Maven or Gradle plugin using [Cloud Native Buildpacks](https://buildpacks.io). If you’ve ever used an application platform such as Cloud Foundry or Heroku then you’ve probably used a buildpack. Buildpacks are the part of the platform that takes your application and converts it into something that the platform can actually run. For example, Cloud Foundry’s Java buildpack will notice that you’re pushing a `.jar` file and automatically add a relevant JRE.

With Cloud Native Buildpacks, you can create Docker compatible images that you can run anywhere. Spring Boot includes buildpack support directly for both Maven and Gradle. This means you can just type a single command and quickly get a sensible image into your locally running Docker daemon.

See the individual plugin documentation on how to use buildpacks with [Maven](https://docs.spring.io/spring-boot/4.2.0/maven-plugin/build-image.html#build-image) and [Gradle](https://docs.spring.io/spring-boot/4.2.0/gradle-plugin/packaging-oci-image.html).

> **Note:** The [Paketo Spring Boot buildpack](https://github.com/paketo-buildpacks/spring-boot) supports the `layers.idx` file, so any [layer customization](https://docs.spring.io/spring-boot/4.2.0/reference/packaging/container-images/efficient-images.html#packaging.container-images.efficient-images.layering) that is applied to it will be reflected in the image created by the buildpacks.

> **Note:** In order to achieve reproducible builds and container image caching, buildpacks can manipulate the application resources metadata (such as the file "last modified" information). You should ensure that your application does not rely on that metadata at runtime. Spring Boot can use that information when serving static resources, but this can be disabled with `spring.web.resources.cache.use-last-modified`.

## Related topics

- [Enabling Production-ready Features](../operations/actuator-enabling.md)
- [Dockerfiles](dockerfiles.md)
