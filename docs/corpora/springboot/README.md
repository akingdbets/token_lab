# Spring Boot v4.2.0 corpus build

The independent English corpus is `data/openwiki/springboot-en/`. It contains
49 topic pages, one runnable Tutorial quickstart, ten native OpenWiki indexes,
and fifty native Claims sidecars. No multiturn scenarios or evaluation datasets
were generated. No existing FastAPI files were changed and no PR heads merged.

## Source and generator

- Official repository: https://github.com/spring-projects/spring-boot
- Annotated tag: `v4.2.0`, tag object `a8da8b4df7a2984b7a20dd750e3fb8a7259fee9c`.
- Peeled source commit: `3a36e91f4d92d2e5986092baf8fa1e4848098f01`.
- Selected input repository commit: `2aac475cc4de920d1e8da1780b759a37188046f4`.
- OpenWiki 0.7.0, Codex host integration. Metadata is actually produced by the
  native lifecycle, not copied from another corpus or constructed by our scripts.
- Host model: Codex (GPT-6 family; exact checkpoint ID is not exposed). Native
  model field: `host-agent/codex`. No Claude invocation or separate API model call.
- Final completion: `2026-11-28T11:55:35.038Z`.
- Rendering: Asciidoctor.js 3.0.4 → Turndown 7.2.2 / GFM 1.0.2. The pinned Spring
  extension source 1.0.0-alpha.18 was inspected to match macro behavior. Full
  Antora generated metadata is deliberately not substituted with invented data.

95 raw input files are retained byte-identically in the external input repository
(`upstream/`). Exact file SHA-256, original selected section line ranges, all
67 include-code/3 include expansions and exact Java snippet selections are in
[input-provenance.json](input-provenance.json). The official checkout and input
repository remain outside TokenLab under `/private/tmp/`. An ignored local
archive in `results/corpora/` preserves the curated input repository including
its Git history; [build-record.json](build-record.json) gives its SHA-256.
Only the generated corpus, scripts and small provenance/verification records
are committed; the full official repository is excluded.

## Comparison with the existing corpora

Historical comparison recorded during the original build (2026-11-28): PR #64 and #67 were inspected via their exact heads without merging. The open/unmerged labels below describe that snapshot, not a live PR status check:

| Corpus | Inspected ref | Non-index pages (incl. quickstart) | Indexes | Claims files | OpenWiki |
|---|---|---:|---:|---:|---|
| FastAPI | main `fabbe95c` | 50 | 16 | 50 | 0.7.0 |
| DuckDB [PR #64](https://github.com/akingdbets/token_lab/pull/64), open/unmerged | `eda7e1a19d4189785b81c4a0e2baf27aa8b18689` | 54 | 17 | 54 | 0.7.0 |
| Kafka [PR #67](https://github.com/akingdbets/token_lab/pull/67), open/unmerged | `451f4f66ed318a828d0ff427ac8c1cfccdf5f064` | 53 | 11 | 53 | 0.7.0 |
| Spring Boot | this branch | 50 | 10 | 50 | 0.7.0 |

All three prior corpora preserve complete native generated output before adding
SOURCE.md. DuckDB retains Jekyll configuration to interpret site variables;
Kafka retains `docs/generated/` HTML tables for its include-html shortcodes.
Spring Boot follows this source-preservation principle and explicitly resolves
AsciiDoc and Java tag selectors instead of changing file extensions. Unlike
prior Claude Code integrations, this run uses Codex and records that difference.
Kafka's user-reported Claude Opus 5.5 is not assumed for Spring Boot.

## Token statistics

Exact `tiktoken:o200k_base` counts over committed Markdown, including native
frontmatter and indexes. SOURCE.md, INSTRUCTIONS.md and hidden control files
are excluded, matching the existing `corpus.py` input selection. Quartiles use
linear interpolation. Complete per-document counts are in
[validation.json](validation.json) and the independent
`data/corpus_manifest.springboot-en.jsonl`.

| Metric | Spring Boot | FastAPI |
|---|---:|---:|
| Loaded Markdown documents | 60 | 66 |
| Non-index pages (incl. quickstart) | 50 | 50 |
| Total tokens (including indexes) | 63,566 | 98,098 |
| Non-index tokens | 61,706 | 94,709 |
| Non-index min / median / max | 338 / 1,027 / 5,080 | 1,108 / 1,935.5 / 2,668 |
| Non-index P25 / P75 | 686.25 / 1,769.75 | 1,557.25 / 2,210 |
| Non-index P90 / P95 | 1,948.7 / 2,237.1 | 2,411.5 / 2,586.1 |
| Non-index mean | 1,234.12 | 1,894.18 |

## Verification and limits

- All 113 native output files are byte-identical to the external generation
  directory. SOURCE.md is the sole post-copy addition. Native page/Claims
  hashes match; all JSON files parse; final OpenWiki finish status is complete.
- 192 substantive source-prose Claims, 260 evidence records, 91 distinct evidence
  files. Every evidence file/range and its native SHA-256 version was checked.
- All 95 raw-file hashes match both the staged files and the pinned checkout.
  All 70 expansions match exact original selected lines. Missing includes,
  unsupported selectors and malformed tags cause preparation to fail.
- 67 Java code blocks match original snippets, ignoring presentation indentation
  and blank lines only; text inside Java string values is retained. 33 source
  configuration listings (YAML/properties) match. 634 inline Javadoc identifiers,
  annotation names and documented configprop names survive rendering.
- No dangling Markdown page links; 168 deduplicated corpus navigation edges.
  All three local heading anchors were checked and rewritten to Markdown slugs.
  All code fences close. Source headings, admonitions and multiline table cells
  have been rendered to proper Markdown rather than embedded AsciiDoc directives.
- 90 source xref occurrences resolve to files in the pinned checkout. One target
  anchor belongs to the generated application-properties appendix and cannot be
  verified from checked-in AsciiDoc alone; it is left as a versioned official
  external link, with its unbuilt status recorded. This does not affect internal
  corpus links. External URLs were not all HTTP-crawled.
- 22 external Javadoc URL attributes retain their actual Java identifiers as
  inline code. 37 other dynamic external-library links point to pinned original
  source rather than guessed dependency API versions. All 59 decisions are logged.
- No unresolved include/include-code, javadoc or configprops directives remain.
  Java compilation and the complete Antora site build were not performed. The
  correctness claim is source fidelity, not independent runtime execution.
- The unmodified corpus loader reads all 60 Spring Boot documents using
  OPENWIKI_DIR. Its manifest is written with an explicit separate path.
  `data/corpus_manifest.jsonl` remains unchanged.
- Full documented project suite: **393 tests, zero failures/errors, one existing
  skip** (independent experiment dataset unavailable), including 14 preparation
  regression/safety tests. Network and LLM calls were blocked during tests.
  See [tests.log](tests.log). Final corpus validation reports zero errors.

## Readiness for multiturn v2

The corpus covers Controller/routing, request and response conversion, validation,
security, external configuration/profiles, dependency injection, test slices,
SQL/JPA/R2DBC, error handling, container deployment and operations. With 50
non-index pages and 61,706 content-page tokens, there is sufficient material to
begin designing multiturn v2 bundles and reference-grounded facts.

Spring Boot is shorter and less uniform than FastAPI: several focused topics
are below 700 tokens, while Testcontainers is 5,080. Matching eight pages per
bundle would not match difficulty or final-history size. The later scenario
stage should balance document token totals and coverage, verify at least 15k
final-history targets, and retain the existing dependency/recall/update and
user-fact rules. This step has not generated or selected an evaluation dataset.

## Files added

- `data/openwiki/springboot-en/`: 114 files (113 native output + SOURCE.md).
- `data/corpus_manifest.springboot-en.jsonl`: isolated loader manifest.
- `scripts/springboot_openwiki/`: source adapter, native lifecycle renderer,
  validator, and exact npm dependency manifest/lock.
- `tests/test_springboot_preparation.py`: 14 semantic source-preservation checks.
- `docs/corpora/springboot/`: this report, original license, build/input/output
  records, native generation logs, test log and machine-readable validation.

Reproduction instructions: [scripts/springboot_openwiki/README.md](../../../scripts/springboot_openwiki/README.md).

## Use this corpus independently

This OpenWiki-only branch is `feature/springboot-openwiki`, based on `origin/main`.
It imports only the corpus build from `14c382a`; no later Spring Boot scenario,
Codex adapter, review sheet or experiment artifact is included. The native content
and Claims are unchanged. See [DELIVERY.md](DELIVERY.md) for fresh reproduction
and validation on this branch.

With the project Python dependencies installed, load it without writing any manifest:

```bash
OPENWIKI_DIR=data/openwiki/springboot-en TOKENIZER=tiktoken:o200k_base \
PYTHONPATH=src python - <<'PY'
from corpus import load_corpus
corpus = load_corpus()
print(len(corpus))  # 60: 49 topics, quickstart, 10 indexes
print(corpus.get("web/controllers-and-routing.md").text)
PY
```

Use the explicit Spring Boot manifest path if exporting metadata. Do not use the
default `src/corpus.py --stats` command: it writes the shared FastAPI manifest.

The upstream license is retained byte-for-byte in
[UPSTREAM-LICENSE.txt](UPSTREAM-LICENSE.txt); source attribution and adaptation
notes are in [SOURCE.md](../../../data/openwiki/springboot-en/SOURCE.md).
