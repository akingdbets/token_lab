# 평가셋 claude-v1

OpenWiki 영어 위키(`data/openwiki/en`) 기준 평가셋. 질문 후보는 Claude Opus 5.5가 만들고,
검사·필터는 `dataset_builder.py --import` (문서 없이 풀기·종합형 한 페이지 검사는 qwen2.5:7b)로 했다.
생성 규칙과 후보 원본은 `candidates/README.md` 참고.

- 문항 번호는 `c0001` 형식 (Ollama로 만든 이전 평가셋의 `q0001` 과 구분)
- persona 필드: beginner / intermediate / advanced. **기록용**이다. 실험의 답변 형식·집계·검수는 type 기준이며,
  2026-10-11 유형 균형 맞추기로 추가한 문항에는 persona 가 없다
- 검수 상태 (2026-10-30, `review/review_log_v1.jsonl` 에 전후 값 기록)
  - dev 35: 사람 검수 (`human_checked` true)
  - test 26 (AI 사전 점검 check·problem): 사람이 기준과 유형별 처리를 정해 반영 (`human_checked` true)
  - test 113 (AI 사전 점검 ok): **AI 점검만** (`human_checked` false, `ai_checked` 에 점검 모델·날짜·keep/edit).
    7문항은 key_facts 범위를 고쳤다. 검수표 `verdict` 는 비워 뒀으므로 사람이 채우면 `apply_review.py` 로 반영된다

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
