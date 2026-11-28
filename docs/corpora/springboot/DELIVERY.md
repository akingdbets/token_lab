# Spring Boot OpenWiki-only delivery

Verified 2026-11-29 (Asia/Seoul). This branch is `feature/springboot-openwiki`,
based on freshly fetched `origin/main` (`fabbe95c5c34ed59fd3cf0286c21d77c5971626c`).
Only the original OpenWiki build `14c382a` was cherry-picked. It has the same
parent as the current main, so no conflict resolution or dataset commit was needed.
The imported commit is amended only for these sharing/attribution notes and their
SOURCE.md hash in the isolated manifest. There are 134 changed files versus main.

## Corpus and provenance

- Official Spring Boot `v4.2.0`, source commit
  `3a36e91f4d92d2e5986092baf8fa1e4848098f01`.
- OpenWiki **0.7.0** native Codex host lifecycle; Asciidoctor.js 3.0.4 and
  Turndown 7.2.2 retain official English Reference prose and Java/config examples.
  No separate model API call. Exact original host checkpoint was not exposed.
- **49 topic pages + 1 quickstart + 10 indexes = 60 loaded Markdown documents**.
- **63,566 total tokens**, **61,706 non-index tokens**, `tiktoken:o200k_base`.
  Non-index min/P25/median/P75/max: 338 / 686.25 / 1,027 / 1,769.75 / 5,080.
- The 113 native output files (including 50 Claims files and control metadata)
  are byte-identical to `14c382a`. Only SOURCE.md attribution is extended.
- Original Apache-2.0 license is retained byte-for-byte; copyright comments
  remain in source examples. SOURCE.md links the license and describes adaptation.

## Fresh checks on the isolated branch

The retained corpus validator reports zero errors: 192 Claims, 260 evidence
records, 91 evidence source files, 95 raw-file hashes, 70 include/include-code
expansions, 67 Java blocks, 33 configuration examples, 634 inline identifiers,
three local heading anchors and 168 deduplicated internal navigation edges.
There are no broken internal Markdown page links or unclosed code fences.
Raw inputs match the pinned upstream checkout, with exact evidence range hashes.

Preparation was rerun into a new external temporary directory. The complete
units/provenance JSON is identical to the original input. The entire native
OpenWiki generation was rerun with installed versions checked against package.json;
finish status is complete. Fresh output validation also has zero errors. **All
60 Markdown bodies match** the frozen corpus; frontmatter timestamps, run IDs,
Claims IDs and the temporary input gitHead are naturally new. The committed
corpus was not replaced by this rebuild.

Full suite: **393 tests, zero failures/errors, one existing artifact skip**,
including all 14 Spring Boot preparation/source-selection tests. Offline mode and
socket.connect blocking prevented model/network requests during the suite.
The original build test log is retained as historical evidence; fresh counts and
checks are recorded in [delivery.json](delivery.json). No experiment was run.

One external application-properties appendix anchor depends on an Antora-generated
appendix and remains explicitly unbuilt. External HTTP destinations were not all
crawled. Java compilation and the full Antora build are outside this verification.
These limits do not create dangling links within the corpus.

## Use and reproduce

See [README.md](README.md#use-this-corpus-independently) to load the corpus with
OPENWIKI_DIR and TOKENIZER. Reading it does not require OpenWiki or a model API key.
See [the reproduction guide](../../../scripts/springboot_openwiki/README.md) for
fresh pinned upstream acquisition, macro expansion, native generation and validation.
The full upstream repository and temporary input archive are not committed;
the guide recreates the curated source and evidence paths from official sources.
Always export to the explicit Spring Boot manifest, never the shared FastAPI path.

The FastAPI/DuckDB/Kafka comparison in README is the historical original build
snapshot. The key methodological difference is this source-preserving Codex adapter
versus freely rewritten Claude host output; Spring Boot also has shorter, less
uniform pages. The same OpenWiki version, native indexes, provenance and Claims
conventions are retained.

## Scope and preservation

The branch diff is restricted to `data/openwiki/springboot-en/`, its independent
manifest, `docs/corpora/springboot/`, `scripts/springboot_openwiki/` and
`tests/test_springboot_preparation.py`. No Spring Boot evalset, scenario/Codex adapter,
human review CSV/HTML, ChatGPT/Claude audit, dataset correction or experiment result
is added. The full test log included by the original build is corpus-build evidence,
not an experiment result. No .env, keys, personal local paths or temporary folders
are added in the patch. Existing repository Git author metadata is unchanged.

The pre-existing root worktree's branch, HEAD, dirty status and tracked modified
file hashes remain unchanged. The separate multiturn worktree remains clean at
`d92aa4048011a61eebbcba2cbeb66ad261c5e905`. No dataset file there was edited.
