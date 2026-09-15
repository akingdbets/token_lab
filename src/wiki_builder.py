"""
FastAPI 공식 문서(.md) -> LLM Wiki 변환 스크립트

하는 일
  1) 코드 참조 {* path *} 를 실제 소스 코드로 펼침
  2) 앵커 { #id }, HTML 태그 등 LLM에 불필요한 요소 제거
  3) 페이지마다 메타정보(제목, 핵심용어, 원본경로) 머리말 부착
  4) 원문 대비 토큰 감소량을 stats.csv 로 기록

사용법
  python wiki_builder.py --src ./fastapi --out ./data/wiki
"""

import argparse
import csv
import re
from pathlib import Path

# ---------- 토큰 계산 ----------
try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:
    # tiktoken 미설치 시 대략치 (영어 기준 약 4글자 = 1토큰)
    def count_tokens(text: str) -> int:
        return len(text) // 4


# ---------- 개별 변환 규칙 ----------

CODE_REF = re.compile(r"\{\*\s*(\S+?\.py)(?:\s+[^*]*?)?\s*\*\}")
ANCHOR = re.compile(r"\s*\{\s*#[\w\-]+\s*\}")
DFN = re.compile(r'<dfn title="(.*?)">(.*?)</dfn>', re.S)
HTML_TAG = re.compile(
    r"</?(?:div|span|p|br|abbr|small|details|summary|font|kbd|sup|sub|em|strong|a|img|table|tr|td|th|ul|li|code|pre)[^>]*>"
)
BLANKS = re.compile(r"\n{3,}")


def resolve_code_path(rel: str, md_path: Path, repo_root: Path) -> Path | None:
    """코드 참조 경로를 실제 파일 위치로 해석.

    문서의 상대 경로(../../docs_src/...)는 빌드 설정 기준이라 파일 시스템과
    맞지 않는 경우가 있어, 여러 후보를 순서대로 시도한다.
    """
    rel = rel.lstrip("./")
    candidates = [
        (md_path.parent / rel),                 # 문서 기준 상대 경로 (원래 방식)
        repo_root / rel,                        # 저장소 루트 기준
    ]
    # ../ 를 걷어낸 뒤 루트 기준으로도 시도 (../../docs_src/x.py -> docs_src/x.py)
    stripped = re.sub(r"^(\.\./)+", "", rel)
    candidates.append(repo_root / stripped)

    for c in candidates:
        try:
            c = c.resolve()
        except OSError:
            continue
        if c.is_file():
            return c

    # 마지막 수단: 파일명으로 저장소 안을 검색
    name = Path(stripped).name
    for found in repo_root.rglob(name):
        if found.is_file():
            return found
    return None


def expand_code_refs(text: str, md_path: Path, repo_root: Path,
                     keep_missing: bool = True) -> tuple[str, int]:
    """{* ../../docs_src/x.py hl[9] *} 를 실제 코드 블록으로 치환."""
    missing = 0

    def repl(m):
        nonlocal missing
        rel = m.group(1)
        src = resolve_code_path(rel, md_path, repo_root)
        if src is None:
            missing += 1
            return f"[코드 파일 없음: {rel}]" if keep_missing else ""
        code = src.read_text(encoding="utf-8").strip()
        return f"```python\n{code}\n```"

    return CODE_REF.sub(repl, text), missing


def strip_noise(text: str, keep_dfn_title: bool = True) -> str:
    """LLM에 불필요한 형식 요소 제거."""
    text = ANCHOR.sub("", text)                      # { #anchor }
    if keep_dfn_title:
        # <dfn title="설명">용어</dfn>  ->  용어(설명)
        text = DFN.sub(lambda m: f"{m.group(2)}({m.group(1).strip()})", text)
    else:
        text = DFN.sub(lambda m: m.group(2), text)
    text = HTML_TAG.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)           # 줄 끝 공백
    text = BLANKS.sub("\n\n", text)                  # 연속 빈 줄
    return text.strip()


# ---------- 메타정보 ----------

def extract_title(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else fallback


def extract_headings(text: str, limit: int = 8) -> list[str]:
    return [h.strip() for h in re.findall(r"^##\s+(.+)$", text, re.M)][:limit]


def extract_entities(text: str, limit: int = 15) -> list[str]:
    """백틱으로 감싼 코드 토큰 = 핵심 엔티티 후보."""
    found = re.findall(r"`([^`\n]{1,40})`", text)
    seen, out = set(), []
    for f in found:
        f = f.strip()
        if f and f not in seen:
            seen.add(f)
            out.append(f)
        if len(out) >= limit:
            break
    return out


def first_paragraph(text: str, max_len: int = 200) -> str:
    body = re.sub(r"^#.*$", "", text, flags=re.M).strip()
    for para in body.split("\n\n"):
        para = para.strip()
        if para and not para.startswith(("```", "*", "-", "|", ">")):
            para = re.sub(r"\s+", " ", para)
            return para[:max_len] + ("..." if len(para) > max_len else "")
    return ""


def build_header(title, rel_path, summary, headings, entities) -> str:
    lines = [
        f"# {title}",
        "",
        f"> 출처: {rel_path}",
    ]
    if summary:
        lines.append(f"> 요약: {summary}")
    if headings:
        lines.append(f"> 목차: {' / '.join(headings)}")
    if entities:
        lines.append(f"> 핵심 용어: {', '.join(entities)}")
    lines.append("")
    return "\n".join(lines)


# ---------- 메인 ----------

def convert_one(md_path: Path, docs_root: Path, out_root: Path, repo_root: Path, args) -> dict | None:
    raw = md_path.read_text(encoding="utf-8")
    raw_tokens = count_tokens(raw)

    text, missing = expand_code_refs(raw, md_path, repo_root,
                                     keep_missing=not args.drop_missing)
    text = strip_noise(text, keep_dfn_title=not args.drop_dfn)

    rel = md_path.relative_to(docs_root)
    title = extract_title(text, fallback=md_path.stem.replace("-", " ").title())

    # 본문에서 최상위 제목 줄은 헤더로 옮기므로 제거
    body = re.sub(r"^#\s+.+$", "", text, count=1, flags=re.M).strip()

    if count_tokens(body) < args.min_tokens:
        return None  # 목차 페이지 등 내용이 거의 없는 문서는 제외

    header = build_header(
        title=title,
        rel_path=str(rel).replace("\\", "/"),
        summary=first_paragraph(body),
        headings=extract_headings(body),
        entities=extract_entities(body),
    )
    wiki = header + "\n" + body + "\n"

    out_path = out_root / rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(wiki, encoding="utf-8")

    wiki_tokens = count_tokens(wiki)
    return {
        "file": str(rel).replace("\\", "/"),
        "title": title,
        "raw_tokens": raw_tokens,
        "wiki_tokens": wiki_tokens,
        "delta": wiki_tokens - raw_tokens,
        "reduction_pct": round((1 - wiki_tokens / raw_tokens) * 100, 2) if raw_tokens else 0,
        "missing_code_refs": missing,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="./fastapi", help="clone한 fastapi 저장소 경로")
    ap.add_argument("--out", default="./data/wiki", help="위키 출력 경로")
    ap.add_argument("--lang", default="en", help="문서 언어 폴더 (en, ko 등)")
    ap.add_argument("--min-tokens", type=int, default=150,
                    help="이 토큰 수 미만 문서는 제외 (목차 페이지 거르기)")
    ap.add_argument("--drop-dfn", action="store_true", help="dfn 설명문을 버림")
    ap.add_argument("--drop-missing", action="store_true", help="없는 코드 참조를 표시 없이 삭제")
    args = ap.parse_args()

    docs_root = Path(args.src) / "docs" / args.lang / "docs"
    if not docs_root.exists():
        raise SystemExit(f"문서 경로를 찾을 수 없습니다: {docs_root}")

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    repo_root = Path(args.src).resolve()

    # 기술 설명 문서가 아닌 페이지(변경 이력, 프로젝트 안내 등) 제외
    EXCLUDE = {
        "release-notes.md", "newsletter.md", "help-fastapi.md", "contributing.md",
        "benchmarks.md", "history-design-future.md", "external-links.md",
        "fastapi-people.md", "project-generation.md", "management.md",
        "management-tasks.md", "alternatives.md", "resources.md",
    }

    rows, skipped, excluded = [], 0, 0
    for md in sorted(docs_root.rglob("*.md")):
        rel_str = str(md.relative_to(docs_root)).replace("\\", "/")
        if md.name in EXCLUDE or rel_str.startswith(("about/", "learn/")):
            excluded += 1
            continue
        try:
            row = convert_one(md, docs_root, out_root, repo_root, args)
        except Exception as e:
            print(f"  [실패] {md.name}: {e}")
            continue
        if row is None:
            skipped += 1
        else:
            rows.append(row)

    if not rows:
        raise SystemExit("변환된 문서가 없습니다.")

    with (out_root.parent / "wiki_stats.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    raw_sum = sum(r["raw_tokens"] for r in rows)
    wiki_sum = sum(r["wiki_tokens"] for r in rows)
    missing_sum = sum(r["missing_code_refs"] for r in rows)

    print(f"\n변환 완료: {len(rows)}개 "
          f"(내용 부족 제외 {skipped}개, 대상 외 문서 제외 {excluded}개)")
    print(f"원문 합계 : {raw_sum:,} 토큰")
    print(f"위키 합계 : {wiki_sum:,} 토큰  ({(1 - wiki_sum / raw_sum) * 100:+.1f}%)")
    if missing_sum:
        print(f"※ 찾지 못한 코드 참조 {missing_sum}건 (경로 확인 필요)")
    print(f"통계 파일 : {out_root.parent / 'wiki_stats.csv'}")


if __name__ == "__main__":
    main()