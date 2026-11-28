---
type: guide
title: "Using Configuration Trees"
description: "Spring Boot Using Configuration Trees: documented behavior, configuration and source-backed examples from v4.2.0."
tags: ["spring-boot","configuration"]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-28T11:55:33.232Z
sources:
  - id: openwiki-source-deacd1ecca3e4f7f16fc0899
    resource: repo://upstream/documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/features/external-config.adoc
generated: { by: "codex", at: "2026-11-28T11:55:33.232Z" }
---

# Using Configuration Trees

Storing config values in environment variables has drawbacks, especially if the value is supposed to be kept secret.

As an alternative to environment variables, many cloud platforms now allow you to map configuration into mounted data volumes. For example, Kubernetes can volume mount both [`ConfigMaps`](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/#populate-a-volume-with-data-stored-in-a-configmap) and [`Secrets`](https://kubernetes.io/docs/concepts/configuration/secret/#using-secrets-as-files-from-a-pod).

There are two common volume mount patterns that can be used:

1.  A single file contains a complete set of properties (usually written as YAML).

2.  Multiple files are written to a directory tree, with the filename becoming the ‘key’ and the contents becoming the ‘value’.


For the first case, you can import the YAML or Properties file directly using `spring.config.import` as described [above](https://docs.spring.io/spring-boot/4.2.0/reference/features/external-config.html#features.external-config.files.importing). For the second case, you need to use the `configtree:` prefix so that Spring Boot knows it needs to expose all the files as properties.

As an example, let’s imagine that Kubernetes has mounted the following volume:

```
etc/
  config/
    myapp/
      username
      password
```

The contents of the `username` file would be a config value, and the contents of `password` would be a secret.

To import these properties, you can add the following to your `application.properties` or `application.yaml` file:

```yaml
spring:
  config:
    import: "optional:configtree:/etc/config/"
```

You can then access or inject `myapp.username` and `myapp.password` properties from the `Environment` in the usual way.

> **Tip:** The names of the folders and files under the config tree form the property name. In the above example, to access the properties as `username` and `password`, you can set `spring.config.import` to `optional:configtree:/etc/config/myapp`.

> **Note:** Filenames with dot notation are also correctly mapped. For example, in the above example, a file named `myapp.username` in `/etc/config` would result in a `myapp.username` property in the `Environment`.

> **Tip:** Configuration tree values can be bound to both string `String` and `byte[]` types depending on the contents expected.

If you have multiple config trees to import from the same parent folder you can use a wildcard shortcut. Any `configtree:` location that ends with `/*/` will import all immediate children as config trees. As with a non-wildcard import, the names of the folders and files under each config tree form the property name.

For example, given the following volume:

```
etc/
  config/
    dbconfig/
      db/
        username
        password
    mqconfig/
      mq/
        username
        password
```

You can use `configtree:/etc/config/*/` as the import location:

```yaml
spring:
  config:
    import: "optional:configtree:/etc/config/*/"
```

This will add `db.username`, `db.password`, `mq.username` and `mq.password` properties.

> **Note:** Directories loaded using a wildcard are sorted alphabetically. If you need a different order, then you should list each location as a separate import

Configuration trees can also be used for Docker secrets. When a Docker swarm service is granted access to a secret, the secret gets mounted into the container. For example, if a secret named `db.password` is mounted at location `/run/secrets/`, you can make `db.password` available to the Spring environment using the following:

```yaml
spring:
  config:
    import: "optional:configtree:/run/secrets/"
```

## Related topics

- [Property Placeholders](placeholders.md)
- [External Application Properties](config-files.md)
