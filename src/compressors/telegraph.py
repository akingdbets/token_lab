"""Telegraph English (TE) 압축 (사전 변환 방식, 탐색 실험)

TE (Arbuzov 외, arXiv:2605.04426) 는 문장을 원자 사실 줄과 기호(→ ∧ ¬ = …)로 다시 쓰는 LLM 압축이다.
위키 페이지를 페이지당 한 번 TE 로 바꿔 data/te_pages/ 에 저장해 두고(convert), 실험에서는 문맥의 각 문서
본문을 저장된 TE 본문으로 갈아 끼운다(TelegraphCompressor). 변환 비용은 페이지마다 한 번이라 문항 수로 상각한다.

프롬프트 (src/prompts/telegraph/)
    system = technical_rules_v1.md + compression_v5.txt (저자 공개 프롬프트 그대로, NOTICE.md)
    user   = 변환할 본문 조각 (저자 참고 구현과 같은 구조)
기술 문서용 규칙 (프롬프트와 후처리 양쪽)
    - 코드 블록(```)은 ⟦CODE-n⟧ 자리표시자로 빼서 보내고, 변환 뒤 원문 그대로 되돌린다.
      자리표시자가 빠지면 그 블록을 조각 끝에 붙이고 기록한다 (코드 블록은 항상 바이트 그대로 남는다)
    - "## Document:" 경계 줄은 변환에 보내지 않고 압축기가 그대로 둔다
    - 식별자는 원문 대소문자로 되돌린다 (TE 의 대문자 기본값을 식별자에는 적용하지 않음)
    - 숫자·버전·하이픈 이름·따옴표 값은 그대로 두라고 프롬프트에 적고, 사라진 것을 페이지별로 기록한다
조각: 코드 블록 자리표시자를 포함한 본문을 문단 단위로 CHUNK_WORDS 단어 이하로 나눈다.
    답이 출력 한도에 걸려 잘리면 그 조각을 반으로 나눠 다시 보낸다.

    EVAL_DIR=data/evalsets/claude-v1 python src/compressors/telegraph.py convert --split test   # 과금 (gpt-6-luna)
    EVAL_DIR=data/evalsets/claude-v1 python src/compressors/telegraph.py check --split test     # 점검만

data/te_pages/
    <페이지 파일>.te.md   TE 본문 (코드 블록 원문 포함)
    index.json           ref -> {file, source_sha256, prompt_hash, model, chunks, tokens, checks}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compressors.base import Compressor, PromptParts
from compressors.llmlingua2 import _split_fenced_blocks
from config import CFG

PROMPT_DIR = CFG.root / "src" / "prompts" / "telegraph"
TE_DIR = CFG.root / "data" / "te_pages"
CONVERT_MODEL = "gpt-6-luna"
CONVERT_MAX_TOKENS = 4096        # 생각 토큰 포함 (기본 설정과 같음)
CHUNK_WORDS = 500
MAX_SPLITS = 3                   # 잘린 조각을 반으로 나누는 최대 깊이
PLACEHOLDER = "⟦CODE-{}⟧"
_PLACEHOLDER = re.compile(r"⟦CODE-(\d+)⟧")
_HEADER = re.compile(r"^## Document: (.+)$", re.MULTILINE)
# 식별자 후보: 백틱 안, 또는 밑줄·숫자·점·안쪽 대문자가 있는 단어 (FastAPI, model_dump, OAuth2, pydantic.v1)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_IDENT = re.compile(r"(?<![\w.])[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?![\w])")
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)*(?![\w])")
_HYPHEN_NAME = re.compile(r"(?<![\w-])[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+(?![\w-])")
_QUOTED = re.compile(r'"([^"\n]{1,40})"')


def load_prompt() -> tuple[str, str]:
    """(system 메시지, 해시 앞 12자리)."""
    text = ((PROMPT_DIR / "technical_rules_v1.md").read_text(encoding="utf-8")
            + "\n" + (PROMPT_DIR / "compression_v5.txt").read_text(encoding="utf-8"))
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mask_code(text: str) -> tuple[str, list[str]]:
    """코드 블록을 자리표시자 줄로 바꾼다. (가린 본문, 코드 블록 원문 목록)."""
    blocks, out = [], []
    for is_code, part in _split_fenced_blocks(text):
        if is_code:
            out.append(PLACEHOLDER.format(len(blocks)) + "\n")
            blocks.append(part)
        else:
            out.append(part)
    return "".join(out), blocks


def chunks(masked: str, limit: int = CHUNK_WORDS) -> list[str]:
    """문단(빈 줄) 단위로 limit 단어 이하 조각. 한 문단이 limit 를 넘으면 그 문단 하나가 한 조각."""
    out, cur, n = [], [], 0
    for para in re.split(r"\n\s*\n", masked):
        w = len(para.split())
        if cur and n + w > limit:
            out.append("\n\n".join(cur))
            cur, n = [], 0
        cur.append(para)
        n += w
    if cur:
        out.append("\n\n".join(cur))
    return [c for c in out if c.strip()]


def identifiers(prose: str) -> set[str]:
    """식별자 후보 (대소문자를 되돌리고, 사라졌는지 볼 대상)."""
    out = set()
    for m in _INLINE_CODE.finditer(prose):
        out.update(t for t in _IDENT.findall(m.group(1)) if len(t) > 1)
    for t in _IDENT.findall(prose):
        if "_" in t or "." in t or any(c.isdigit() for c in t) or any(c.isupper() for c in t[1:]):
            out.add(t)
    return out


def restore_case(te: str, idents: set[str]) -> tuple[str, int]:
    """TE 출력에서 원문 식별자와 대소문자만 다른 단어를 원문 표기로 되돌린다.
    코드 블록을 되돌리기 전(자리표시자 상태)의 TE 에만 쓴다. 대소문자만 다른 원문 식별자가 둘 이상이면
    (fastapi / FastAPI) 어느 쪽인지 모르므로 건드리지 않는다."""
    by_lower: dict[str, set[str]] = {}
    for t in idents:
        by_lower.setdefault(t.lower(), set()).add(t)
    n = 0

    def fix(m):
        nonlocal n
        w = m.group(0)
        origs = by_lower.get(w.lower())
        if origs and len(origs) == 1 and w not in origs:
            n += 1
            return next(iter(origs))
        return w
    return _IDENT.sub(fix, te), n


def fact_tokens(prose: str) -> dict[str, set[str]]:
    """사라졌는지 볼 원문 토큰: 식별자, 숫자·버전, 하이픈 이름, 따옴표 값."""
    return {"identifiers": identifiers(prose), "numbers": set(_NUMBER.findall(prose)),
            "hyphen_names": {h for h in _HYPHEN_NAME.findall(prose) if any(c.isdigit() for c in h) or h.islower()},
            "quoted": set(_QUOTED.findall(prose))}


def check_page(source: str, te: str) -> dict:
    """코드 블록 바이트 일치, 원문 토큰 중 TE 에서 사라진 것."""
    src_code = [p for is_code, p in _split_fenced_blocks(source) if is_code]
    te_code = [p for is_code, p in _split_fenced_blocks(te) if is_code]
    prose = "".join(p for is_code, p in _split_fenced_blocks(source) if not is_code)
    te_prose = "".join(p for is_code, p in _split_fenced_blocks(te) if not is_code)
    missing = {}
    for kind, toks in fact_tokens(prose).items():
        if kind == "numbers":
            have = set(_NUMBER.findall(te_prose))
            missing[kind] = sorted(t for t in toks if t not in have)
        else:
            missing[kind] = sorted(t for t in toks if t not in te_prose)
    return {"code_blocks": len(src_code), "code_blocks_identical": src_code == te_code,
            "missing": missing, "missing_count": sum(len(v) for v in missing.values()),
            "source_count": sum(len(v) for v in fact_tokens(prose).values())}


def page_file(ref: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", ref.removesuffix(".md")) + ".te.md"


def load_index() -> dict:
    path = TE_DIR / "index.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


# ---------------- 변환 (과금) ----------------

def convert_chunk(llm, system: str, chunk: str, depth: int = 0) -> tuple[str, list[dict]]:
    """조각 하나를 변환. 잘리면 반으로 나눠 다시. (TE 텍스트, 호출 기록)."""
    res = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": chunk}])
    usage = (res.raw.get("usage") or {}) if res.raw else {}
    call = {"words": len(chunk.split()), "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
            "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "finish_reason": res.finish_reason, "depth": depth}
    text = (res.text or "").strip()
    if (res.finish_reason == "length" or not text) and depth < MAX_SPLITS:
        paras = re.split(r"\n\s*\n", chunk)
        if len(paras) < 2:      # 문단 하나면 줄 단위로 나눈다
            paras = chunk.splitlines()
        if len(paras) >= 2:
            half = len(paras) // 2
            a, ca = convert_chunk(llm, system, "\n\n".join(paras[:half]), depth + 1)
            b, cb = convert_chunk(llm, system, "\n\n".join(paras[half:]), depth + 1)
            return a + "\n" + b, [call, *ca, *cb]
    return text, [call]


def restore_code(te: str, blocks: list[str], wanted: list[int]) -> tuple[str, dict]:
    """조각의 자리표시자를 코드 블록 원문으로 되돌린다. 빠진 것은 끝에 붙이고, 중복·모르는 번호는 지운다."""
    seen, dup, unknown = [], 0, 0
    lines = []
    for line in te.splitlines():
        m = _PLACEHOLDER.search(line)
        if not m:
            lines.append(line)
            continue
        i = int(m.group(1))
        rest = _PLACEHOLDER.sub("", line).strip()
        if rest:                           # 자리표시자와 같은 줄에 붙은 TE 는 따로 남긴다
            lines.append(rest)
        if i not in wanted:
            unknown += 1
        elif i in seen:
            dup += 1
        else:
            seen.append(i)
            lines.append(blocks[i].rstrip("\n"))
    missing = [i for i in wanted if i not in seen]
    for i in missing:
        lines.append(blocks[i].rstrip("\n"))
    reordered = seen != sorted(seen)
    return "\n".join(lines), {"missing": missing, "duplicate": dup, "unknown": unknown, "reordered": reordered}


def convert_page(llm, system: str, text: str) -> tuple[str, dict]:
    masked, blocks = mask_code(text)
    prose = "".join(p for is_code, p in _split_fenced_blocks(text) if not is_code)
    idents = identifiers(prose)
    outs, calls, fixes, n_case = [], [], {"missing": [], "duplicate": 0, "unknown": 0, "reordered": 0}, 0
    for ch in chunks(masked):
        wanted = [int(i) for i in _PLACEHOLDER.findall(ch)]
        te, cs = convert_chunk(llm, system, ch)
        te, n = restore_case(te, idents)          # 코드 블록을 되돌리기 전에: 코드는 건드리지 않는다
        n_case += n
        te, fx = restore_code(te, blocks, wanted)
        outs.append(te)
        calls += cs
        fixes["missing"] += fx["missing"]
        fixes["duplicate"] += fx["duplicate"]
        fixes["unknown"] += fx["unknown"]
        fixes["reordered"] += int(fx["reordered"])
    return "\n".join(outs), {"calls": calls, "placeholder_fixes": fixes, "case_restored": n_case}


def cmd_convert(args) -> None:
    from experiment import load_corpus, load_items
    from llm import LLM

    system, phash = load_prompt()
    corpus = load_corpus()
    items = load_items(args.split, None, None)
    pages = sorted({p for it in items for p in it["evidence_pages"]})
    TE_DIR.mkdir(parents=True, exist_ok=True)
    index = load_index()
    llm = LLM(model=CONVERT_MODEL, max_tokens=CONVERT_MAX_TOKENS)   # 기본 설정: temperature·reasoning_effort 안 보냄
    print(f"변환 {len(pages)} 페이지, 프롬프트 {phash}, {llm.sampling_info()}", flush=True)
    for n, doc_id in enumerate(pages, 1):
        ref = corpus.page_ref(doc_id)
        text = corpus.expanded_text(doc_id).strip()
        old = index.get(ref)
        if old and old["source_sha256"] == sha(text) and old["prompt_hash"] == phash and (TE_DIR / old["file"]).exists():
            continue                        # 같은 원문·프롬프트로 이미 변환함 (재사용)
        te, rec = convert_page(llm, system, text)
        (TE_DIR / page_file(ref)).write_text(te + "\n", encoding="utf-8")
        calls = rec["calls"]
        index[ref] = {"file": page_file(ref), "doc_id": doc_id, "source_sha256": sha(text), "prompt_hash": phash,
                      "model": CONVERT_MODEL, "sampling": llm.sampling_info(), "chunks": len(calls),
                      "prompt_tokens": sum(c["prompt_tokens"] for c in calls),
                      "completion_tokens": sum(c["completion_tokens"] for c in calls),
                      "reasoning_tokens": sum(c["reasoning_tokens"] or 0 for c in calls),
                      "truncated_calls": sum(c["finish_reason"] == "length" for c in calls),
                      "calls": calls, "placeholder_fixes": rec["placeholder_fixes"],
                      "case_restored": rec["case_restored"], "checks": check_page(text, te)}
        (TE_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        r = index[ref]
        print(f"[{n}/{len(pages)}] {ref}: 조각 {r['chunks']}, 입력 {r['prompt_tokens']} 출력 {r['completion_tokens']} "
              f"(생각 {r['reasoning_tokens']}), 잘림 {r['truncated_calls']}, 코드 블록 일치 "
              f"{r['checks']['code_blocks_identical']}, 사라진 토큰 {r['checks']['missing_count']}", flush=True)
    cmd_check(args)


def cmd_check(args) -> None:
    from experiment import build_context, load_corpus, load_items
    from llm import count_tokens

    corpus = load_corpus()
    items = load_items(args.split, None, None)
    index = load_index()
    pages = sorted({p for it in items for p in it["evidence_pages"]})
    src_tok = te_tok = 0
    for doc_id in pages:
        ref = corpus.page_ref(doc_id)
        text = corpus.expanded_text(doc_id).strip()
        r = index.get(ref)
        if not r:
            print("변환 안 됨", ref)
            continue
        te = (TE_DIR / r["file"]).read_text(encoding="utf-8").strip()
        r["checks"] = check_page(text, te)
        r["stale"] = r["source_sha256"] != sha(text)
        src_tok += count_tokens(text)
        te_tok += count_tokens(te)
    bad_ctx = []
    comp = TelegraphCompressor()
    for it in items:
        ctx = build_context(corpus, it)
        out = comp.compress(PromptParts(system="", context=ctx, question=it["question"])).context
        if len(_HEADER.findall(out)) != len(_HEADER.findall(ctx)):
            bad_ctx.append(it["id"])
    (TE_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    rs = [index[corpus.page_ref(p)] for p in pages if corpus.page_ref(p) in index]
    print(f"페이지 {len(rs)}/{len(pages)}, 원문 {src_tok} -> TE {te_tok} 토큰 ({100 * (1 - te_tok / src_tok):.1f}% 절감)")
    print(f"코드 블록 바이트 불일치 {sum(not r['checks']['code_blocks_identical'] for r in rs)}, "
          f"원문 대체 필요(stale) {sum(r.get('stale', False) for r in rs)}, 문서 경계 수 다른 문항 {bad_ctx}")
    print(f"사라진 토큰 합 {sum(r['checks']['missing_count'] for r in rs)} / 원문 {sum(r['checks']['source_count'] for r in rs)}, "
          f"잘린 호출 {sum(r['truncated_calls'] for r in rs)}, 자리표시자 보정 "
          f"{sum(len(r['placeholder_fixes']['missing']) for r in rs)} 누락 / {sum(r['placeholder_fixes']['duplicate'] for r in rs)} 중복")
    print(f"변환 토큰 합: 입력 {sum(r['prompt_tokens'] for r in rs)}, 출력 {sum(r['completion_tokens'] for r in rs)} "
          f"(생각 {sum(r['reasoning_tokens'] for r in rs)})")


# ---------------- 압축기 ----------------

class TelegraphCompressor(Compressor):
    """문맥의 각 "## Document: <ref>" 본문을 data/te_pages 의 TE 본문으로 갈아 끼운다 (경계 줄은 그대로).
    저장된 변환이 없거나 원문이 바뀌었으면(source_sha256 불일치) 멈춘다 (원문으로 조용히 대체하지 않음)."""
    name = "te"
    targets = ("context",)

    def __init__(self, name: str = "te"):
        self.name = name
        self._index = None

    def compress_context(self, question: str, context: str) -> str:
        if self._index is None:
            self._index = load_index()
        heads = list(_HEADER.finditer(context))
        if not heads:
            raise ValueError("te: 문맥에 '## Document:' 경계가 없습니다")
        out, pages = [], []
        for k, h in enumerate(heads):
            end = heads[k + 1].start() if k + 1 < len(heads) else len(context)
            body = context[h.end():end].strip()
            ref = h.group(1).strip()
            r = self._index.get(ref)
            if r is None:
                raise KeyError(f"te: {ref} 의 TE 변환이 없습니다 (telegraph.py convert 먼저)")
            if r["source_sha256"] != sha(body):
                raise ValueError(f"te: {ref} 원문이 변환 때와 다릅니다 (다시 변환 필요)")
            te = (TE_DIR / r["file"]).read_text(encoding="utf-8").strip()
            out.append(f"## Document: {ref}\n\n{te}")
            pages.append(ref)
        self.add_info(te_pages=pages, prompt_hash=self._index[pages[0]]["prompt_hash"])
        return "\n\n".join(out)

    def config(self) -> dict:
        _, phash = load_prompt()
        return {"method": "telegraph-english (사전 변환)", "prompt_hash": phash, "convert_model": CONVERT_MODEL,
                "chunk_words": CHUNK_WORDS, "convert_max_tokens": CONVERT_MAX_TOKENS,
                "prompt": "technical_rules_v1.md + compression_v5.txt (sibmike/telegrapher 7aadc09)"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("convert", "check"):
        a = sub.add_parser(name)
        a.add_argument("--split", default="test")
    args = ap.parse_args()
    {"convert": cmd_convert, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    main()
