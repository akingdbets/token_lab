"""
raw 코퍼스 로더

data/raw 의 FastAPI 저장소 스냅샷을 가공 없이 읽어, 모든 실험이 공통으로 쓰는
"원본 문서의 단일 출처"를 제공한다. 문서를 고치지 않고, 일관된 ID로 읽어 주기만 한다.

범위
    문서      docs/en/docs/**/*.md   (config.corpus_exclude 제외)
    코드      docs_src/**/*.py 전체 + 코퍼스 문서가 {* ... *} 로 참조하는 그 외 파일
              (예: fastapi/openapi/docs.py)

doc_id 는 저장소 루트 기준 POSIX 경로 (예: "docs/en/docs/tutorial/body.md").
평가셋 근거와 실험 로그가 이 ID를 쓰므로 절대 바꾸지 않는다.

사용 예
    from corpus import load_corpus

    corpus = load_corpus()
    doc = corpus.get("docs/en/docs/tutorial/body.md")
    print(doc.title, doc.tokens, doc.code_refs)
    print(corpus.section_text(doc.doc_id, "Import Pydantic's BaseModel"))
    print(corpus.expanded_text(doc.doc_id))          # {* ... *} 를 예제 코드로 펼친 보기
    print(corpus.locate(doc.doc_id, "class Item(BaseModel):"))
    # -> {"doc_id": "docs_src/body/tutorial001_py310.py", "line": 5}
    print(corpus.locate_all(doc.doc_id, "class Item(BaseModel):"))   # 일치하는 위치 전부
    print(corpus.page_ref(doc.doc_id))                   # -> "tutorial/body.md"
    print(corpus.resolve_page_ref("tutorial/body.md"))   # -> "docs/en/docs/tutorial/body.md"

통계 (매니페스트 data/corpus_manifest.jsonl 도 함께 기록)
    python src/corpus.py --stats
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median

from config import CFG
from llm import count_tokens

DOCS_PREFIX = "docs/en/docs/"
CODE_PREFIX = "docs_src/"

# {* ../../docs_src/body/tutorial001_py310.py hl[9] *}
CODE_REF = re.compile(r"\{\*\s*(\S+?\.py)\b[^*]*\*\}")
# ln[19:21] / ln[1:2,19:26,29] : 웹사이트에 보이는 줄. 원본 파일 기준 1부터, 끝 포함
LINE_RANGE = re.compile(r"\bln\[([^\]]*)\]")
HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
ANCHOR = re.compile(r"\s*\{\s*#([\w\-]+)\s*\}\s*$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


@dataclass
class Section:
    """md 제목 하나. 줄 번호는 1부터, end는 포함.
    범위는 다음 같은/상위 레벨 제목 직전까지 (하위 제목 포함)."""
    level: int              # 1 = #, 2 = ##, 3 = ###
    heading: str            # 앵커 { #id } 를 뗀 제목
    anchor: str | None      # { #id } 의 id
    start: int
    end: int


@dataclass
class Document:
    doc_id: str             # 저장소 루트 기준 POSIX 경로. 불변
    kind: str               # "doc" | "code"
    title: str
    text: str               # 원문 그대로 (줄바꿈 포함 한 글자도 바꾸지 않음)
    tokens: int
    sha256: str
    sections: list[Section] = field(default_factory=list)
    code_refs: list[str] = field(default_factory=list)       # 참조하는 코드 파일 doc_id
    unresolved_refs: list[str] = field(default_factory=list)  # 해석 실패한 참조 원문
    referenced_by: list[str] = field(default_factory=list)    # code: 이 파일을 참조하는 md

    @property
    def path(self) -> Path:
        return CFG.raw_repo / self.doc_id


# ---------------- 파싱 ----------------

def _lines(text: str) -> list[str]:
    """줄 번호 기준. splitlines()는 \\x0c 등에서도 끊어 편집기 줄 번호와 어긋나므로 쓰지 않는다."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def parse_sections(text: str) -> list[Section]:
    """#, ##, ### 제목과 줄 범위. 코드 블록 안의 # 주석은 제목으로 치지 않는다."""
    lines = _lines(text)
    found: list[tuple[int, int, str]] = []    # (줄 번호, 레벨, 제목 원문)
    fence = None
    for i, ln in enumerate(lines, 1):
        ln = ln.rstrip("\r")
        m = FENCE.match(ln)
        if m:
            mark = m.group(1)
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
            continue
        if fence is None and (h := HEADING.match(ln)):
            found.append((i, len(h.group(1)), h.group(2)))

    sections = []
    for k, (start, level, raw) in enumerate(found):
        end = len(lines)
        for nxt_start, nxt_level, _ in found[k + 1:]:
            if nxt_level <= level:
                end = nxt_start - 1
                break
        a = ANCHOR.search(raw)
        heading = ANCHOR.sub("", raw).strip() if a else raw
        sections.append(Section(level, heading, a.group(1) if a else None, start, end))
    return sections


def parse_line_range(ref_text: str) -> list[tuple[int, int]] | None:
    """참조 구문의 ln[...] -> [(시작, 끝), ...] (1부터, 끝 포함). 없으면 None (파일 전체).
    FastAPI 문서 빌드 도구(markdown-include-variants 0.0.8 parse_lines_index)와 같게
    구간을 정렬해서 돌려준다. 48건 전부 빌드 도구 출력과 코드 줄·생략 위치가 일치함을 확인."""
    m = LINE_RANGE.search(ref_text)
    if not m:
        return None
    ranges = []
    for part in m.group(1).split(","):
        a, _, b = part.strip().partition(":")
        ranges.append((int(a), int(b or a)))
    return sorted(ranges)


def resolve_ref(ref: str, doc_id: str) -> str | None:
    """코드 참조 경로 -> 참조 대상 파일의 doc_id.
    1) 문서 기준 상대 경로  2) 앞의 ../ 를 뗀 저장소 루트 기준 경로. 이 둘만 시도한다.
    (파일 이름 검색은 tutorial001.py 같은 동명 파일이 많아 오매칭되므로 쓰지 않음)"""
    candidates = (
        posixpath.normpath(posixpath.join(posixpath.dirname(doc_id), ref)),
        posixpath.normpath(re.sub(r"^(\.\./)+", "", ref)),
    )
    for c in candidates:
        if not c.startswith("../") and (CFG.raw_repo / c).is_file():
            return c
    return None


def is_excluded(doc_id: str) -> bool:
    rel = doc_id[len(DOCS_PREFIX):]
    for pat in CFG.corpus_exclude:
        if (pat.endswith("/") and rel.startswith(pat)) or rel == pat:
            return True
    return False


def _read(doc_id: str) -> tuple[str, str]:
    """(원문, sha256). 바이트 그대로 디코딩해 줄바꿈 변환도 하지 않는다."""
    b = (CFG.raw_repo / doc_id).read_bytes()
    return b.decode("utf-8"), hashlib.sha256(b).hexdigest()


def _load_md(doc_id: str) -> Document:
    text, sha = _read(doc_id)
    sections = parse_sections(text)
    top = next((s for s in sections if s.level == 1), None)
    title = top.heading if top else posixpath.basename(doc_id)

    refs, unresolved = [], []
    for m in CODE_REF.finditer(text):
        target = resolve_ref(m.group(1), doc_id)
        if target is None:
            if m.group(0) not in unresolved:
                unresolved.append(m.group(0))
        elif target not in refs:
            refs.append(target)

    return Document(doc_id, "doc", title, text, count_tokens(text), sha,
                    sections=sections, code_refs=refs, unresolved_refs=unresolved)


def _load_code(doc_id: str) -> Document:
    text, sha = _read(doc_id)
    return Document(doc_id, "code", doc_id, text, count_tokens(text), sha)


# ---------------- 코퍼스 ----------------

_MARKUP = re.compile(r"\{\s*#[\w\-]+\s*\}|</?[a-zA-Z][^>]*>")
# LLM 이 인용문을 `...` 나 "..." 로 감싸거나, 원문의 인라인 코드 백틱을 빼먹는 경우 대비
_QUOTES = re.compile("[`\"'“”‘’]")


def match_form(s: str) -> str:
    """인용문과 원문을 비교할 때만 쓰는 형태. 앵커 { #id }, HTML 태그, 백틱, 따옴표
    (" ' “ ” ‘ ’)를 양쪽에서 똑같이 걷어내고 공백을 하나로 접는다.
    줄 번호는 원본 기준 그대로이고, 이 형태는 비교에만 쓴다."""
    return re.sub(r"\s+", " ", _QUOTES.sub("", _MARKUP.sub("", s))).strip()


class Corpus:
    def __init__(self, documents: list[Document], source: str):
        self._docs = {d.doc_id: d for d in sorted(documents, key=lambda d: d.doc_id)}
        self.source = source        # 스냅샷 출처 (SOURCE.md 내용 또는 git 커밋)
        self._expanded: dict[str, tuple[str, list]] = {}
        self._match_lines: dict[str, list[str]] = {}

    def get(self, doc_id: str) -> Document:
        return self._docs[doc_id]

    def docs(self, kind: str | None = None) -> list[Document]:
        return [d for d in self._docs.values() if kind is None or d.kind == kind]

    def section_text(self, doc_id: str, heading: str) -> str:
        """제목(앵커 뗀 텍스트) 또는 앵커 id로 섹션 원문을 돌려준다. 같은 제목이 여럿이면 첫 번째."""
        d = self.get(doc_id)
        key = heading.lstrip("#").strip()
        for s in d.sections:
            if key in (s.heading, s.anchor):
                return "\n".join(_lines(d.text)[s.start - 1:s.end])
        raise KeyError(f"{doc_id} 에 '{heading}' 섹션이 없습니다")

    # ---------- 코드 참조 펼친 보기 ----------

    def _expand(self, doc_id: str) -> tuple[str, list[tuple[str, int] | None]]:
        """(펼친 텍스트, 줄별 출처). 출처는 (원본 doc_id, 그 파일의 줄 번호),
        펼치면서 끼워 넣은 ``` / # file: 줄은 None. Document.text 는 건드리지 않는다."""
        if doc_id in self._expanded:
            return self._expanded[doc_id]
        d = self.get(doc_id)
        out: list[str] = []
        origin: list[tuple[str, int] | None] = []

        def emit(line, src):
            out.append(line)
            origin.append(src)

        for i, ln in enumerate(_lines(d.text), 1):
            pos = 0
            for m in CODE_REF.finditer(ln):
                target = resolve_ref(m.group(1), doc_id) if d.kind == "doc" else None
                if target is None or target not in self._docs:
                    continue                      # 해석 실패 참조는 원문 그대로 둔다
                if ln[pos:m.start()].strip():
                    emit(ln[pos:m.start()], (doc_id, i))
                emit("```python", None)
                emit(f"# file: {target}", None)
                code = _lines(self._docs[target].text)
                # ln[...] 이 있으면 웹사이트처럼 그 줄만 넣고, 빠진 부분은 "# ..." 한 줄로 표시
                ranges = parse_line_range(m.group(0)) or [(1, len(code))]
                last = 0
                for a, b in ranges:
                    a, b = max(a, 1), min(b, len(code))
                    if a > b:
                        continue
                    if a > last + 1:
                        emit("# ...", None)
                    for k in range(a, b + 1):
                        emit(code[k - 1], (target, k))
                    last = b
                if last < len(code):
                    emit("# ...", None)
                emit("```", None)
                pos = m.end()
            if pos == 0:
                emit(ln, (doc_id, i))
            elif ln[pos:].strip():
                emit(ln[pos:], (doc_id, i))

        self._expanded[doc_id] = ("\n".join(out), origin)
        return self._expanded[doc_id]

    def expanded_text(self, doc_id: str) -> str:
        """{* ... *} 코드 참조를 실제 코드로 펼친 보기용 텍스트.
        각 코드 블록은 "```python" / "# file: <doc_id>" 로 시작한다. ln[...] 이 있으면
        그 줄만 넣고 빠진 부분은 "# ..." 로 표시한다. 원문(Document.text)은 그대로."""
        return self._expand(doc_id)[0]

    def locate_all(self, doc_id: str, quote: str) -> list[dict]:
        """인용문이 펼친 텍스트에서 일치하는 원본 위치 전부 -> [{"file": 원본 doc_id, "line": 줄 번호}].
        펼친 코드 안이면 해당 코드 파일과 그 파일의 줄 번호. 못 찾으면 [].

        - 비교는 match_form 형태로 하고, 인용문이 여러 줄이면 가장 긴 줄로 찾는다
          (```, # file: 줄은 제외). 6자 미만이면 어디든 걸리므로 근거로 인정하지 않는다.
        - 순서: 문서 본문 줄 먼저, 그다음 펼친 코드 줄. 같은 (file, line) 은 한 번만
          (같은 코드 파일을 여러 번 펼쳐도 한 번).
        """
        parts = [match_form(ln) for ln in quote.split("\n")]
        parts = [ln for ln in parts if ln and not ln.startswith(("```", "# file:"))]
        if not parts:
            return []
        needle = max(parts, key=len)
        if len(needle) < 6:
            return []

        text, origin = self._expand(doc_id)
        if doc_id not in self._match_lines:
            self._match_lines[doc_id] = [match_form(ln) for ln in text.split("\n")]
        lines = self._match_lines[doc_id]
        found: list[dict] = []
        seen: set[tuple[str, int]] = set()
        for own in (True, False):
            for ln, src in zip(lines, origin):
                if src and (src[0] == doc_id) == own and needle in ln and src not in seen:
                    seen.add(src)
                    found.append({"file": src[0], "line": src[1]})
        return found

    def locate(self, doc_id: str, quote: str) -> dict | None:
        """locate_all 의 첫 위치 -> {"doc_id": 원본 파일, "line": 줄 번호}. 못 찾으면 None.
        (같은 줄이 양쪽에 있으면 본문 우선)"""
        found = self.locate_all(doc_id, quote)
        return {"doc_id": found[0]["file"], "line": found[0]["line"]} if found else None

    # ---------- 페이지 경로 표기 ----------
    # 인덱스·탐색기·채점기가 md 페이지를 가리킬 때 쓰는 짧은 표기 (docs/en/docs 기준 경로).
    # 모두 이 두 함수만 써서 변환한다. 코드 문서는 인덱스에 나오지 않으므로 다루지 않는다.

    def page_ref(self, doc_id: str) -> str:
        """"docs/en/docs/tutorial/body.md" -> "tutorial/body.md". md 문서(kind="doc")만."""
        d = self.get(doc_id)
        if d.kind != "doc" or not doc_id.startswith(DOCS_PREFIX):
            raise KeyError(f"md 문서가 아닙니다: {doc_id}")
        return doc_id[len(DOCS_PREFIX):]

    def resolve_page_ref(self, ref: str) -> str:
        """page_ref 의 반대. "tutorial/body.md" -> "docs/en/docs/tutorial/body.md".
        앞뒤 공백, 앞의 "./" 나 "/", 실수로 붙은 "docs/en/docs/" 접두어는 허용한다.
        코퍼스의 md 문서가 아니면 KeyError."""
        r = ref.strip()
        while r.startswith(("./", "/")):
            r = r[2:] if r.startswith("./") else r[1:]
        if r.startswith(DOCS_PREFIX):
            r = r[len(DOCS_PREFIX):]
        doc_id = DOCS_PREFIX + r
        if doc_id not in self._docs or self._docs[doc_id].kind != "doc":
            raise KeyError(f"코퍼스에 없는 페이지입니다: {ref!r}")
        return doc_id

    def __len__(self):
        return len(self._docs)

    def __iter__(self):
        return iter(self._docs.values())

    def __contains__(self, doc_id: str):
        return doc_id in self._docs


def snapshot_source() -> str:
    """SOURCE.md 가 있으면 그 내용, 없으면 저장소 git 커밋 해시, 둘 다 없으면 unknown."""
    src = CFG.raw_dir / "SOURCE.md"
    if src.is_file():
        return src.read_text(encoding="utf-8").strip()
    try:
        # 상위 프로젝트(token_lab) 저장소를 잘못 읽지 않도록 스냅샷 루트가 git 최상위인지 확인
        top = subprocess.run(["git", "-C", str(CFG.raw_repo), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        if Path(top).resolve() == CFG.raw_repo.resolve():
            return "git:" + subprocess.run(
                ["git", "-C", str(CFG.raw_repo), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    warnings.warn("스냅샷 출처를 알 수 없습니다 (SOURCE.md, git 모두 없음)")
    return "unknown"


def load_corpus() -> Corpus:
    root = CFG.raw_repo
    if not (root / "docs" / "en").is_dir():
        raise FileNotFoundError(f"저장소 루트가 아닙니다 (docs/en 없음): {root}")

    md_ids = sorted(p.relative_to(root).as_posix() for p in (root / DOCS_PREFIX).rglob("*.md"))
    code_ids = sorted(p.relative_to(root).as_posix() for p in (root / CODE_PREFIX).rglob("*.py"))

    docs = [_load_md(i) for i in md_ids if not is_excluded(i)]
    # 코드 범위: docs_src 전체 + 문서가 참조하는 그 외 파일 (config.corpus_exclude 주석 참고)
    extra = sorted({r for d in docs for r in d.code_refs} - set(code_ids))
    codes = {i: _load_code(i) for i in sorted(code_ids + extra)}
    for d in docs:                       # doc_id 순으로 돌므로 referenced_by 도 정렬됨
        for ref in d.code_refs:
            if ref in codes:
                codes[ref].referenced_by.append(d.doc_id)

    return Corpus(docs + list(codes.values()), snapshot_source())


def manifest_text(corpus: Corpus) -> str:
    """첫 줄은 스냅샷 출처, 이후 문서별 한 줄. 같은 스냅샷이면 바이트 단위로 동일."""
    rows = [{"source": corpus.source, "documents": len(corpus)}]
    rows += [{"doc_id": d.doc_id, "kind": d.kind, "title": d.title, "tokens": d.tokens,
              "sha256": d.sha256, "code_refs": len(d.code_refs)} for d in corpus]
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def manifest_sha256(corpus: Corpus) -> str:
    """매니페스트 파일 내용의 해시. 평가셋이 어떤 코퍼스로 만들어졌는지 기록하는 데 쓴다."""
    return hashlib.sha256(manifest_text(corpus).encode("utf-8")).hexdigest()


def write_manifest(corpus: Corpus, path: Path | None = None) -> Path:
    path = path or CFG.corpus_manifest
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(manifest_text(corpus))
    return path


# ---------------- 통계 ----------------

MKDOCS_YML = "docs/en/mkdocs.yml"


def load_nav() -> list | None:
    """docs/en/mkdocs.yml 의 nav 원형 (pyyaml 파싱 결과). 페이지 경로는 docs/en/docs 기준.
    nav 블록만 떼어 읽는다 (파일 전체에는 !!python/name 태그가 있어 safe_load가 실패한다).
    파일이나 nav 가 없으면 None."""
    import yaml
    mk = CFG.raw_repo / MKDOCS_YML
    if not mk.is_file():
        return None
    lines = mk.read_text(encoding="utf-8").splitlines()
    try:
        s = next(i for i, ln in enumerate(lines) if ln.startswith("nav:"))
    except StopIteration:
        return None
    e = s + 1
    while e < len(lines) and (not lines[e].strip() or lines[e][0] in " -#"):
        e += 1
    return yaml.safe_load("\n".join(lines[s:e]))["nav"]


def _nav_pages() -> tuple[int, list[str]] | None:
    """nav: (최상위 항목 수, 페이지 경로 목록)."""
    try:
        nav = load_nav()
    except ImportError:
        return None
    if nav is None:
        return None

    pages = []

    def walk(node):
        if isinstance(node, str):
            pages.append(node)
        elif isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)

    walk(nav)
    return len(nav), pages


def _dist(xs: list[int]) -> str:
    return (f"최소 {min(xs):,} / 중앙 {int(median(xs)):,} / "
            f"평균 {int(mean(xs)):,} / 최대 {max(xs):,}")


def print_stats(corpus: Corpus):
    docs, codes = corpus.docs("doc"), corpus.docs("code")
    print(f"출처       : {corpus.source}")
    print(f"문서(md)   : {len(docs)}개   코드(py): {len(codes)}개")
    dt, ct = sum(d.tokens for d in docs), sum(d.tokens for d in codes)
    print(f"총 토큰    : {dt + ct:,}  (문서 {dt:,} / 코드 {ct:,})")
    print(f"문서 토큰  : {_dist([d.tokens for d in docs])}")
    print(f"코드 토큰  : {_dist([d.tokens for d in codes])}")
    unref = sum(1 for c in codes if not c.referenced_by)
    print(f"참조 없는 코드 파일: {unref}개")

    print("\n폴더별 문서")
    folders: dict[str, list[Document]] = {}
    for d in docs:
        rel = d.doc_id[len(DOCS_PREFIX):]
        folders.setdefault(rel.split("/")[0] if "/" in rel else "(root)", []).append(d)
    for k in sorted(folders):
        g = folders[k]
        print(f"  {k:12s} {len(g):4d}개  {sum(d.tokens for d in g):>9,} 토큰")

    refs = [m.group(0) for d in docs for m in CODE_REF.finditer(d.text)]
    ranged = sum(1 for r in refs if LINE_RANGE.search(r))
    outside = sorted({c.doc_id for c in codes if not c.doc_id.startswith(CODE_PREFIX)})
    print(f"\n코드 참조  : {len(refs)}건 (줄 범위 ln[...] 지정 {ranged}건)")
    print(f"docs_src 밖 코드 문서: {len(outside)}개 {outside if outside else ''}")

    bad = [(d.doc_id, r) for d in docs for r in d.unresolved_refs]
    print(f"\n해석 실패 코드 참조: {len(bad)}개")
    for doc_id, r in bad[:20]:
        print(f"  {doc_id}: {r}")

    mk = CFG.raw_repo / MKDOCS_YML
    print(f"\nmkdocs.yml : {'있음' if mk.is_file() else '없음'} ({mk.relative_to(CFG.root).as_posix()})")
    if mk.is_file():
        nav = _nav_pages()
        if nav is None:
            print("  nav 파싱 불가 (pyyaml 없음 또는 nav 없음)")
        else:
            top, pages = nav
            md_pages = {DOCS_PREFIX + p for p in pages if p.endswith(".md")}
            in_corpus = {d.doc_id for d in docs}
            print(f"  nav 최상위 {top}개 / 페이지 {len(pages)}개 (md {len(md_pages)}개)")
            print(f"  코퍼스 문서 중 nav 에 있음 {len(in_corpus & md_pages)} / "
                  f"없음 {len(in_corpus - md_pages)}")
            missing = sorted(in_corpus - md_pages)
            if missing:
                print("  nav 에 없는 코퍼스 문서: " + ", ".join(m[len(DOCS_PREFIX):] for m in missing))

    idx = CFG.raw_repo / DOCS_PREFIX / "index.md"
    print(f"\n{DOCS_PREFIX}index.md 첫 20줄")
    if idx.is_file():
        for ln in _lines(_read(DOCS_PREFIX + "index.md")[0])[:20]:
            print("  | " + ln.rstrip("\r")[:120])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true", help="코퍼스 통계 출력")
    args = ap.parse_args()

    corpus = load_corpus()
    path = write_manifest(corpus)
    if args.stats:
        print_stats(corpus)
    print(f"\n매니페스트: {path.relative_to(CFG.root).as_posix()} ({len(corpus) + 1}줄)")


if __name__ == "__main__":
    main()
