"""GPU(Colab 등)에서 LongLLMLingua 압축만 돌리기 위한 입력 내보내기.

한 줄 = (scenario, turn): 오래된 턴 문맥 목록, 최근 1턴 메시지, 현재 질문. 비율별 예산은 GPU 쪽에서 모델 토크나이저로 계산한다.
압축은 정답·key_facts·evidence 를 보지 않으므로 그 필드는 내보내지 않는다.

python docs/experiments/feasibility/export_inputs.py            # 정식 20개
python docs/experiments/feasibility/export_inputs.py --samples --types recall  # 샘플 2개의 recall 턴 6개
"""
import argparse
import json

from common import DATA, OUT, SAMPLES, history_and_current, question_of, split_turns
from longlingua import contexts_of

ap = argparse.ArgumentParser()
ap.add_argument("--samples", action="store_true")
ap.add_argument("--types", default="", help="쉼표로 구분한 turn_type 만 (예: recall). 비우면 전 턴")
a = ap.parse_args()
files = [DATA / f"{s}.json" for s in SAMPLES] if a.samples else sorted(DATA.glob("v2_*.json"))
types = [t for t in a.types.split(",") if t]
path = OUT / ("ll_inputs_samples.jsonl" if a.samples else "ll_inputs_all.jsonl")
n = 0
with path.open("w", encoding="utf-8") as fh:
    for f in files:
        scn = json.loads(f.read_text(encoding="utf-8"))
        for k in range(1, len(scn["turns"])):
            if types and scn["turns"][k]["turn_type"] not in types:
                continue
            past, cur = history_and_current(scn, k)
            turns = split_turns(past)
            older = [m for t in turns[:-1] for m in t]
            fh.write(json.dumps({"scenario": scn["scenario_id"], "turn": k, "turn_type": scn["turns"][k]["turn_type"], "question": question_of(cur),
                                 "contexts": contexts_of(older), "recent": turns[-1],
                                 "all_texts": [m["content"] for m in past]}, ensure_ascii=False) + "\n")
            n += 1
print(path, n)
