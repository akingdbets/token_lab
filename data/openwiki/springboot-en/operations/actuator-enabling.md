---
type: guide
title: "Enabling Production-ready Features"
description: "Spring Boot Enabling Production-ready Features: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","operations"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-ed1720b25c729e676b7cb646
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/actuator/enabling.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Enabling Production-ready Features

The [`spring-boot-actuator`](https://github.com/spring-projects/spring-boot/tree/v4.2.0/module/spring-boot-actuator) module provides all of Spring Boot’s production-ready features. The recommended way to enable the features is to add a dependency on the `spring-boot-starter-actuator` starter.

Definition of Actuator

An actuator is a manufacturing term that refers to a mechanical device for moving or controlling something. Actuators can generate a large amount of motion from a small change.

To add the actuator to a Maven-based project, add the following starter dependency:

```xml
<dependencies>
	<dependency>
		<groupId>org.springframework.boot</groupId>
		<artifactId>spring-boot-starter-actuator</artifactId>
	</dependency>
</dependencies>
```

For Gradle, use the following declaration:

```gradle
dependencies {
	implementation 'org.springframework.boot:spring-boot-starter-actuator'
}
```

## Related topics

- [Writing the Code](../quickstart.md)
- [Cloud Native Buildpacks](../deployment/buildpacks.md)
