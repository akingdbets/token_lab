# OpenWiki Instructions

Write every wiki page in English.
The readers of this wiki are developers and operators who use Apache Kafka, from beginners to advanced users.
Prioritize usage over internal implementation. Cover every topic of the user documentation
(docs) as pages: introduction and quickstart, core concepts (topics, partitions, offsets, replication),
producers and consumers (including consumer groups and the rebalance protocols), the Admin and other APIs,
delivery semantics, idempotence and transactions, storage, retention and log compaction, tiered storage,
KRaft cluster setup and migration from ZooKeeper, basic operations and CLI tools, monitoring,
geo-replication with MirrorMaker, security (SSL, SASL, ACLs), Kafka Connect, and Kafka Streams.
Each page must include example code, CLI commands or configuration (from docs, examples and config)
and exact class, method, tool, config and parameter names.
Keep the exact default values and version notes that the documentation states.
The configuration reference pages in docs/configuration include generated tables through
include-html shortcodes; those tables are in docs/generated (for example producer_config.html).
Cover internals only as far as users need them.
