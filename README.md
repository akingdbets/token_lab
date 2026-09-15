# Context Compression Research

문서의 의미 손실을 최소화하면서 토큰 소비량을 줄이는 문맥 압축 연구
(2026학년도 2학기 산학협력 프로젝트 / LG전자)

오픈소스 기술 문서(FastAPI 공식 문서)를 LLM Wiki로 구조화하고, 서로 다른 문맥 압축 기법을
동일 조건에서 비교하여 토큰 절감률·의미 손실률·답변 정확도를 정량적으로 측정한다.

## 실험 설계

RAG(Vector DB 검색) 단계를 두지 않고, 질문마다 정답 근거 문서를 직접 입력한다.
검색 품질이라는 변수를 제거하여, 성능 변화가 압축 기법에 의한 것만 측정되도록 통제하기 위함이다.
압축 모듈은 문자열을 받아 문자열을 반환하는 독립 구조이므로, 추후 RAG 파이프라인의
검색 결과 후처리 단계에 그대로 연결할 수 있다.

```
[준비]  원문 수집 → LLM Wiki 구축 → 평가 데이터셋 생성
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
│   ├── raw/fastapi/          # git clone 원본 (버전 관리 제외)
│   ├── wiki/                 # 정제된 LLM Wiki (생성물, 버전 관리 제외)
│   ├── wiki_stats.csv        # 문서별 토큰 변화 기록
│   └── eval/qa_dataset.json  # 평가 데이터셋
├── src/
│   ├── config.py             # 모델·경로·실험 조건 통합 설정
│   ├── llm.py                # LLM 호출 (백엔드 교체 가능)
│   ├── wiki_builder.py       # 원문 → LLM Wiki 변환
│   ├── dataset_builder.py    # 평가 데이터셋 생성 및 검수
│   └── compressors/          # 압축 기법 구현 (예정)
├── results/                  # 실험 로그
└── dashboard/                # Streamlit 대시보드 (예정)
```

## 사용법

### 1. 원문 수집

```bash
git clone --depth 1 https://github.com/fastapi/fastapi.git data/raw/fastapi
```

### 2. LLM Wiki 구축

```bash
python src/wiki_builder.py --src ./data/raw/fastapi --out ./data/wiki
```

원문 마크다운을 LLM이 읽기 좋은 형태로 가공한다.

- 코드 참조 `{* ../../docs_src/x.py *}` 를 실제 소스 코드로 펼침
- 앵커 `{ #id }`, HTML 태그 등 형식 잡음 제거
- 페이지별 메타정보(제목·요약·목차·핵심 용어·원본 경로) 부착
- 변경 이력, 프로젝트 안내 등 기술 설명이 아닌 문서 제외
- 문서별 토큰 변화를 `data/wiki_stats.csv`에 기록

### 3. 평가 데이터셋 생성

```bash
python src/dataset_builder.py --docs 30 --per-doc 2      # 생성
python src/dataset_builder.py --review                   # 사람 검수
python src/dataset_builder.py --stats                    # 통계 확인
```

문항마다 3단계 필터를 거친다.

| 단계 | 내용 |
|---|---|
| 생성 | 위키 문서를 LLM에 입력해 사실 확인형 질문·정답·근거 문장 생성 |
| 자동 검증 | 정답이 문서에 명시되어 있고 구체적인지 LLM이 판정 |
| Closed-book 검사 | 문서 없이도 맞히는 질문은 제외 (압축 효과 측정 불가) |
| 순환 질문 제거 | 정답이 질문 안에 포함된 항목 자동 제외 |

주요 옵션

```
--docs N           대상 문서 수
--per-doc N        문서당 문항 수
--prefix PATH      우선할 문서 폴더 (기본 tutorial/)
--dry-run          저장 없이 화면 출력만
--no-closed-book   closed-book 검사 생략 (빠르지만 품질 저하)
```

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

- [x] LLM Wiki 구축 (121개 문서 / 약 26만 토큰)
- [x] LLM 호출 모듈 (Ollama · OpenAI 호환 백엔드, TTFT 측정)
- [x] 평가 데이터셋 생성 파이프라인
- [ ] 평가 데이터셋 확정 (생성 및 검수)
- [ ] 기준선(Baseline) 측정
- [ ] 압축 기법 1 — 규칙 기반 문맥 정제
- [ ] 압축 기법 3 — LLMLingua
- [ ] 압축 기법 2 — 재귀 요약
- [ ] 하이브리드 파이프라인
- [ ] 멀티 에이전트 오케스트레이션 검증
- [ ] 평가 지표 모듈 (의미 손실률 · 정답 채점)
- [ ] Streamlit 대시보드
