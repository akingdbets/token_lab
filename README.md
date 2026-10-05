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
[준비]  원문 수집(코퍼스) → OpenWiki 생성 → 평가 데이터셋 생성
[실험]  질문 + 근거 문서 → 압축 → LLM 답변 → 평가·기록 → 대시보드
```

### 정량 목표

| 지표 | 정의 | 목표 |
|---|---|---|
| 토큰 절감률 | (1 − 압축 후 토큰 / 원본 토큰) × 100 | 50% 이상 |
| 의미 손실률 | 임베딩 코사인 유사도 및 핵심 엔티티 보존율 기반 | 5% 이내 |
| 답변 정확도 유지율 | 압축 문맥 정답률 / 원본 문맥 정답률 × 100 | 90% 이상 |
| 순 토큰 절감률 | 압축에 소모된 토큰까지 차감한 실질 절감률 | 측정·보고 |

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
│   ├── raw/fastapi/          # FastAPI 원문 스냅샷 (git clone, 버전 관리 제외)
│   ├── corpus_manifest.jsonl # 코퍼스 문서 목록·해시·토큰 수
│   ├── index/                # 탐색용 인덱스 (nav_v0 등)
│   ├── openwiki/             # OpenWiki 생성 위키: en/ (실험용, 고정), ko/ (보관용). 출처는 각 SOURCE.md
│   └── eval/                 # 평가 데이터셋 (버전 관리 제외)
├── src/
│   ├── config.py             # 모델·경로·실험 조건 통합 설정
│   ├── llm.py                # LLM 호출 (백엔드 교체 가능), 토큰 계산
│   ├── corpus.py             # 원문 코퍼스 로더 (원본의 단일 출처)
│   ├── index_builder.py      # 탐색용 인덱스 생성
│   ├── dataset_builder.py    # 평가 데이터셋 생성 및 검수
│   ├── grader.py             # 정답 채점 (단어 일치 + LLM 판정)
│   ├── experiment.py         # 압축 실험 실행 (A/B 비교)
│   └── compressors/          # 압축 기법 (none, rule)
├── results/                  # 실험 로그 (runs/<run_id>/)
└── dashboard/                # Streamlit 대시보드 (예정)
```

## 사용법

### 1. 원문 수집

코퍼스는 FastAPI 커밋 `50113da` (v0.142.2) 스냅샷으로 고정한다.

```bash
git clone -c core.autocrlf=true https://github.com/fastapi/fastapi.git data/raw/fastapi
git -C data/raw/fastapi checkout 50113da16fec53b66b80d75e80a89296de4fa5a5
python src/corpus.py --stats
```

`corpus.py`는 파일 바이트 그대로 해시·토큰 수를 계산한다. `data/corpus_manifest.jsonl`은
CRLF 줄바꿈으로 체크아웃한 상태에서 만들어졌으므로, OS와 관계없이 `core.autocrlf=true`로
clone해야 해시와 토큰 수가 일치한다.

### 2. 위키 (OpenWiki)

위키는 OpenWiki로 같은 스냅샷에서 생성하고,
결과 `openwiki/` 폴더를 `data/openwiki/`에 그대로 둔다. 실험 기간 동안 위키는 고정한다.
생성 시 `config.corpus_exclude`에 해당하는 페이지(릴리스 노트, reference 등)는 원본에서
빼고 생성해 위키와 코퍼스의 범위를 맞춘다.

### 3. 평가 데이터셋 생성

```bash
python src/dataset_builder.py --docs 30 --per-type 1     # 생성
python src/dataset_builder.py --review                   # 사람 검수
python src/dataset_builder.py --stats                    # 통계 확인
```

질문 유형은 사실 확인형(`fact`), 절차형(`procedure`), 코드·파라미터형(`code`),
여러 페이지 종합형(`multi`) 네 가지다. 문항마다 다음 필터를 거친다.

| 단계 | 내용 |
|---|---|
| 생성 | 코퍼스 문서(예제 코드 펼친 보기)를 LLM에 입력해 질문·정답·근거 문장 생성 |
| 순환 질문 제거 | 정답이 질문 안에 포함된 항목 제외 |
| 베끼기 검사 | 문서 표현을 그대로 옮긴 질문은 바꿔 쓰거나 제외 |
| 근거 확인 | 근거 문장이 원문 어디에 있는지 파일·줄 번호로 기록, 못 찾으면 제외 |
| 자동 검증 | 정답이 문서에 명시되어 있고 구체적인지 LLM이 판정 |
| Closed-book 검사 | 문서 없이도 맞히는 질문은 제외 (압축 효과 측정 불가) |

주요 옵션 (전체는 `--help`)

```
--docs N           대상 문서 수 (폴더별 층화 추출)
--per-type N       문서당 유형별 문항 수
--types LIST       생성할 유형 (예: fact,code)
--dry-run          저장 없이 화면 출력만
--no-verify        LLM 자동 검증 생략
--no-closed-book   closed-book 검사 생략 (빠르지만 품질 저하)
```

### 4. 탐색용 인덱스 생성

```bash
python src/index_builder.py
```

mkdocs nav 계층을 목차 형태로 만들어 `data/index/nav_v0.md`에 저장한다.

### 5. 압축 실험 (A/B 비교)

```bash
python src/experiment.py                              # dev 문항, none(기준선) vs rule
python src/experiment.py --split all --limit 5        # 연결 확인용
python src/experiment.py --compressors none,rule --semantic   # 임베딩 유사도 포함 (bge-m3)
```

문항마다 `질문 → 근거 문서 → 압축 → LLM 답변 → 채점 → 로그` 를 압축기별로 실행한다.
문맥은 문항의 정답 근거 페이지 원문(예제 코드 펼침)이고, `none` 이 기준선이다.
결과는 `results/runs/<run_id>/` 에 저장된다.

- `trials.jsonl` 문항 x 압축기마다 한 줄 (토큰, 절감률, 답변, 채점, TTFT 등)
- `summary.json` 압축기별 집계 (절감률, 순 절감률, 정확도, 정확도 유지율, 엔티티 보존율)
- `contexts/` 압축 전후 문맥 (압축 결과를 눈으로 확인할 때)

채점은 짧은 정답(5단어 이하)은 단어 일치, 긴 정답은 LLM 판정(`judge_model`)을 쓴다.

압축기는 `compress(question, context) -> CompressResult` 인터페이스를 따르고
`src/compressors/__init__.py` 의 `REGISTRY` 에 등록하면 `--compressors` 로 고를 수 있다.

### 6. LLM 연결 확인

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

- [x] 원문 코퍼스 로더 (574개 파일, 커밋 50113da 고정)
- [x] 탐색용 인덱스 (nav_v0)
- [x] OpenWiki 위키 생성 (영어, 코퍼스 범위에 맞춤)
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
- [ ] 평가 지표 모듈 (의미 손실률 · 정답 채점) — 채점·엔티티 보존율 구현, 의미 손실률은 bge-m3 필요
- [ ] Streamlit 대시보드
