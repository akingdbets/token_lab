# 평가셋 claude-v1

OpenWiki 영어 위키(`data/openwiki/en`) 기준 평가셋. 질문 후보는 Claude Opus 5.5가 만들고,
검사·필터는 `dataset_builder.py --import` (문서 없이 풀기·종합형 한 페이지 검사는 qwen2.5:7b)로 했다.
생성 규칙과 후보 원본은 `candidates/README.md` 참고.

- 문항 번호는 `c0001` 형식 (Ollama로 만든 이전 평가셋의 `q0001` 과 구분)
- persona 필드: beginner / intermediate / advanced. **기록용**이다. 실험의 답변 형식·집계·검수는 type 기준이며,
  2026-10-11 유형 균형 맞추기로 추가한 문항에는 persona 가 없다
- 사람 검수 완료 (`human_checked` 174문항 모두 true). dev 35 는 `review/review_dev_v1.csv`, test 139 는
  `review/review_test_v1.csv` (keep 113 · edit 26 · delete 0, PR #37) 를 `apply_review.py` 로 반영했다. 변경 기록은 `review/review_log_v1.jsonl`
  - c0152 는 검수표 `final_*` 열로 담을 수 없는 메모(근거 문서·유형)를 따로 반영했다. 질문의 전제 문서 `integrations/sql-databases.md`
    를 빼고 근거를 `app-structure/lifespan-events.md` 131행 하나로, 유형을 multi → fact 로 바꿨다 (test: code 42 · fact 38 · procedure 30 · multi 29)
- key_facts 단위: 질문이 묻는 항목 하나에 key_fact 하나. 한 항목의 답이 값 여러 개면 한 fact 로 묶는다
  (c0153 "Status codes below 200 and 204, 205 and 304 forbid a body.", test 검수에서 c0008·c0009·c0131·c0139 도 이 규칙으로 묶음)

## 파일

| 파일 | 내용 |
|---|---|
| `qa_dataset.json` | 전체 문항 |
| `qa_dev.json` / `qa_test.json` | split 별 (dev 는 조정용, test 는 최종 보고용) |
| `qa_meta.json` | 다음 번호, 번호 접두어(`id_prefix`), 코퍼스 매니페스트 해시 |
| `candidates/` | 후보 원본, 생성 규칙, 대상 페이지 목록 |

## 사용법

평가셋 폴더는 환경변수 `EVAL_DIR` 로 고른다 (기본 `data/eval` 은 git 밖 작업 공간).

```bash
EVAL_DIR=data/evalsets/claude-v1 python src/experiment.py --split dev --semantic
EVAL_DIR=data/evalsets/claude-v1 python src/dataset_builder.py --stats
```

PowerShell: `$env:EVAL_DIR = "data/evalsets/claude-v1"` 를 먼저 실행한다.

## 다시 만들기

```bash
EVAL_DIR=data/evalsets/claude-v1 python src/dataset_builder.py --list-targets
EVAL_DIR=data/evalsets/claude-v1 python src/dataset_builder.py \
    --import data/evalsets/claude-v1/candidates/claude_20261006.jsonl \
    --generator claude-opus-5-5 --id-prefix c
# 2026-10-11 유형 균형 맞추기 (c0145-c0174)
EVAL_DIR=data/evalsets/claude-v1 python src/dataset_builder.py     --import data/evalsets/claude-v1/candidates/claude_20261011_balance.jsonl     --generator claude-opus-5-5 --id-prefix c     --cap dev:procedure=8,dev:multi=8,test:multi=30 --max-per-pair 2
```

후보 파일이 같아도 문서 없이 풀기 검사는 Qwen 응답에 따르므로, 실행 환경(Ollama 버전, 하드웨어)이 다르면
통과 문항이 조금 달라질 수 있다.
