"""
평가 데이터셋 생성

위키 문서를 LLM에 주고 질문-정답 후보를 뽑은 뒤, 자동 검증을 거쳐
data/eval/qa_dataset.json 으로 저장한다. 최종 확정은 사람 검수를 거친다.

사용법
    python src/dataset_builder.py                      # 기본: 문서 30개 x 2문항
    python src/dataset_builder.py --docs 50 --per-doc 3
    python src/dataset_builder.py --docs 3 --per-doc 2 --dry-run   # 화면 출력만

검수
    python src/dataset_builder.py --review             # 대화형 검수 모드
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CFG
from llm import LLM, count_tokens

# ---------------- 프롬프트 ----------------

GEN_SYSTEM = (
    "You create factual question-answer pairs for evaluating document-grounded QA systems. "
    "You output only valid JSON."
)

GEN_PROMPT = """Below is a technical documentation page.

Create {n} FACT-CHECKING questions that can be answered from this page.

Requirements for each question:
- The answer must be a specific, verifiable fact stated explicitly in the page
  (a default value, a parameter name, a type, a number, a keyword, a term definition).
- The answer must be SHORT: at most 15 words.
- The question must be answerable WITHOUT seeing the page title, so include enough
  context in the question itself (e.g. "In FastAPI, what is the default value of X?").
- Each question must target a DIFFERENT fact.
- Include in "evidence" the exact sentence or code line from the page that proves the answer.

FORBIDDEN — do not produce questions like these:
- The answer appears inside the question itself.
  BAD: Q "What did FastAPI 0.119.0 introduce?" A "FastAPI 0.119.0"
- The answer is general knowledge that does not need this page.
  BAD: Q "What language is FastAPI written in?" A "Python"
- The answer is a whole sentence of prose, or is vague ("it depends", "several options").
- The question is about the document itself ("what does this page explain?").
- The question asks why, or asks for an opinion or comparison.

GOOD examples:
- Q "In FastAPI, what is the default value of the limit query parameter in the example?" A "10"
- Q "Which FastAPI class is used to declare a request body parameter as a form field?" A "Form"
- Q "What HTTP status code does FastAPI return by default for a successful POST route?" A "200"

Output ONLY a JSON array, no markdown fences, no explanation:
[
  {{"question": "...", "answer": "...", "evidence": "..."}}
]

--- DOCUMENT START ---
{doc}
--- DOCUMENT END ---"""

VERIFY_PROMPT = """Below is a document and a question-answer pair.

Check ALL of the following:
1. The answer is explicitly stated in the document.
2. The question is answerable using only the document.
3. The answer is specific and short, not vague.
4. The answer does NOT already appear inside the question text.

Output ONLY one word: VALID or INVALID

--- DOCUMENT ---
{doc}
--- QUESTION ---
{q}
--- PROPOSED ANSWER ---
{a}"""

CLOSED_BOOK_PROMPT = """Answer the question from your own knowledge. Be brief.
If you do not know, reply exactly: UNKNOWN

Question: {q}"""


# ---------------- 유틸 ----------------

def strip_header(text: str) -> str:
    """위키 머리말(> 출처/요약/목차/핵심 용어)을 제거한 본문."""
    lines = text.split("\n")
    out, started = [], False
    for ln in lines:
        if not started and (ln.startswith(("# ", ">")) or not ln.strip()):
            continue
        started = True
        out.append(ln)
    return "\n".join(out).strip()


def parse_json_array(text: str) -> list[dict]:
    """LLM 출력에서 JSON 배열만 뽑아낸다."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict)]


def pick_documents(n: int, min_tokens: int, max_tokens: int, seed: int,
                   prefix: str = "") -> list[Path]:
    """길이가 적당한 문서를 고른다. prefix가 주어지면 해당 폴더를 우선한다."""
    docs = []
    for p in sorted(CFG.wiki_dir.rglob("*.md")):
        t = count_tokens(p.read_text(encoding="utf-8"))
        if min_tokens <= t <= max_tokens:
            docs.append(p)

    rng = random.Random(seed)
    if prefix:
        rels = {p: str(p.relative_to(CFG.wiki_dir)).replace("\\", "/") for p in docs}
        wanted = [p for p in docs if rels[p].startswith(prefix)]
        rest = [p for p in docs if not rels[p].startswith(prefix)]
        rng.shuffle(wanted)
        rng.shuffle(rest)
        docs = wanted + rest          # 우선 폴더를 앞에 배치
    else:
        rng.shuffle(docs)
    return docs[:n]


# ---------------- 생성 ----------------

def answer_leaks_into_question(q: str, a: str) -> bool:
    """정답이 질문 안에 그대로 들어 있으면 순환 질문."""
    a_norm = re.sub(r"[^a-z0-9.]+", "", a.lower())
    q_norm = re.sub(r"[^a-z0-9.]+", "", q.lower())
    if len(a_norm) < 3:
        return False
    return a_norm in q_norm


def generate_for_doc(llm: LLM, path: Path, n: int, verify: bool,
                     closed_book: bool = True, retries: int = 2) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    body = strip_header(raw)
    rel = str(path.relative_to(CFG.wiki_dir)).replace("\\", "/")

    items = []
    for attempt in range(retries + 1):
        res = llm.ask(GEN_PROMPT.format(n=n, doc=body), system=GEN_SYSTEM)
        items = parse_json_array(res.text)
        if items:
            break

    out = []
    for it in items:
        q = str(it.get("question", "")).strip()
        a = str(it.get("answer", "")).strip()
        ev = str(it.get("evidence", "")).strip()
        if not q or not a:
            continue
        if len(a.split()) > 20:          # 너무 긴 답은 사실 확인형이 아님
            continue
        if answer_leaks_into_question(q, a):
            continue                      # 질문에 답이 들어 있는 순환 질문 제외

        item = {
            "id": "",
            "question": q,
            "answer": a,
            "evidence": ev,
            "source_file": rel,
            "type": "fact",
            "doc_tokens": count_tokens(raw),
            "verified": None,
            "closed_book_ok": None,
            "human_checked": False,
        }

        if verify:
            v = llm.ask(VERIFY_PROMPT.format(doc=body, q=q, a=a))
            item["verified"] = v.text.strip().upper().startswith("VALID")

        if closed_book:
            # 문서 없이도 맞히는 질문이면 압축 실험에 쓸 수 없다
            cb = llm.ask(CLOSED_BOOK_PROMPT.format(q=q))
            cb_text = cb.text.strip()
            a_norm = re.sub(r"[^a-z0-9.]+", "", a.lower())
            cb_norm = re.sub(r"[^a-z0-9.]+", "", cb_text.lower())
            knows = len(a_norm) >= 2 and a_norm in cb_norm
            item["closed_book_ok"] = not knows   # True면 문서가 필요한 좋은 질문

        out.append(item)
    return out


def cmd_generate(args):
    llm = LLM()
    print(f"설정: {CFG.summary()}")

    docs = pick_documents(args.docs, args.min_tokens, args.max_tokens,
                          args.seed, args.prefix)
    if not docs:
        raise SystemExit("조건에 맞는 문서가 없습니다. --min-tokens / --max-tokens / --prefix 확인")
    print(f"대상 문서 {len(docs)}개, 문서당 {args.per_doc}문항 생성\n")

    all_items = []
    for i, p in enumerate(docs, 1):
        rel = str(p.relative_to(CFG.wiki_dir)).replace("\\", "/")
        print(f"[{i}/{len(docs)}] {rel}", end=" ", flush=True)
        try:
            items = generate_for_doc(llm, p, args.per_doc,
                                     verify=not args.no_verify,
                                     closed_book=not args.no_closed_book)
        except Exception as e:
            print(f"-> 실패: {e}")
            continue
        ok = sum(1 for x in items if x["verified"] is not False
                 and x["closed_book_ok"] is not False)
        print(f"-> {len(items)}문항 (통과 {ok})")
        all_items.extend(items)

        if args.dry_run:
            for x in items:
                flag = "OK " if (x["verified"] is not False
                                 and x["closed_book_ok"] is not False) else "제외"
                print(f"    [{flag}] Q: {x['question']}")
                print(f"           A: {x['answer']}"
                      f"  (검증={x['verified']}, 문서필요={x['closed_book_ok']})")

    # 검증 실패 또는 문서 없이도 맞히는 항목 제외
    kept = [x for x in all_items
            if x["verified"] is not False and x["closed_book_ok"] is not False]
    for i, x in enumerate(kept, 1):
        x["id"] = f"q{i:04d}"

    if args.dry_run:
        print(f"\n[dry-run] 생성 {len(all_items)} / 유지 {len(kept)} — 저장하지 않음")
        return

    CFG.eval_dir.mkdir(parents=True, exist_ok=True)
    out_path = CFG.eval_dir / "qa_dataset.json"
    out_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n생성 {len(all_items)}문항 -> 검증 통과 {len(kept)}문항")
    print(f"저장: {out_path}")
    print("\n※ 다음 단계: python src/dataset_builder.py --review 로 사람 검수를 진행하세요.")


# ---------------- 검수 ----------------

def cmd_review(args):
    path = CFG.eval_dir / "qa_dataset.json"
    if not path.exists():
        raise SystemExit("qa_dataset.json이 없습니다. 먼저 생성하세요.")

    items = json.loads(path.read_text(encoding="utf-8"))
    todo = [x for x in items if not x["human_checked"]]
    if not todo:
        print("검수할 항목이 없습니다.")
        return

    print(f"검수 대기 {len(todo)}문항. [Enter]=통과  d=삭제  e=답 수정  q=저장 후 종료\n")
    removed = 0
    for i, x in enumerate(todo, 1):
        print(f"--- [{i}/{len(todo)}] {x['source_file']}")
        print(f"Q: {x['question']}")
        print(f"A: {x['answer']}")
        if x["evidence"]:
            print(f"근거: {x['evidence'][:160]}")
        cmd = input("> ").strip().lower()

        if cmd == "q":
            break
        if cmd == "d":
            x["_delete"] = True
            removed += 1
        elif cmd == "e":
            new = input("  새 정답: ").strip()
            if new:
                x["answer"] = new
            x["human_checked"] = True
        else:
            x["human_checked"] = True
        print()

    items = [x for x in items if not x.get("_delete")]
    for i, x in enumerate(items, 1):
        x["id"] = f"q{i:04d}"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    checked = sum(1 for x in items if x["human_checked"])
    print(f"저장 완료: 전체 {len(items)}문항 (검수 완료 {checked}, 삭제 {removed})")


# ---------------- 통계 ----------------

def cmd_stats(args):
    path = CFG.eval_dir / "qa_dataset.json"
    if not path.exists():
        raise SystemExit("qa_dataset.json이 없습니다.")
    items = json.loads(path.read_text(encoding="utf-8"))
    files = {x["source_file"] for x in items}
    checked = sum(1 for x in items if x["human_checked"])
    toks = [x["doc_tokens"] for x in items]
    print(f"문항 수    : {len(items)}")
    print(f"출처 문서  : {len(files)}개")
    print(f"사람 검수  : {checked}/{len(items)}")
    if toks:
        print(f"문서 길이  : 평균 {sum(toks)//len(toks)} / 최소 {min(toks)} / 최대 {max(toks)} 토큰")


# ---------------- 진입점 ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=int, default=30, help="대상 문서 수")
    ap.add_argument("--per-doc", type=int, default=2, help="문서당 문항 수")
    ap.add_argument("--min-tokens", type=int, default=600, help="너무 짧은 문서 제외")
    ap.add_argument("--max-tokens", type=int, default=6000, help="너무 긴 문서 제외")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--prefix", default="tutorial/",
                    help="우선할 문서 폴더 (예: tutorial/). 빈 값이면 전체 무작위")
    ap.add_argument("--no-verify", action="store_true", help="LLM 자동 검증 생략(빠름)")
    ap.add_argument("--no-closed-book", action="store_true",
                    help="문서 없이도 맞히는 질문 걸러내기 생략(빠름)")
    ap.add_argument("--dry-run", action="store_true", help="저장하지 않고 화면 출력만")
    ap.add_argument("--review", action="store_true", help="대화형 검수 모드")
    ap.add_argument("--stats", action="store_true", help="현재 평가셋 통계")
    args = ap.parse_args()

    if args.review:
        cmd_review(args)
    elif args.stats:
        cmd_stats(args)
    else:
        cmd_generate(args)


if __name__ == "__main__":
    main()