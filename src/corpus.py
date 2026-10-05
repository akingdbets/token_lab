"""
코퍼스 로더 (OpenWiki 위키)

OpenWiki 가 만든 영어 위키(CFG.openwiki_dir, 기본 data/openwiki/en)를 가공 없이 읽어,
모든 실험이 공통으로 쓰는 "문서의 단일 출처"를 제공한다. 페이지를 고치지 않고,
일관된 ID로 읽어 주기만 한다.

범위
    위키의 .md 페이지 전부 (본문 + 목차)
    제외: 숨김 폴더·파일(.claims/ 등), OpenWiki 내부 파일(INSTRUCTIONS.md, SOURCE.md)

kind
    page        본문 페이지 (질문 생성 대상)
    quickstart  최상위 목차 페이지 (CFG.index_page). 탐색기가 인덱스로 그대로 읽는다
    index       루트·폴더 목차 페이지 (index.md)

doc_id 는 위키 루트 기준 POSIX 경로 (예: "request/request-body.md").
평가셋 근거와 실험 로그가 이 ID를 쓰므로 절대 바꾸지 않는다.

줄바꿈은 LF 로 통일해서 읽는다 (git core.autocrlf 설정과 관계없이 해시·토큰 수·줄 번호가 같도록).

사용 예
    from corpus import load_corpus

    corpus = load_corpus()
    doc = corpus.get("request/request-body.md")
    print(doc.kind, doc.title, doc.tokens, doc.links)
    print(corpus.section_text(doc.doc_id, "Request Body"))
    print(corpus.locate(doc.doc_id, "class Item(BaseModel):"))
    # -> {"doc_id": "request/request-body.md", "line": 31}
    print(corpus.in_code(doc.doc_id, 31))                 # 코드 블록 안의 줄인지
    print(corpus.resolve_page_ref("./request/request-body.md"))   # -> "request/request-body.md"

통계 (매니페스트 data/corpus_manifest.jsonl 도 함께 기록)
    python src/corpus.py --stats
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median

from config import CFG
from llm import count_tokens

# 위키 폴더 안이지만 코퍼스가 아닌 OpenWiki 내부 파일
INTERNAL_FILES = ("INSTRUCTIONS.md", "SOURCE.md")

HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
# [글자](대상) 의 대상. 외부 링크·앵커는 _resolve_link 에서 거른다
LINK = re.compile(r"\]\(([^)\s]+)\)")


@dataclass
class Section:
    """md 제목 하나. 줄 번호는 1부터, end는 포함.
    범위는 다음 같은/상위 레벨 제목 직전까지 (하위 제목 포함)."""
    level: int              # 1 = #, 2 = ##, 3 = ###
    heading: str
    start: int
    end: int


@dataclass
class Document:
    doc_id: str             # 위키 루트 기준 POSIX 경로. 불변
    kind: str               # "page" | "quickstart" | "index"
    title: str
    text: str               # 원문 그대로 (줄바꿈만 LF 로 통일)
    tokens: int
    sha256: str
    sections: list[Section] = field(default_factory=list)
    links: list[str] = field(default_factory=list)          # 코드 블록 밖 위키 내부 링크 (doc_id)
    broken_links: list[str] = field(default_factory=list)   # 위키 안 파일로 해석되지 않는 링크 원문
    code_lines: frozenset[int] = frozenset()                # 코드 블록 안의 줄 번호 (``` 줄 포함)

    @property
    def path(self) -> Path:
        return CFG.openwiki_dir / self.doc_id


# ---------------- 파싱 ----------------

def _lines(text: str) -> list[str]:
    """줄 번호 기준. splitlines()는 \\x0c 등에서도 끊어 편집기 줄 번호와 어긋나므로 쓰지 않는다."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _fence_lines(lines: list[str]) -> set[int]:
    """코드 블록에 속한 줄 번호 (1부터). 여는/닫는 ``` 줄도 포함."""
    inside: set[int] = set()
    fence = None
    for i, ln in enumerate(lines, 1):
        m = FENCE.match(ln)
        if fence is not None:
            inside.add(i)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
        elif m:
            fence = m.group(1)
            inside.add(i)
    return inside


def _frontmatter_end(text: str) -> int:
    """머리말(--- ... ---)의 마지막 줄 번호. 머리말이 없으면 0."""
    m = FRONTMATTER.match(text)
    return m.group(0).count("\n") if m else 0


def parse_sections(text: str) -> list[Section]:
    """#, ##, ### 제목과 줄 범위. 머리말과 코드 블록 안의 # 는 제목으로 치지 않는다."""
    lines = _lines(text)
    code = _fence_lines(lines)
    fm_end = _frontmatter_end(text)
    found = [(i, len(h.group(1)), h.group(2)) for i, ln in enumerate(lines, 1)
             if i > fm_end and i not in code and (h := HEADING.match(ln))]

    sections = []
    for k, (start, level, heading) in enumerate(found):
        end = len(lines)
        for nxt_start, nxt_level, _ in found[k + 1:]:
            if nxt_level <= level:
                end = nxt_start - 1
                break
        sections.append(Section(level, heading, start, end))
    return sections


def frontmatter_value(text: str, key: str) -> str | None:
    """머리말의 한 줄짜리 값 (예: title, type). 없으면 None."""
    m = FRONTMATTER.match(text)
    if not m:
        return None
    v = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", m.group(1), re.M)
    return v.group(1).strip("\"'") if v else None


def _resolve_link(target: str, doc_id: str) -> str | None:
    """링크 대상 -> 위키 doc_id 후보. 외부 링크·앵커만 있는 링크는 None.
    폴더 링크("about/")는 그 폴더의 index.md."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#"):
        return None
    target = target.split("#", 1)[0]
    if target.endswith("/"):
        target += "index.md"
    return posixpath.normpath(posixpath.join(posixpath.dirname(doc_id), target))


def _kind(doc_id: str) -> str:
    if doc_id == CFG.index_page:
        return "quickstart"
    return "index" if posixpath.basename(doc_id) == "index.md" else "page"


def _title(doc_id: str, text: str, sections: list[Section]) -> str:
    if t := frontmatter_value(text, "title"):
        return t
    if posixpath.basename(doc_id) == "index.md":     # 목차 페이지 제목은 모두 "# Files" 라 폴더로 구분
        folder = posixpath.dirname(doc_id)
        return f"{folder}/ index" if folder else "index"
    top = next((s for s in sections if s.level == 1), None)
    return top.heading if top else doc_id


def _read(path: Path) -> tuple[str, str]:
    """(원문, sha256). 줄바꿈만 LF 로 통일하고 나머지는 바이트 그대로."""
    b = path.read_bytes().replace(b"\r\n", b"\n")
    return b.decode("utf-8"), hashlib.sha256(b).hexdigest()


def _load_page(doc_id: str) -> Document:
    text, sha = _read(CFG.openwiki_dir / doc_id)
    sections = parse_sections(text)
    lines = _lines(text)
    code = _fence_lines(lines)

    raw_links = []
    for i, ln in enumerate(lines, 1):
        if i not in code:
            raw_links += [t for t in LINK.findall(ln) if _resolve_link(t, doc_id) is not None]
    return Document(doc_id, _kind(doc_id), _title(doc_id, text, sections), text,
                    count_tokens(text), sha, sections=sections,
                    links=raw_links, code_lines=frozenset(code))


# ---------------- 코퍼스 ----------------

_MARKUP = re.compile(r"</?[a-zA-Z][^>]*>")
# LLM 이 인용문을 `...` 나 "..." 로 감싸거나, 원문의 인라인 코드 백틱을 빼먹는 경우 대비
_QUOTES = re.compile("[`\"'“”‘’]")


def match_form(s: str) -> str:
    """인용문과 원문을 비교할 때만 쓰는 형태. HTML 태그, 백틱, 따옴표
    (" ' “ ” ‘ ’)를 양쪽에서 똑같이 걷어내고 공백을 하나로 접는다.
    줄 번호는 원본 기준 그대로이고, 이 형태는 비교에만 쓴다."""
    return re.sub(r"\s+", " ", _QUOTES.sub("", _MARKUP.sub("", s))).strip()


class Corpus:
    def __init__(self, documents: list[Document], source: dict):
        self._docs = {d.doc_id: d for d in sorted(documents, key=lambda d: d.doc_id)}
        self.source = source        # 위키 출처 (SOURCE.md 요약)
        self._match_lines: dict[str, list[str]] = {}

    def get(self, doc_id: str) -> Document:
        return self._docs[doc_id]

    def docs(self, kind: str | None = None) -> list[Document]:
        return [d for d in self._docs.values() if kind is None or d.kind == kind]

    def section_text(self, doc_id: str, heading: str) -> str:
        """제목 텍스트로 섹션 원문을 돌려준다. 같은 제목이 여럿이면 첫 번째."""
        d = self.get(doc_id)
        key = heading.lstrip("#").strip()
        for s in d.sections:
            if s.heading == key:
                return "\n".join(_lines(d.text)[s.start - 1:s.end])
        raise KeyError(f"{doc_id} 에 '{heading}' 섹션이 없습니다")

    def expanded_text(self, doc_id: str) -> str:
        """원문 그대로 (Document.text). 원본 코퍼스 시절 코드 펼친 보기의 자리를 지키는 함수로,
        experiment.py 가 쓴다. 위키는 예제 코드를 이미 본문에 담고 있어 펼칠 것이 없다."""
        return self.get(doc_id).text

    def in_code(self, doc_id: str, line: int) -> bool:
        """그 줄이 코드 블록 안(``` 줄 포함)인지."""
        return line in self.get(doc_id).code_lines

    def locate_all(self, doc_id: str, quote: str) -> list[dict]:
        """인용문이 페이지에서 일치하는 위치 전부 -> [{"file": doc_id, "line": 줄 번호}]. 못 찾으면 [].

        - 비교는 match_form 형태로 하고, 인용문이 여러 줄이면 가장 긴 줄로 찾는다
          (``` 줄은 제외). 6자 미만이면 어디든 걸리므로 근거로 인정하지 않는다.
        - 순서: 코드 블록 밖 줄 먼저, 그다음 코드 블록 안 줄.
        """
        parts = [match_form(ln) for ln in quote.split("\n")]
        parts = [ln for ln in parts if ln and not ln.startswith("```")]
        if not parts:
            return []
        needle = max(parts, key=len)
        if len(needle) < 6:
            return []

        d = self.get(doc_id)
        if doc_id not in self._match_lines:
            self._match_lines[doc_id] = [match_form(ln) for ln in _lines(d.text)]
        hits = [i for i, ln in enumerate(self._match_lines[doc_id], 1) if needle in ln]
        hits.sort(key=lambda i: i in d.code_lines)          # 코드 밖 먼저 (안정 정렬)
        return [{"file": doc_id, "line": i} for i in hits]

    def locate(self, doc_id: str, quote: str) -> dict | None:
        """locate_all 의 첫 위치 -> {"doc_id": 페이지, "line": 줄 번호}. 못 찾으면 None."""
        found = self.locate_all(doc_id, quote)
        return {"doc_id": found[0]["file"], "line": found[0]["line"]} if found else None

    # ---------- 페이지 경로 표기 ----------
    # 인덱스·탐색기·채점기가 페이지를 가리킬 때 쓰는 표기. 위키 루트 기준 경로라 doc_id 와 같다.
    # 다른 표기가 필요해지면 이 두 함수만 바꾼다.

    def page_ref(self, doc_id: str) -> str:
        """doc_id -> 페이지 표기 (현재는 같은 값)."""
        self.get(doc_id)
        return doc_id

    def resolve_page_ref(self, ref: str) -> str:
        """page_ref 의 반대. 앞뒤 공백, 앞의 "./" 나 "/", 실수로 붙은 위키 폴더 접두어
        (data/openwiki/en/), 폴더 링크("about/" -> "about/index.md")는 허용한다.
        코퍼스의 페이지가 아니면 KeyError."""
        r = ref.strip()
        while r.startswith(("./", "/")):
            r = r[2:] if r.startswith("./") else r[1:]
        prefix = _wiki_rel() + "/"
        if r.startswith(prefix):
            r = r[len(prefix):]
        if r == "" or r.endswith("/"):
            r += "index.md"
        if r not in self._docs:
            raise KeyError(f"코퍼스에 없는 페이지입니다: {ref!r}")
        return r

    def __len__(self):
        return len(self._docs)

    def __iter__(self):
        return iter(self._docs.values())

    def __contains__(self, doc_id: str):
        return doc_id in self._docs


def _wiki_rel() -> str:
    """위키 폴더의 프로젝트 루트 기준 경로 (data/openwiki/en). 루트 밖이면 절대 경로."""
    p = CFG.openwiki_dir.resolve()
    return p.relative_to(CFG.root).as_posix() if p.is_relative_to(CFG.root) else p.as_posix()


# SOURCE.md 표에서 매니페스트에 남길 항목 (표의 첫 칸 -> 키)
_SOURCE_KEYS = {
    "OpenWiki": "openwiki",
    "생성 방식": "method",
    "생성 모델": "model",
    "생성 일시": "generated_at",
    "언어": "language",
    "입력 FastAPI 커밋": "input_commit",
    "복사본 저장소 커밋": "wiki_repo_commit",
    "입력 범위": "input_scope",
}


def wiki_source() -> dict:
    """위키 출처 요약: SOURCE.md 표의 주요 항목 첫 문장 + 파일 해시."""
    src = {"wiki": _wiki_rel()}
    path = CFG.openwiki_dir / "SOURCE.md"
    if not path.is_file():
        warnings.warn(f"위키 출처를 알 수 없습니다 (SOURCE.md 없음): {path}")
        return src
    text, sha = _read(path)
    for m in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$", text, re.M):
        key = _SOURCE_KEYS.get(m.group(1))
        if key:
            src[key] = re.split(r"(?<=[.)])\s", m.group(2), maxsplit=1)[0]
    src["source_md_sha256"] = sha
    return src


def load_corpus() -> Corpus:
    root = CFG.openwiki_dir
    if not (root / CFG.index_page).is_file():
        raise FileNotFoundError(f"OpenWiki 위키가 아닙니다 ({CFG.index_page} 없음): {root}")

    ids = sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*.md")
        if not any(part.startswith(".") for part in p.relative_to(root).parts)
        and p.relative_to(root).as_posix() not in INTERNAL_FILES)
    docs = [_load_page(i) for i in ids]

    # 링크를 doc_id 로 확정. 위키 안 파일로 해석되지 않으면 broken_links 로
    known = set(ids)
    for d in docs:
        resolved, broken = [], []
        for t in d.links:
            r = _resolve_link(t, d.doc_id)
            if r in known:
                if r != d.doc_id and r not in resolved:
                    resolved.append(r)
            elif t not in broken:
                broken.append(t)
        d.links, d.broken_links = resolved, broken

    return Corpus(docs, wiki_source())


def manifest_text(corpus: Corpus) -> str:
    """첫 줄은 위키 출처, 이후 문서별 한 줄. 같은 위키면 바이트 단위로 동일."""
    rows = [{"source": corpus.source, "documents": len(corpus),
             "kinds": dict(sorted(Counter(d.kind for d in corpus).items()))}]
    rows += [{"doc_id": d.doc_id, "kind": d.kind, "title": d.title, "tokens": d.tokens,
              "sha256": d.sha256, "links": len(d.links)} for d in corpus]
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

def _dist(xs: list[int]) -> str:
    return (f"최소 {min(xs):,} / 중앙 {int(median(xs)):,} / "
            f"평균 {int(mean(xs)):,} / 최대 {max(xs):,}")


def print_stats(corpus: Corpus):
    print("출처")
    for k, v in corpus.source.items():
        print(f"  {k:18s} {v}")

    kinds = Counter(d.kind for d in corpus)
    print(f"\n페이지     : {len(corpus)}개 (본문 page {kinds['page']} / "
          f"최상위 목차 quickstart {kinds['quickstart']} / 목차 index {kinds['index']})")
    for k in ("page", "quickstart", "index"):
        g = corpus.docs(k)
        if g:
            print(f"  {k:10s} 토큰 합 {sum(d.tokens for d in g):>8,}   {_dist([d.tokens for d in g])}")
    print(f"  전체       토큰 합 {sum(d.tokens for d in corpus):>8,}")

    print("\n폴더별 페이지 (본문 / 목차)")
    folders: dict[str, list[Document]] = {}
    for d in corpus:
        folders.setdefault(d.doc_id.split("/")[0] if "/" in d.doc_id else "(root)", []).append(d)
    for k in sorted(folders):
        g = folders[k]
        pages = [d for d in g if d.kind == "page"]
        print(f"  {k:16s} {len(pages):3d} / {len(g) - len(pages)}   "
              f"본문 {sum(d.tokens for d in pages):>7,} 토큰")

    top = corpus.get(CFG.index_page) if CFG.index_page in corpus else None
    print(f"\n최상위 목차 페이지 (CFG.index_page): {CFG.index_page}"
          + (f"  ({top.tokens:,} 토큰)" if top else "  ※ 코퍼스에 없음"))
    if top:
        pages = {d.doc_id for d in corpus.docs("page")}
        missing = sorted(pages - set(top.links))
        print(f"  링크하는 본문 페이지 {len(pages & set(top.links))} / {len(pages)}"
              + (f"  (빠진 페이지: {', '.join(missing)})" if missing else ""))

    n_links = sum(len(d.links) for d in corpus)
    code = sum(len(d.code_lines) for d in corpus)
    total = sum(len(_lines(d.text)) for d in corpus)
    print(f"\n내부 링크  : {n_links}개 (코드 블록 밖)")
    print(f"코드 블록 줄 비율: {100 * code / total:.1f}% ({code:,} / {total:,}줄)")

    bad = [(d.doc_id, t) for d in corpus for t in d.broken_links]
    print(f"\n깨진 링크  : {len(bad)}개" + ("  ※ 경고: 위키 원본이라 고치지 않는다" if bad else ""))
    for doc_id, t in bad:
        print(f"  ※ {doc_id}: ({t})")


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
