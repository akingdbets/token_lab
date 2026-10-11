"""
검수표 반영

사람이 채운 검수표(CSV)를 읽어 평가셋에 반영한다. 검수표는 dev 사전 점검 때 만든
data/evalsets/<이름>/review/review_<split>_v<n>.csv 형식이다 (UTF-8 BOM, 엑셀에서 편집).

verdict 별 처리
    keep     human_checked = True
    edit     final_* 칸이 채워진 필드만 교체 (비어 있으면 기존 값 유지), human_checked = True
             final_answer         -> answer
             final_key_facts      -> key_facts     (한 칸 안에서 줄바꿈으로 구분)
             final_key_entities   -> key_entities  (한 칸 안에서 줄바꿈으로 구분)
             final_question       -> question      (질문 수정: 기존 결과는 답변부터 재실행 대상)
    delete   문항 제거, qa_meta.json 의 deleted 에 번호 기록 (번호는 재사용하지 않는다)
    (빈칸)   건드리지 않고 목록으로 출력

모든 변경은 검수표 옆 review_log_v<n>.jsonl 에 한 줄씩 남긴다 (qid, verdict, 전후 값, reviewer).
반영 후 split x type 문항 수와, 기존 실험 결과(results/runs) 중 다시 돌려야 할 것을 안내한다.
    질문 수정·삭제      -> 그 문항이 든 실행은 답변부터 다시 (재실행)
    정답·key_facts 수정 -> 답변은 그대로 두고 채점만 다시 (재채점)
    key_entities 수정   -> 엔티티 보존율만 다시 계산 (LLM 호출 없음)

사용법
    EVAL_DIR=data/evalsets/claude-v1 python src/apply_review.py data/evalsets/claude-v1/review/review_dev_v1.csv --dry-run
    EVAL_DIR=data/evalsets/claude-v1 python src/apply_review.py data/evalsets/claude-v1/review/review_dev_v1.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CFG
from dataset_builder import TYPES, load_dataset, save_dataset

VERDICTS = ("keep", "edit", "delete")
# 검수표 열 -> 평가셋 필드, 목록 필드 여부
EDITABLE = {
    "final_question": ("question", False),
    "final_answer": ("answer", False),
    "final_key_facts": ("key_facts", True),
    "final_key_entities": ("key_entities", True),
}


def split_lines(cell: str) -> list[str]:
    return [s.strip() for s in cell.replace("\r\n", "\n").split("\n") if s.strip()]


def read_sheet(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or "qid" not in rows[0] or "verdict" not in rows[0]:
        sys.exit(f"검수표 형식이 아닙니다 (qid, verdict 열 필요): {path}")
    return rows


def log_path_for(sheet: Path) -> Path:
    m = re.search(r"_v(\d+)$", sheet.stem)
    return sheet.with_name(f"review_log_v{m.group(1) if m else 1}.jsonl")


def apply(rows: list[dict], items: list[dict], meta: dict, sheet: Path):
    """(바뀐 평가셋, 로그 항목, 빈 verdict qid, 오류)"""
    by_id = {x["id"]: x for x in items}
    logs, blank, errors, deleted = [], [], [], set()
    now = datetime.now().isoformat(timespec="seconds")
    seen = set()
    for n, r in enumerate(rows, 2):         # 엑셀 기준 줄 번호 (1행은 머리글)
        qid = (r.get("qid") or "").strip()
        verdict = (r.get("verdict") or "").strip().lower()
        reviewer = (r.get("reviewer") or "").strip() or None
        if not qid:
            continue
        if qid in seen:
            errors.append(f"{n}행 {qid}: 검수표에 같은 문항이 두 번 있음")
            continue
        seen.add(qid)
        if not verdict:
            blank.append(qid)
            continue
        if verdict not in VERDICTS:
            errors.append(f"{n}행 {qid}: 알 수 없는 verdict ({verdict})")
            continue
        x = by_id.get(qid)
        if x is None:
            errors.append(f"{n}행 {qid}: 평가셋에 없는 문항 (이미 삭제됐거나 번호 오류)")
            continue
        entry = {"time": now, "sheet": sheet.as_posix(), "qid": qid, "verdict": verdict,
                 "reviewer": reviewer, "note": (r.get("note") or "").strip() or None}

        if verdict == "delete":
            entry["before"] = {k: x[k] for k in ("question", "answer", "key_facts", "key_entities")}
            entry["after"] = None
            deleted.add(qid)
        else:
            before, after = {}, {}
            if verdict == "edit":
                for col, (field, is_list) in EDITABLE.items():
                    cell = (r.get(col) or "").strip()
                    if not cell:
                        continue
                    new = split_lines(cell) if is_list else cell
                    if new != x[field]:
                        before[field], after[field] = x[field], new
                        x[field] = new
                if not after:
                    entry["warning"] = "edit 인데 바뀐 필드 없음 (final_* 칸이 비었거나 기존 값과 같음)"
            if not x.get("human_checked"):
                before["human_checked"], after["human_checked"] = x.get("human_checked"), True
            x["human_checked"] = True
            entry["before"], entry["after"] = before, after
        logs.append(entry)

    if deleted:
        items = [x for x in items if x["id"] not in deleted]
        meta["deleted"].extend(sorted(deleted))
    return items, logs, blank, errors


def print_table(items: list[dict]):
    print(f"\n{'':8s}" + "".join(f"{t:>11s}" for t in TYPES) + f"{'합계':>8s}")
    for s in ("dev", "test"):
        c = Counter(x["type"] for x in items if x["split"] == s)
        print(f"{s:8s}" + "".join(f"{c[t]:11d}" for t in TYPES) + f"{sum(c.values()):10d}")


def rerun_guide(logs: list[dict]):
    """바뀐 문항이 든 기존 실행 결과와 필요한 조치."""
    need: dict[str, str] = {}
    for e in logs:
        changed = set((e.get("after") or {}).keys()) - {"human_checked"}
        if e["verdict"] == "delete" or "question" in changed:
            need[e["qid"]] = "재실행"
        elif changed & {"answer", "key_facts"}:
            need[e["qid"]] = "재채점"
        elif "key_entities" in changed:
            need[e["qid"]] = "엔티티 보존율 재계산"
    if not need:
        print("\n기존 실험 결과에 영향 없음 (질문·정답·key_facts·key_entities 변경 없음)")
        return
    print("\n기존 실험 결과 영향 (질문 수정·삭제 = 재실행, 정답·key_facts 수정 = 재채점만, key_entities = 보존율만)")
    runs = sorted((CFG.results_dir / "runs").glob("*/trials.jsonl"))
    hit = False
    for t in runs:
        qids = set()
        for line in t.read_text(encoding="utf-8").splitlines():
            if line.strip():
                qids.add(json.loads(line)["qid"])
        touched = sorted(q for q in need if q in qids)
        if not touched:
            continue
        hit = True
        kinds = Counter(need[q] for q in touched)
        print(f"  {t.parent.relative_to(CFG.root).as_posix()}: "
              + ", ".join(f"{k} {v}문항" for k, v in kinds.items())
              + f"  ({', '.join(f'{q}:{need[q]}' for q in touched)})")
    if not hit:
        print("  results/runs 에 바뀐 문항이 든 실행이 없음")
    print("  (평가셋이 바뀐 뒤의 summary 는 문항 구성이 다르므로 이전 summary 와 바로 비교하지 않는다)")


def main():
    ap = argparse.ArgumentParser(description="검수표(CSV)를 평가셋에 반영")
    ap.add_argument("sheet", type=Path, help="채워진 검수표 CSV (예: data/evalsets/claude-v1/review/review_dev_v1.csv)")
    ap.add_argument("--dry-run", action="store_true", help="평가셋·로그를 저장하지 않고 결과만 출력")
    args = ap.parse_args()

    rows = read_sheet(args.sheet)
    items, meta = load_dataset()
    if not items:
        sys.exit(f"평가셋이 없습니다: {CFG.eval_dir}")
    n_before = len(items)
    items, logs, blank, errors = apply(rows, items, meta, args.sheet)

    print(f"평가셋: {CFG.eval_dir}  검수표: {args.sheet.as_posix()} ({len(rows)}행)")
    c = Counter(e["verdict"] for e in logs)
    print(f"반영: keep {c['keep']}, edit {c['edit']}, delete {c['delete']}  ->  {n_before} -> {len(items)}문항")
    for e in logs:
        if e["verdict"] == "edit":
            fields = [k for k in (e["after"] or {}) if k != "human_checked"]
            print(f"  edit   {e['qid']}: {', '.join(fields) or '-'}" + (f"  ※ {e['warning']}" if "warning" in e else ""))
        elif e["verdict"] == "delete":
            print(f"  delete {e['qid']}")
    if blank:
        print(f"\nverdict 빈칸 (건드리지 않음) {len(blank)}문항: {', '.join(blank)}")
    if errors:
        print(f"\n오류 {len(errors)}건 (반영하지 않음):")
        for e in errors:
            print(f"  {e}")

    print_table(items)
    rerun_guide(logs)

    if args.dry_run:
        print("\n[dry-run] 평가셋과 검수 로그를 저장하지 않음")
        return
    save_dataset(items, meta)
    log = log_path_for(args.sheet)
    with open(log, "a", encoding="utf-8") as f:
        for e in logs:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"\n저장: {CFG.eval_dir}  (+ qa_dev.json / qa_test.json / qa_meta.json)")
    print(f"로그: {log.as_posix()} ({len(logs)}줄 추가)")


if __name__ == "__main__":
    main()
