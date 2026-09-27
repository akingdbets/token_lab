"""
탐색용 인덱스 생성

코퍼스 문서를 가리키는 목차(인덱스)를 만들어 data/index/{변형 이름}.md 로 쓴다.
인덱스 변형은 VARIANTS 에 이름 -> 생성 함수로 등록한다. 생성 함수는 코퍼스를 받아
인덱스 본문(마크다운)을 돌려주고, 저장·보고는 build_index 가 공통으로 한다.

변형
    nav_v0   docs/en/mkdocs.yml 의 nav 계층(섹션 -> 페이지)을 들여쓴 목록으로.
             항목마다 페이지 제목과 경로만 (요약·태그·핵심 용어 없음).
             경로는 docs/en/docs 기준 (corpus.page_ref, 예: tutorial/body.md).
             탐색기·채점기는 corpus.resolve_page_ref 로 doc_id 로 되돌린다.

본문의 모든 경로가 원래 doc_id 로 1:1 로 돌아오는지 쓰기 전에 검사한다 (check_paths).

저장 (data/index/)
    {이름}.md          인덱스 본문 (LLM 에 그대로 넣는 텍스트)
    {이름}.meta.json   만든 코퍼스(매니페스트 해시), 항목 수, 토큰 수, nav 와 코퍼스 차이

사용법
    python src/index_builder.py                  # nav_v0
    python src/index_builder.py --variant nav_v0
    python src/index_builder.py --list           # 등록된 변형 목록
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from config import CFG
from corpus import DOCS_PREFIX, Corpus, load_corpus, load_nav, manifest_sha256
from llm import count_tokens


# ---------------- nav 트리 ----------------

@dataclass
class Node:
    title: str
    doc_id: str | None                  # 섹션인데 대표 페이지가 코퍼스에 없으면 None
    children: list[Node] = field(default_factory=list)


@dataclass
class NavTree:
    nodes: list[Node]
    nav_pages: list[str]                # nav 에 나온 모든 md 페이지 doc_id (코퍼스 제외 포함, 나온 순서)


def _page_path(item) -> tuple[str, str] | None:
    """nav 항목이 페이지면 (nav 제목, 경로). 'x.md' 또는 {'제목': 'x.md'}."""
    if isinstance(item, str):
        return "", item
    if isinstance(item, dict) and len(item) == 1:
        (k, v), = item.items()
        if isinstance(v, str):
            return k or "", v
    return None


def parse_nav(nav: list, corpus: Corpus) -> NavTree:
    """mkdocs nav -> Node 트리. 코퍼스에 없는 페이지는 뺀다.

    섹션 제목: 이 nav 는 섹션 이름이 모두 "" 이고 navigation.indexes 기능으로 섹션의 첫
    index.md 페이지가 섹션 자체를 대표한다 (웹사이트에서 섹션 이름 = 그 페이지 제목).
    그래서 섹션 첫 항목이 index.md 면 그 페이지를 섹션 줄로 올린다. 그 페이지가 코퍼스에서
    제외됐으면 섹션 줄은 폴더 이름만 남기고 doc_id 는 비운다 (하위 페이지 묶음 표시용).
    """
    nav_pages: list[str] = []

    def page(title: str, path: str) -> Node | None:
        if "://" in path or not path.endswith(".md"):
            return None                         # 외부 링크 등
        doc_id = posixpath.normpath(DOCS_PREFIX + path)
        nav_pages.append(doc_id)
        if doc_id not in corpus:
            return None
        return Node(title or corpus.get(doc_id).title, doc_id)

    def section(title: str, items: list) -> Node | None:
        items = list(items)
        head = None
        if items and (p := _page_path(items[0])) and p[1].endswith("index.md"):
            head = p
            items = items[1:]
        children = walk(items)
        rep = page(*head) if head else None
        if rep is not None:
            label, doc_id = (title or rep.title), rep.doc_id
        else:
            folder = posixpath.basename(posixpath.dirname(head[1])) if head else ""
            label, doc_id = (title or folder or "(섹션)"), None
        if doc_id is None and not children:
            return None                         # 전부 코퍼스 밖이면 섹션째 뺀다
        return Node(label, doc_id, children)

    def walk(items: list) -> list[Node]:
        out = []
        for it in items:
            if (p := _page_path(it)) is not None:
                n = page(*p)
            elif isinstance(it, dict):
                n = None
                for k, v in it.items():
                    if isinstance(v, list) and (s := section(k or "", v)) is not None:
                        out.append(s)
                continue
            else:
                n = None
            if n is not None:
                out.append(n)
        return out

    return NavTree(walk(nav), nav_pages)


def render(nodes: list[Node], ref: Callable[[str], str], depth: int = 0) -> list[str]:
    """들여쓴 마크다운 목록. 줄마다 '- 제목 (경로)', 대표 페이지 없는 섹션은 '- 제목'.
    경로 표기는 ref(doc_id) 로 정한다 (nav_v0 는 corpus.page_ref: tutorial/body.md)."""
    lines = []
    for n in nodes:
        pad = "  " * depth
        lines.append(f"{pad}- {n.title} ({ref(n.doc_id)})" if n.doc_id else f"{pad}- {n.title}")
        lines += render(n.children, ref, depth + 1)
    return lines


def flatten_doc_ids(nodes: list[Node]) -> list[str]:
    """인덱스에 나오는 순서대로 doc_id 목록 (doc_id 없는 섹션 줄 제외)."""
    out = []
    for n in nodes:
        if n.doc_id:
            out.append(n.doc_id)
        out += flatten_doc_ids(n.children)
    return out


def count_nodes(nodes: list[Node]) -> tuple[int, int]:
    """(doc_id 가 있는 항목 수, doc_id 없는 섹션 줄 수)."""
    pages = groups = 0
    for n in nodes:
        if n.doc_id:
            pages += 1
        else:
            groups += 1
        p, g = count_nodes(n.children)
        pages, groups = pages + p, groups + g
    return pages, groups


# ---------------- 변형 ----------------

@dataclass
class IndexResult:
    text: str
    entries: int                        # doc_id 가 붙은 항목 수
    groups: int                         # doc_id 없는 섹션 줄 수
    doc_ids: list[str] = field(default_factory=list)   # 본문에 경로가 나오는 순서대로 (검증용)
    notes: dict = field(default_factory=dict)   # 변형별 보고 내용 (meta 에 저장)


def build_nav_v0(corpus: Corpus) -> IndexResult:
    """mkdocs nav 계층을 그대로. 페이지 제목은 nav 에 제목이 있으면 그것, 없으면 코퍼스 제목(# 제목).
    경로는 docs/en/docs 기준 (corpus.page_ref) — 공통 접두어를 줄마다 반복하지 않는다."""
    nav = load_nav()
    if nav is None:
        raise FileNotFoundError("mkdocs.yml 의 nav 를 찾을 수 없습니다")
    tree = parse_nav(nav, corpus)
    entries, groups = count_nodes(tree.nodes)
    in_nav = set(tree.nav_pages)
    corpus_docs = {d.doc_id for d in corpus.docs("doc")}
    notes = {
        "path_style": "docs_rel",           # 경로 = corpus.page_ref(doc_id), 되돌리기는 resolve_page_ref
        "nav_not_in_corpus": sorted(set(tree.nav_pages) - corpus_docs),
        "corpus_not_in_nav": sorted(corpus_docs - in_nav),
    }
    text = "\n".join(render(tree.nodes, corpus.page_ref)) + "\n"
    return IndexResult(text, entries, groups, flatten_doc_ids(tree.nodes), notes)


VARIANTS: dict[str, Callable[[Corpus], IndexResult]] = {
    "nav_v0": build_nav_v0,
}


PATH_AT_END = re.compile(r"\(([^()]*)\)$")


def check_paths(res: IndexResult, corpus: Corpus):
    """인덱스 본문의 모든 경로가 resolve_page_ref 로 원래 doc_id 에 1:1 로 돌아오는지 확인.
    실패하면 ValueError (인덱스 파일을 쓰기 전에 멈춘다)."""
    refs = [m.group(1) for ln in res.text.splitlines() if (m := PATH_AT_END.search(ln.rstrip()))]
    if len(refs) != len(res.doc_ids):
        raise ValueError(f"인덱스 경로 수 {len(refs)} != 항목 수 {len(res.doc_ids)}")
    ref_to_doc: dict[str, str] = {}
    doc_to_ref: dict[str, str] = {}
    for ref, expected in zip(refs, res.doc_ids):
        try:
            got = corpus.resolve_page_ref(ref)
        except KeyError as e:
            raise ValueError(f"인덱스 경로를 되돌릴 수 없습니다: {ref!r} ({e})") from None
        if got != expected:
            raise ValueError(f"인덱스 경로 {ref!r} -> {got}, 기대값 {expected}")
        if ref_to_doc.setdefault(ref, got) != got or doc_to_ref.setdefault(got, ref) != ref:
            raise ValueError(f"인덱스 경로와 doc_id 가 1:1 이 아닙니다: {ref!r} / {got}")


def build_index(name: str, corpus: Corpus | None = None) -> tuple[Path, IndexResult, dict]:
    """변형 name 을 만들어 data/index/{name}.md 와 {name}.meta.json 으로 쓴다.
    같은 코퍼스면 두 파일 모두 바이트 단위로 같다 (시각 등은 기록하지 않음)."""
    if name not in VARIANTS:
        raise KeyError(f"알 수 없는 인덱스 변형: {name}. 가능: {', '.join(VARIANTS)}")
    corpus = corpus or load_corpus()
    res = VARIANTS[name](corpus)
    check_paths(res, corpus)

    CFG.index_dir.mkdir(parents=True, exist_ok=True)
    path = CFG.index_dir / f"{name}.md"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(res.text)
    meta = {
        "variant": name,
        "corpus_source": corpus.source,
        "corpus_manifest_sha256": manifest_sha256(corpus),
        "entries": res.entries,
        "groups": res.groups,
        "tokens": count_tokens(res.text),
        **res.notes,
    }
    with open(CFG.index_dir / f"{name}.meta.json", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return path, res, meta


# ---------------- 진입점 ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="nav_v0", help="인덱스 변형 이름")
    ap.add_argument("--list", action="store_true", help="등록된 변형 목록")
    args = ap.parse_args()

    if args.list:
        for k, fn in VARIANTS.items():
            print(f"{k:10s} {(fn.__doc__ or '').strip().splitlines()[0]}")
        return

    path, res, meta = build_index(args.variant)
    strip = lambda ids: [i[len(DOCS_PREFIX):] if i.startswith(DOCS_PREFIX) else i for i in ids]
    print(f"인덱스   : {path.relative_to(CFG.root).as_posix()}  ({args.variant})")
    print(f"코퍼스   : {meta['corpus_source']}  (매니페스트 {meta['corpus_manifest_sha256'][:12]})")
    print(f"항목 수  : {meta['entries']}  (doc_id 없는 섹션 줄 {meta['groups']}개)")
    print(f"토큰 수  : {meta['tokens']:,}")
    for key, label in (("nav_not_in_corpus", "nav 에 있지만 코퍼스에 없는 페이지"),
                       ("corpus_not_in_nav", "코퍼스에 있지만 nav 에 없는 문서")):
        if key in meta:
            ids = strip(meta[key])
            print(f"\n{label}: {len(ids)}개")
            for i in ids:
                print(f"  {i}")


if __name__ == "__main__":
    main()
