# Reproduce the Spring Boot corpus

Run from the `feature/springboot-openwiki` worktree (or the repository checkout after merge). These scripts only prepare
Spring Boot sources, generate a separate wiki and write its separate manifest.
They do not modify FastAPI, scenario generation or dataset files.

The retained output is a source-preserving English Reference edition. Codex
chooses the topic taxonomy and macro/rendering policy; a deterministic adapter
retains official prose and exact source examples instead of asking an additional
model to paraphrase them. OpenWiki 0.7.0 owns Claims, IDs, evidence versions,
indexes, page provenance, manifest hashes and completion metadata.

The current session does not dynamically install new MCP tools. `generate.mjs`
therefore invokes OpenWiki's own `HostSessionManager` (the same implementation
behind its MCP tools) through the pinned package. It follows begin → submitPlan →
nextPage → write assigned page → submitPage → finish, one page at a time. No
OpenWiki control file is authored by these scripts and no model API is called.

## Fresh tools and source

Use fresh temporary paths to keep the frozen corpus and retained input intact:

```bash
BOOT_SOURCE=/private/tmp/springboot-420-rebuild-source
BOOT_INPUT=/private/tmp/springboot-420-rebuild-input
BOOT_TOOLS=/private/tmp/springboot-420-rebuild-tools
mkdir -p "$BOOT_TOOLS"
cp scripts/springboot_openwiki/package.json scripts/springboot_openwiki/package-lock.json "$BOOT_TOOLS/"
npm ci --prefix "$BOOT_TOOLS" --ignore-scripts

git clone --depth 1 --single-branch --branch v4.2.0 \
  https://github.com/spring-projects/spring-boot.git "$BOOT_SOURCE"
git -C "$BOOT_SOURCE" rev-parse 'v4.2.0^{}'
# Must be 3a36e91f4d92d2e5986092baf8fa1e4848098f01
python3 scripts/springboot_openwiki/prepare.py --source "$BOOT_SOURCE" --output "$BOOT_INPUT"
```

`prepare.py` refuses another HEAD, modified tracked upstream files, output nested
inside upstream, absent includes, unknown selectors and unbalanced/missing tags.
It preserves raw input bytes under `upstream/` and expands only explicit selected
sections into `prepared/*.adoc`. `units.json` records source lines and hashes,
all code selectors and exact snippet text. Java example paths derive from the
enclosing section ID, not simply the page path or any inline anchor.

## Freeze the independent input and generate

```bash
mkdir -p "$BOOT_INPUT/openwiki"
cp data/openwiki/springboot-en/INSTRUCTIONS.md "$BOOT_INPUT/openwiki/"
printf '%s\n' 'openwiki/' 'generation-log.json' > "$BOOT_INPUT/.gitignore"
git -C "$BOOT_INPUT" init
git -C "$BOOT_INPUT" add .gitignore upstream prepared units.json
git -C "$BOOT_INPUT" commit -m 'Stage pinned Spring Boot Reference input'
node scripts/springboot_openwiki/generate.mjs "$BOOT_INPUT" "$BOOT_TOOLS/node_modules"
```

A resumed call continues the durable pending queue. A new init after completion
regenerates that **temporary input repository's** wiki, not TokenLab's frozen
corpus. OpenWiki also creates managed AGENTS/workflow files in that external
input repository; they are not copied into TokenLab.

To inspect a rebuild without changing the frozen destination, leave its output
at `$BOOT_INPUT/openwiki`. Compare it to retained source provenance. For a new
versioned corpus, copy the entire native output directory with hidden files,
record byte hashes and only then add a SOURCE.md. Do not hand-edit .claims,
.page-manifest, indexes or generated provenance. New run UUIDs, Git commit times
and completion timestamps are expected; input/source/snippet hashes can still
be reproduced exactly. Rendering follows the pinned original English text.

Important source adaptations:

- Real Asciidoctor parsing handles sections, lists, tables and admonitions.
- configprops YAML remains YAML. No generated Properties alternative is invented.
- Javadoc URL attributes are separated from class names; class/annotation names
  survive even when a generated dependency URL catalog is unavailable.
- Internal source xrefs become explicit versioned official links. Local source
  anchors are mapped to real Markdown heading slugs.
- Named Java tags, `*`, `**`, exclusions, explicit line selections and indentation
  are handled and recorded. Missing selectors fail rather than emitting blanks.
- Kotlin, generated starter/property tables and runtime log-output partials are
  outside the selected input scope. The selected 50 units have no missing includes.

## Validate the retained corpus

Use a Python environment with this repository's requirements installed, for example `python3 -m venv .venv` then `.venv/bin/python -m pip install -r requirements.txt`. Activate it before running the validator:

```bash
TIKTOKEN_CACHE_DIR=/private/tmp/tokenlab-tiktoken \
  python \
  scripts/springboot_openwiki/validate.py \
  --input /private/tmp/tokenlab-springboot-input \
  --upstream /private/tmp/tokenlab-springboot-v4.2.0
```

The validator sets OPENWIKI_DIR to the Spring Boot folder and TOKENIZER to
`tiktoken:o200k_base` before importing the unchanged loader. It calls
`write_manifest(corpus, explicit_springboot_path)`; it never calls the corpus
CLI. Its output is `data/corpus_manifest.springboot-en.jsonl` and
`docs/corpora/springboot/validation.json`. It also checks that the FastAPI manifest
hash is unchanged. Never run `python src/corpus.py --stats` for this corpus:
that CLI uses the default shared manifest path.

For a rebuild, `--input "$BOOT_INPUT" --upstream "$BOOT_SOURCE" --wiki
"$BOOT_INPUT/openwiki" --out /private/tmp/springboot-rebuild-validation.json`
validates temporary output; it still writes the explicitly named Spring Boot
manifest, so rerun against the frozen corpus before committing that manifest.

Verification covers raw source hashes, prepared and expanded snippets, Java and
configuration blocks, inline identifiers/annotations, native page and Claims
hashes, evidence file/line hashes, Markdown links/heading anchors, closed fences
and unresolved directives. Optional `--upstream` also compares the raw files
against the pinned official checkout and resolves source xrefs. The full Antora
site and Java application samples are not compiled.

The ignored source archive path and hash, complete native output copy hashes,
source provenance, generation log, test log, statistics and limitations are in
`docs/corpora/springboot/`. Restoring the retained archive also restores the
curated input Git HEAD needed by the native metadata.
