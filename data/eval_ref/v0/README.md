# 참고용 평가셋 v0

파이프라인 동작 확인과 팀원 테스트용으로 남겨 둔 평가셋이다. **최종 평가셋이 아니며 나중에 다시 만든다.**
실험 결과를 보고할 때 이 평가셋 기준 수치를 최종 결과로 쓰지 않는다.

## 생성 조건

| 항목 | 값 |
|---|---|
| 생성일 | 2026-10-04 ~ 2026-10-05 |
| 생성 모델 | qwen2.5:7b (Ollama, temperature 0, seed 42), 검증·문서 없이 풀기 검사도 같은 모델 |
| 코퍼스 | FastAPI `50113da` (매니페스트 `d2a1440461f5…`) |
| 생성 실행 | `--docs 3`, `--docs 20` (문서 선택 수정 전), `--only-split dev --docs 14` (수정 후) |
| 사람 검수 | 안 함 (`human_checked` 전부 false) |

## 구성 (51문항)

| | fact | procedure | code | multi | 합계 |
|---|---|---|---|---|---|
| dev | 7 | 8 | 5 | 0 | 20 |
| test | 11 | 8 | 10 | 2 | 31 |

## 알려진 한계

- 사람 검수를 하지 않아 어색하거나 틀린 문항이 섞여 있을 수 있다.
- 종합형(multi)이 dev 에 없고 test 에도 2문항뿐이다. 7b 모델로는 종합형 생성 통과율이 낮다.
- 문항의 `gen_log` 가 가리키는 생성 로그(`results/logs/`)는 저장소에 없다.

## 사용법

실험 실행기는 `data/eval/qa_dataset.json` 을 읽으므로 복사해서 쓴다.

```bash
mkdir data/eval
copy data\eval_ref\v0\qa_dataset.json data\eval\
copy data\eval_ref\v0\qa_meta.json data\eval\
python src/experiment.py --split dev --semantic
```

`data/eval/` 에 이미 직접 만든 평가셋이 있으면 덮어쓰게 되니 먼저 백업한다.
