# TECHNICAL DOCUMENTATION RULES (read first; these override the Telegraph English rules below where they conflict)

The text to convert is a page of software documentation (FastAPI). Apply Telegraph English to the prose, with these exceptions:

1. **Code placeholders.** Lines like `⟦CODE-3⟧` stand for code blocks that were removed before conversion and will be put back afterwards. Copy every placeholder line exactly, alone on its own line, in its original order. Never drop, edit, merge, translate or add placeholder lines.
2. **Identifiers keep their exact spelling and case.** The upper-case default does NOT apply to identifiers: class, function, method, parameter, attribute, module and package names, CLI commands, file paths, environment variables, HTTP headers and methods, URLs (for example `APIRouter`, `model_dump`, `Depends()`, `fastapi dev`, `FASTAPI_ENV`, `WWW-Authenticate`). Do not hyphen-join, abbreviate or re-case them. Text inside backticks is copied verbatim, backticks included.
3. **Copy these verbatim:** every number, version string (`0.95.0`), status code, hyphenated name (`starlette-graphene3`), quoted value (`"request"`, `"Successful Response"`) and default value. Do not round, reformat or convert units.
4. **No omission, no invention.** Every fact in the source must survive: defaults, conditions, exceptions, version notes, comparisons, and which thing a statement is about. Do not add facts. If a symbol would make a statement ambiguous, keep the original words.
5. **Headings.** Markdown headings (`#`, `##`, `###`) become `H1:`, `H2:`, `H3:` with the heading text kept (identifiers in headings keep their case).
6. **Output only the converted lines.** No commentary, no surrounding code fence.

---

