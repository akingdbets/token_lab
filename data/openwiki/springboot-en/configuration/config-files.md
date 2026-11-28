---
type: guide
title: "External Application Properties"
description: "Spring Boot External Application Properties: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","configuration"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-deacd1ecca3e4f7f16fc0899
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/features/external-config.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# External Application Properties

Spring Boot will automatically find and load `application.properties` and `application.yaml` files from the following locations when your application starts:

1.  From the classpath

    1.  The classpath root

    2.  The classpath `/config` package


2.  From the current directory

    1.  The current directory

    2.  The `config/` subdirectory in the current directory

    3.  Immediate child directories of the `config/` subdirectory



The list is ordered by precedence (with values from lower items overriding earlier ones). Documents from the loaded files are added as `PropertySource` instances to the Spring `Environment`.

If you do not like `application` as the configuration file name, you can switch to another file name by specifying a `spring.config.name` environment property. For example, to look for `myproject.properties` and `myproject.yaml` files you can run your application as follows:

```shell
$ java -jar myproject.jar --spring.config.name=myproject
```

You can also refer to an explicit location by using the `spring.config.location` environment property. This property accepts a comma-separated list of one or more locations to check.

The following example shows how to specify two distinct files:

```shell
$ java -jar myproject.jar --spring.config.location=\
	optional:classpath:/default.properties,\
	optional:classpath:/override.properties
```

> **Tip:** Use the prefix `optional:` if the [locations are optional](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.optional-prefix) and you do not mind if they do not exist.

> **Warning:** `spring.config.name`, `spring.config.location`, and `spring.config.additional-location` are used very early to determine which files have to be loaded. They must be defined as an environment property (typically an OS environment variable, a system property, or a command-line argument).

If `spring.config.location` contains directories (as opposed to files), they should end in `/`. At runtime they will be appended with the names generated from `spring.config.name` before being loaded. Files specified in `spring.config.location` are imported directly.

> **Note:** Both directory and file location values are also expanded to check for [profile-specific files](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.profile-specific). For example, if you have a `spring.config.location` of `classpath:myconfig.properties`, you will also find appropriate `classpath:myconfig-<profile>.properties` files are loaded.

In most situations, each `spring.config.location` item you add will reference a single file or directory. Locations are processed in the order that they are defined and later ones can override the values of earlier ones.

If you have a complex location setup, and you use profile-specific configuration files, you may need to provide further hints so that Spring Boot knows how they should be grouped. A location group is a collection of locations that are all considered at the same level. For example, you might want to group all classpath locations, then all external locations. Items within a location group should be separated with `;`. See the example in the [features/external-config.adoc](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.profile-specific) section for more details.

Locations configured by using `spring.config.location` replace the default locations. For example, if `spring.config.location` is configured with the value `optional:classpath:/custom-config/,optional:file:./custom-config/`, the complete set of locations considered is:

1.  `optional:classpath:custom-config/`

2.  `optional:file:./custom-config/`


If you prefer to add additional locations, rather than replacing them, you can use `spring.config.additional-location`. Properties loaded from additional locations can override those in the default locations. For example, if `spring.config.additional-location` is configured with the value `optional:classpath:/custom-config/,optional:file:./custom-config/`, the complete set of locations considered is:

1.  `optional:classpath:/;optional:classpath:/config/`

2.  `optional:file:./;optional:file:./config/;optional:file:./config/*/`

3.  `optional:classpath:custom-config/`

4.  `optional:file:./custom-config/`


This search ordering lets you specify default values in one configuration file and then selectively override those values in another. You can provide default values for your application in `application.properties` (or whatever other basename you choose with `spring.config.name`) in one of the default locations. These default values can then be overridden at runtime with a different file located in one of the custom locations.

## Related topics

- [Using Configuration Trees](imports-and-configtrees.md)
- [Externalized Configuration](property-precedence.md)
