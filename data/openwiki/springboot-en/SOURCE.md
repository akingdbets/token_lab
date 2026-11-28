# SOURCE — Spring Boot OpenWiki (English)

Frozen corpus for external generalization experiments. Existing FastAPI inputs, datasets and results are unchanged.

| 항목 | 값 |
|---|---|
| OpenWiki | `openwiki` 0.7.0 (npm; exact package lock retained) |
| 생성 방식 | OpenWiki Codex host-agent lifecycle: begin → submit_plan → next_page/write/submit_page → finish. Source-preserving English Reference edition, parsed with Asciidoctor.js 3.0.4 then Turndown 7.2.2; no separate model API calls. |
| 생성 모델 | Codex host agent (GPT-6 family; exact checkpoint ID is not exposed). Native metadata records `host-agent/codex`, producer `codex`; not Claude. |
| 생성 일시 | 2026-11-28T11:55:35.038Z (2026-11-28 20:55:35 KST); native `command: init`, `status: complete`. |
| 언어 | en |
| 공식 원본 | https://github.com/spring-projects/spring-boot |
| 공식 원본 버전 | `v4.2.0` (annotated tag object `a8da8b4df7a2984b7a20dd750e3fb8a7259fee9c`) |
| 입력 Spring Boot 커밋 | `3a36e91f4d92d2e5986092baf8fa1e4848098f01` (peeled tag / checkout HEAD) |
| 복사본 저장소 커밋 | `2aac475cc4de920d1e8da1780b759a37188046f4` (the separate, curated input repository; native gitHead) |
| 입력 범위 | 49 selected Reference units and one Tutorial quickstart; 95 upstream files including AsciiDoc, Java examples, referenced assets, Antora attributes/package metadata, gradle.properties and LICENSE.txt. Exact paths, original lines and SHA-256 in `docs/corpora/springboot/input-provenance.json`. |
| 문서 원본 경로 | `documentation/spring-boot-docs/src/docs/antora/modules/reference/pages/` and `modules/tutorial/pages/first-application/index.adoc`; Java: `documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/`. |
| 내용 | 49 topic pages + quickstart = 50 non-index pages; 10 generated indexes; 50 `.claims` sidecars. |

## Input preservation and AsciiDoc handling

The unmodified official checkout is `/private/tmp/tokenlab-springboot-v4.2.0`.
The independent input repository is `/private/tmp/tokenlab-springboot-input`:
`upstream/` holds byte-identical original files; `prepared/` holds explicitly
selected and expanded AsciiDoc. `repo://upstream/...` evidence resolves against
that input repository, not TokenLab. No full upstream repository is committed.
An ignored local input archive is kept at
`results/corpora/springboot-v4.2.0-input.tar.gz`; its hash is in the build record.

`prepare.py` resolves section-dependent include-code paths and exact Java tag/line
selections. All 67 include-code and 3 include directives in the selected scope
are expanded and recorded; missing files, tags or unsupported selectors fail.
The renderer parses AsciiDoc headings, lists, tables, admonitions and source
blocks; this is not an extension rename. configprops YAML is retained as YAML,
without manufacturing a Properties tab or a generated metadata/default table.
Javadoc annotations and configprop names are rendered as exact code identifiers.

Kotlin examples, generated starter/property appendices, runtime log-output
partials and unselected Reference sections are outside this corpus scope.
The full Antora site and Java projects were not built. Dynamic external-library
URL attributes require Antora's generated catalog; 59 such occurrences are recorded: Javadoc identifiers are retained without a guessed
URL, and other unresolved external links point to the pinned original AsciiDoc. Xrefs to
other Spring Boot pages use explicit versioned official Reference URLs.

## Output preservation and verification

All 113 native OpenWiki output files were copied byte-for-byte, including
INSTRUCTIONS.md, quickstart, indexes, `.claims`, `.page-manifest.json` and
`.last-update.json`. This SOURCE.md is the only file added after the copy.
Native control files were never synthesized or hand-edited.

The retained generator deterministically selects source prose and code under
Codex's authored topic plan, and submits substantive original prose as Claims.
OpenWiki owns Claim IDs, evidence hashes, indexes and completion metadata.
This differs from the freely rewritten Claude host output used for FastAPI,
DuckDB and Kafka; it preserves the official wording and code to minimize
unsupported additions. See the comparison and experiment implications in
`docs/corpora/springboot/README.md`.

Validation and reproduction: `scripts/springboot_openwiki/README.md`.
The independent manifest is `data/corpus_manifest.springboot-en.jsonl`.
Do not run `python src/corpus.py --stats` for this corpus: its default output
would overwrite the existing FastAPI manifest. The dedicated validator loads
`corpus.py` unchanged and calls `write_manifest` with the explicit separate path.

## License and attribution

Source documentation and Java examples are derived from the official Spring Boot
repository under the Apache License, Version 2.0. The original license is retained
in [UPSTREAM-LICENSE.txt](../../../docs/corpora/springboot/UPSTREAM-LICENSE.txt)
and in the separately prepared `upstream/LICENSE.txt` input. Existing copyright
comments in code examples are preserved. The Markdown conversion is an adaptation;
its scripts and exact source ranges are recorded in the build provenance. Native
OpenWiki Claims/control metadata and content pages have not been hand-edited.
