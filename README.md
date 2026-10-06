# Context Compression Research

문서의 의미 손실을 최소화하면서 토큰 소비량을 줄이는 문맥 압축 연구
(2026학년도 2학기 산학협력 프로젝트 / LG전자)

오픈소스 기술 문서(FastAPI 공식 문서)를 OpenWiki로 구조화하고, 서로 다른 문맥 압축 기법을
동일 조건에서 비교하여 토큰 절감률·의미 손실률·답변 정확도를 정량적으로 측정한다.

## 실험 설계

RAG(Vector DB 검색) 단계를 두지 않고, 질문마다 정답 근거 문서를 직접 입력한다.
검색 품질이라는 변수를 제거하여, 성능 변화가 압축 기법에 의한 것만 측정되도록 통제하기 위함이다.
압축 모듈은 문자열을 받아 문자열을 반환하는 독립 구조이므로, 추후 RAG 파이프라인의
검색 결과 후처리 단계에 그대로 연결할 수 있다.

```
[준비]  OpenWiki 위키(코퍼스) → 평가 데이터셋 생성
[실험]  질문 + 근거 문서 → 압축 → LLM 답변 → 평가·기록 → 대시보드
```

### 정량 목표

| 지표 | 정의 | 목표 | `summary.json` 필드 |
|---|---|---|---|
| 토큰 절감률 | (1 − 압축 후 토큰 / 원본 토큰) × 100 | 50% 이상 | `reduction_pct` |
| 의미 손실률 | 임베딩 코사인 유사도(손실률 = 1 − 유사도) 및 핵심 엔티티 보존율 기반 | 5% 이내 | `semantic_sim`, `entity_retention` |
| 답변 정확도 유지율 | 압축 문맥 답변 정확도 / 원본 문맥(`none`) 답변 정확도 × 100 | 90% 이상 | `answer_accuracy_retention_pct` |
| 순 토큰 절감률 | 압축에 소모된 LLM 토큰까지 차감한 실질 절감률 | 측정·보고 | `net_reduction_pct` |

답변 정확도(`answer_accuracy`)는 정답/오답이 아니라, 문항의 핵심 사실(`key_facts`) 중
답변이 전달한 비율(0~1)이다. 자세한 내용은 [3. 압축 실험](#3-압축-실험-ab-비교) 참고.

### 압축 기법

1. **규칙 기반 문맥 정제** — 형식 잡음 제거, 중복 문장 제거, 무관 섹션 필터링, 지시문 간결화
2. **재귀 요약** — 요약본을 반복 압축 / 멀티턴 누적 기록 압축 / 사전 요약 변형
3. **LLMLingua** — 소형 언어모델 기반 저정보 토큰 제거 (LLMLingua-2, LongLLMLingua)
4. **하이브리드** — 상기 기법을 순차 결합한 파이프라인

## 실행 환경

- Python 3.11+
- [Ollama](https://ollama.com) (로컬 open-weight 모델)

```bash
pip install -r requirements.txt

ollama pull qwen2.5:7b      # 답변 생성 · 채점
ollama pull qwen2.5:3b      # 요약 전용 (재귀 요약 비용 비교용)
ollama pull bge-m3          # 임베딩 (의미 손실률 측정)
```

## 프로젝트 구조

```
token_lab/
├── data/
│   ├── openwiki/             # OpenWiki 생성 위키: en/ (문서 원천, 고정), ko/ (보관용). 출처는 각 SOURCE.md
│   ├── corpus_manifest.jsonl # 코퍼스 페이지 목록·종류·해시·토큰 수
│   └── eval/                 # 평가 데이터셋 (버전 관리 제외)
├── src/
│   ├── config.py             # 모델·경로·실험 조건 통합 설정
│   ├── llm.py                # LLM 호출 (백엔드 교체 가능), 토큰 계산
│   ├── corpus.py             # 코퍼스 로더 (OpenWiki 위키, 문서의 단일 출처)
│   ├── dataset_builder.py    # 평가 데이터셋 생성 및 검수
│   ├── grader.py             # 답변 채점 (key_facts 단위 LLM 판정 + 단어 일치)
│   ├── experiment.py         # 압축 실험 실행 (A/B 비교)
│   └── compressors/          # 압축 기법 (none, rule)
├── results/                  # 실험 로그 (runs/<run_id>/)
└── dashboard/                # Streamlit 대시보드 (예정)
```

## 사용법

### 1. 코퍼스 (OpenWiki 위키)

- **문서 원천 = `data/openwiki/en`** (OpenWiki 결과물 그대로). 페이지를 가공하지 않고, 머리말까지 원문 그대로 쓴다.
  생성 조건(OpenWiki 버전, 모델, 입력 커밋 등)은 `data/openwiki/en/SOURCE.md` 에 있다. 실험 기간 동안 다시 생성하지 않는다.
- **인덱스 = OpenWiki 최상위 목차 페이지** (`config.index_page`, 기본 `quickstart.md`). 탐색기가 이 페이지를 그대로 인덱스로 읽는다.
- 페이지 종류(`kind`): `page` 본문 49개(질문 생성 대상) / `quickstart` 최상위 목차 / `index` 루트·폴더 목차(`index.md`).
  `.claims/` 등 숨김 파일과 `INSTRUCTIONS.md`, `SOURCE.md` 는 코퍼스가 아니다.

```bash
python src/corpus.py --stats     # 페이지 수·토큰 분포·폴더별 페이지 수, 매니페스트 갱신
```

`corpus.py` 는 줄바꿈을 LF 로 통일해서 해시·토큰 수를 계산하므로, OS나 git 줄바꿈 설정과 관계없이
`data/corpus_manifest.jsonl` 이 같게 나온다. 위키 폴더는 환경변수 `OPENWIKI_DIR` 로 바꿀 수 있다.

### 2. 평가 데이터셋 생성

```bash
python src/dataset_builder.py --docs 30 --per-type 1     # 생성
python src/dataset_builder.py --review                   # 사람 검수
python src/dataset_builder.py --stats                    # 통계 확인
```

질문 유형은 사실 확인형(`fact`), 절차형(`procedure`), 코드·파라미터형(`code`),
여러 페이지 종합형(`multi`) 네 가지다. 종합형의 짝 페이지는 위키 페이지 간 링크로 고른다.
문항마다 다음 필터를 거친다.

| 단계 | 내용 |
|---|---|
| 생성 | 본문 페이지(목차 페이지 제외) 원문을 LLM에 입력해 질문·정답·근거 문장 생성 |
| 순환 질문 제거 | 정답이 질문 안에 포함된 항목 제외 |
| 베끼기 검사 | 문서 표현을 그대로 옮긴 질문은 바꿔 쓰거나 제외 |
| 근거 확인 | 근거 문장이 페이지 어디에 있는지 줄 번호로 기록, 못 찾으면 제외. 사실형은 코드 블록 밖 문장, 코드형은 코드 블록 안의 줄이어야 함 |
| 자동 검증 | 정답이 문서에 명시되어 있고 구체적인지 LLM이 판정 |
| Closed-book 검사 | 문서 없이도 맞히는 질문은 제외 (압축 효과 측정 불가) |

문항마다 정답과 함께 `key_entities`(핵심 용어·이름·값, 압축 후 남았는지 확인용)와
`key_facts`(정답이 전달해야 할 사실을 하나씩 나눈 목록, 답변 정확도 채점용)를 만든다.
`key_facts` 가 없는 후보는 제외된다.

주요 옵션 (전체는 `--help`)

```
--docs N           대상 문서 수 (폴더별 층화 추출)
--per-type N       문서당 유형별 문항 수
--types LIST       생성할 유형 (예: fact,code)
--dry-run          저장 없이 화면 출력만
--no-verify        LLM 자동 검증 생략
--no-closed-book   closed-book 검사 생략 (빠르지만 품질 저하)
```

### 3. 압축 실험 (A/B 비교)

```bash
python src/experiment.py                              # dev 문항, none(기준선) vs rule
python src/experiment.py --split all --limit 5        # 연결 확인용
python src/experiment.py --compressors none,rule --semantic   # 임베딩 유사도 포함 (bge-m3)
```

문항마다 `질문 → 근거 문서 → 압축 → LLM 답변 → 채점 → 로그` 를 압축기별로 실행한다.
문맥은 문항의 정답 근거 페이지 원문이고, `none` 이 기준선이다.
결과는 `results/runs/<run_id>/` 에 저장된다.

- `trials.jsonl` 문항 x 압축기마다 한 줄 (토큰, 절감률, 답변, 문항별 지표, key_fact별 판정, TTFT 등)
- `summary.json` 압축기별 집계 (아래 표)
- `contexts/` 압축 전후 문맥 (압축 결과를 눈으로 확인할 때)

#### 평가 지표 (`summary.json`)

| # | 필드 | 의미 | 계산 |
|---|---|---|---|
| 1 | `reduction_pct` | 토큰 절감률 | 1 − 압축 후 문맥 토큰 / 원문 문맥 토큰 (Qwen 토크나이저) |
| 2 | `net_reduction_pct` | 순 토큰 절감률 | 압축 과정에서 LLM 이 쓴 토큰까지 더해서 계산 (LLM 안 쓰는 압축기는 1과 같음) |
| 3 | `semantic_sim` | 의미 유사도 | 압축 전후 문맥 임베딩(bge-m3)의 코사인 유사도. `--semantic` 일 때만 |
| 4 | `entity_retention` | 핵심 엔티티 보존율 | 문항의 `key_entities` 중 압축 문맥에 남은 비율 |
| 5 | `answer_accuracy` | 답변 정확도 | 문항마다 `key_facts` 중 답변이 전달한 비율(0~1)의 평균 |
| 6 | `answer_accuracy_retention_pct` | 답변 정확도 유지율 | 같은 문항끼리 짝지어 압축기 / `none` 답변 정확도 × 100 (`none` 자신은 null) |

보조 기록 (지표 아님, 비교·디버깅용)

- `binary_accuracy` 예전 방식의 정답/오답 비율 (짧은 정답은 단어 일치, 긴 정답은 LLM YES/NO 판정)
- `answer_in_context` 짧은 정답이 압축 문맥에 단어 그대로 남은 비율
- `baseline_answer_accuracy`, `paired_answer_accuracy` 유지율 계산에 쓴 짝지은 문항의 두 정확도
- `ctx_tokens_raw`, `ctx_tokens`, `compress_llm_tokens`, `ttft_sec`, `latency_sec`, `ctx_overflow`

#### 채점 방식

- 답변 정확도는 LLM judge(`judge_model`)가 `key_fact` 하나하나를 충족/불충족으로 판정한다.
  표현이 달라도 뜻이 같으면 충족이고, 판정 결과를 읽지 못한 fact 는 불충족으로 센다. v0 은 fact 별 가중치가 같다.
- 판정 결과는 `trials.jsonl` 의 `fact_results`, `satisfied_facts`, `total_facts` 에 남는다.
- 평가셋 문항에 `key_facts` 가 있어야 한다. 없는 문항이나 `--no-judge` 로 실행하면 5·6번 지표는 `null` 이다.

압축기는 `compress(question, context) -> CompressResult` 인터페이스를 따르고
`src/compressors/__init__.py` 의 `REGISTRY` 에 등록하면 `--compressors` 로 고를 수 있다.

### 4. LLM 연결 확인

```bash
python src/llm.py
```

응답, 입출력 토큰 수, TTFT(첫 토큰까지 시간), 임베딩 차원을 출력한다.

## 실험 통제 조건

압축 기법 간 비교가 공정하도록 다음을 고정한다.

- 동일 모델, `temperature=0`, `seed` 고정
- `num_ctx=16384` (Ollama 기본값 4096은 긴 문서를 잘라내므로 반드시 지정)
- 답변·채점 프롬프트 고정 (지시문 변경이 정확도에 영향을 주므로 실험 내내 동일하게 유지)
- 압축하지 않은 원본 입력 결과를 기준선(Baseline)으로 삼음
- 조건별 반복 실행 후 평균·표준편차 보고

노트북 등 사양이 낮은 환경에서는 환경변수로 모델만 교체한다.

```bash
LLM_MODEL=qwen2.5:3b python src/dataset_builder.py --docs 3 --dry-run
```

## 진행 현황

- [x] OpenWiki 위키 생성 (영어)
- [x] 코퍼스 OpenWiki 전환 (문서 원천 data/openwiki/en, 인덱스 quickstart.md)
- [ ] 평가셋 재생성 (OpenWiki 코퍼스 기준)
- [x] LLM 호출 모듈 (Ollama · OpenAI 호환 백엔드, TTFT 측정)
- [x] 평가 데이터셋 생성 파이프라인
- [ ] 평가 데이터셋 확정 (생성 및 검수)
- [x] 압축 실험 실행기 (A/B 비교, 채점, 로그)
- [ ] 기준선(Baseline) 측정
- [x] 압축 기법 1 — 규칙 기반 문맥 정제 (구현, 측정 전)
- [ ] 압축 기법 3 — LLMLingua
- [ ] 압축 기법 2 — 재귀 요약
- [ ] 하이브리드 파이프라인
- [ ] 멀티 에이전트 오케스트레이션 검증
- [x] 평가 지표 모듈 (6개 지표, key_facts 기반 답변 정확도) — 의미 유사도는 bge-m3 필요, judge 신뢰도 검증 전
- [ ] Streamlit 대시보드
