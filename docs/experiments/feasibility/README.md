# 추가 압축기 후보 2종 가능성 확인 (2026-11-28)

측정만 했다. `src/multiturn/` 은 고치지 않았고 측정 코드는 이 폴더에 있다 (기존 모듈은 import 만 한다).
측정 데이터: 샘플 시나리오 2개 (`data/evalsets/multiturn-v2/v2_01_auth_switch.json`, `v2_02_response_design.json`).
**후속 결정:** LongLLMLingua 는 후보에서 뺀다. hybrid 는 압축기 작업(`src/multiturn/history_compressors`)에서 구현한다.

## 결론

| 후보 | 판정 | 근거 |
|---|---|---|
| LongLLMLingua (질문 기반 토큰 압축) | **후보에서 뺀다** | 7B 도 정확도에서 BM25 를 못 넘음 (18건 평균 0.639 vs 0.861). 모델을 키워도 나아지지 않음 |
| query_select_hybrid (BM25 + bge-m3, 현재 질문만) | **추가할 만하다** | 정확도 0.944 로 BM25(0.861)보다 높고 모든 비율에서 같거나 높음. 노트북만으로 전체 약 1시간 |

표본이 작다 (recall 6턴 x 비율 3 = 18건, 조건당 답변 1회). 차이는 방향만 보여 주며 통계적으로 확정한 것이 아니다.

## 1. 환경

- 노트북: Ryzen 7 8845HS (8코어 16스레드, AVX-512), RAM 19.8GB (다른 프로그램 때문에 실제 여유 5~14GB), Radeon 780M
- torch-directml: torch 2.4.1 을 요구해 현재 torch 2.11 을 내려야 하므로 설치하지 않음 (내장 GPU 사용 불가)
- llmlingua 0.2.2 는 transformers 5 의 KV 캐시 형식과 맞지 않아, 측정 코드에서 모델 호출을 감싸 형식을 변환했다 (설치 패키지는 고치지 않음)
- Colab T4 에서 원래 llmlingua 는 긴 기록에서 메모리 부족이 났다 (토큰 수 x 어휘 15만 크기의 logits 를 한 번에 만듦).
  get_ppl 을 1,024 토큰씩 나눠 계산하도록 바꿔 해결했다. CPU 에서 원래 계산과 값이 같음(오차 2e-5, 압축 결과 글자 단위 일치),
  8천 토큰 기준 추가 메모리 6.9GB -> 1.0GB 를 확인했다

## 2. 압축 1회 시간과 메모리

### LongLLMLingua, 노트북 CPU (r=0.5, 나눠 계산하기 전 원래 llmlingua)

| 모델 | 약 1.1만 토큰 | 약 2.1만 토큰 | 최대 메모리(RSS) |
|---|---|---|---|
| GPT-2 | 30~45초 | 80~100초 | 2GB |
| Qwen2.5-0.5B bf16 | 81~170초 | 330~490초 | 12~13.6GB |
| Qwen2.5-1.5B bf16 | 350초 | 916초 | 13.3GB |
| Qwen2.5-3B bf16 | 630초 | (안 잼) | 12GB |
| Qwen2.5-7B | 안 잼: bf16 무게만 약 15GB 로 RAM 초과 | | |

### LongLLMLingua, Colab T4 (나눠 계산, recall 6턴 x 비율 3 = 18건)

| 모델 | 로드 | 1회 중앙값 / 최대 | GPU 최대 |
|---|---|---|---|
| Qwen2.5-0.5B | fp16 | 8초 / 27초 | 2.0GB |
| Qwen2.5-1.5B | fp16 | 17초 / 49초 | 4.3GB |
| Qwen2.5-7B | 8bit | 60초 / 170초 | 10.9GB |

### hybrid (노트북)

- bge-m3 (Ollama, CPU): 193 토큰/초 (단독 측정, 400조각 1.08만 토큰 56초). 같은 조각은 한 번만 임베딩
- BM25 와 예산 채우기: 1회 최대 약 2.8초

## 3. 정식 20개 시나리오 전체 예상 시간

압축 지점 361개 (20개 x 턴, 턴 0 제외), 기록 평균 1.13만·최대 2.13만 토큰, 비율 3개 = 1,083회. 압축 결과는 sample 끼리 재사용.

| 후보 | 예상 | 판단 |
|---|---|---|
| hybrid | 임베딩 3,762조각 12.1만 토큰 약 11분(1회만) + 선택 1,083회 최대 약 50분 = **약 1시간** | 노트북으로 충분, GPU 불필요 |
| LongLLMLingua 0.5B, 노트북 CPU | 1회 평균 약 4분 x 1,083 = 약 70시간 | 노트북 불가 |
| LongLLMLingua 7B, Colab T4 | 1회 중앙값 60초 x 1,083 = 약 18시간 (무료 Colab 세션 제한 때문에 여러 번 이어 돌려야 함) | 가능은 하나, 후보에서 빠졌으므로 하지 않음 |

## 4. 품질

### 근거 인용 잔존 (recall 6턴, 근거 16개 중 압축 결과에 그대로 남은 수, 괄호는 평균 기록 토큰)

| 방법 | r=0.25 | r=0.5 | r=0.75 |
|---|---|---|---|
| query_select (BM25) | 11 (4,061) | 15 (7,942) | 15 (8,316) |
| hybrid (현재 질문만) | 12 (4,064) | 16 (8,128) | 16 (12,192) |
| LongLLMLingua GPT-2 (CPU) | 2 (3,898) | 3 (7,046) | 9 (10,440) |
| LongLLMLingua 0.5B | 6 (3,790) | 12 (7,358) | 13 (11,080) |
| LongLLMLingua 1.5B | 4 (3,726) | 11 (7,598) | 12 (11,115) |
| LongLLMLingua 7B | 5 (3,835) | 11 (7,552) | 12 (11,104) |

hybrid 에 직전 1~2턴 질문을 붙인 변형은 근거가 오히려 줄었다 (r=0.25 에서 직전 2턴: 10/16). 현재 질문만 쓰는 쪽을 권한다.

### 답변 정확도 (gpt-6-luna, fact_judge_v3 per_fact, 주 정확도 = setup 태그 제외)

| 방법 | r=0.25 | r=0.5 | r=0.75 | 18건 평균 |
|---|---|---|---|---|
| none (원본 기록, 참고) | 1.000 | 1.000 | 1.000 | 1.000 |
| query_select (BM25) | 0.833 | 0.833 | 0.917 | 0.861 |
| hybrid (현재 질문만) | 1.000 | 0.917 | 0.917 | **0.944** |
| LongLLMLingua 0.5B | 0.667 | 0.750 | 0.750 | 0.722 |
| LongLLMLingua 1.5B | 0.667 | 0.833 | 0.833 | 0.778 |
| LongLLMLingua 7B | 0.417 | 0.667 | 0.833 | 0.639 |

출처별 key_fact 충족 (18건 합):

| 방법 | user (사용자가 정한 값) | doc (문서 사실) |
|---|---|---|
| none | 18/18 | 18/18 |
| query_select | 16/18 | 15/18 |
| hybrid | 18/18 | 16/18 |
| LongLLMLingua 0.5B | 11/18 | 15/18 |
| LongLLMLingua 1.5B | 12/18 | 16/18 |
| LongLLMLingua 7B | 9/18 | 14/18 |

LongLLMLingua 는 특히 사용자 고유 값(헤더 이름, 만료 시간 같은 것)을 잃는다. 토큰 단위로 지우다 보니 짧은 값이 끊기거나 빠진다.

## 주의할 점

- 과거 기록의 assistant 응답은 시나리오 정답(answer)이다. 실험 reference 궤적이 아니다.
- 조건당 답변 1회, 셀당 6건이다. 1건 차이가 0.083~0.167 이므로 작은 차이는 우연일 수 있다.
- none 은 비율과 상관없이 같은 입력이라 실제로는 6건이 세 번 들어갔다 (두 번째부터 응답 캐시).
- LongLLMLingua 는 받은 예산의 83~86% 만 써서 BM25·hybrid 보다 토큰이 약간 적다 (5~10%). 이 차이로 정확도 격차(0.2 이상)를 설명하기는 어렵다.
- query_select 는 BM25 점수가 0 보다 큰 조각만 골라 r=0.75 에서 예산의 54% 만 쓴다 (8,316 / 15,490). hybrid 는 예산을 다 쓴다.
  hybrid 의 이득 일부는 "더 많이 남긴 것" 에서 온다. r=0.25 (두 방법 토큰 같음) 에서도 hybrid 가 높았다 (1.000 vs 0.833).
- 채점 중 채점 모델 연결 끊김으로 18번 재시도했다. 빠진 건은 없다 (108/108, 빈 답변 0).

## 파일

| 파일 | 내용 |
|---|---|
| `common.py` | 기록 구성, 근거 인용 잔존 검사, 메모리 측정 |
| `hybrid.py` | hybrid 선택 (BM25 + bge-m3) 과 query_select 기준선 측정 |
| `longlingua.py` | 노트북 CPU LongLLMLingua 측정 (transformers 5 KV 형식 변환 포함) |
| `download_models.py`, `run_timing.sh`, `run_quality.sh` | 모델 내려받기, CPU 시간·품질 측정 순서 실행 |
| `make_colab_notebook.py` -> `ll_colab.ipynb` | Colab 압축 노트북 (get_ppl 나눠 계산, Drive 건별 저장, 이어 하기). 셀 원문은 생성 스크립트가 원본 |
| `export_inputs.py` | Colab 입력 내보내기 (`--samples --types recall` 은 18건용, 옵션 없으면 정식 20개) |
| `eval_compare.py` | 답변·채점 비교 (`--report` 로 표 다시 출력) |
| `quality_table.py` | 근거 인용 잔존 표 |
| `scenario_sizes.py` | 20개 시나리오 기록 크기와 조각 수 |

### 결과 (`results/`, 커밋한 작은 파일만)

| 파일 | 내용 |
|---|---|
| `ll_timing_*.json` | 노트북 CPU LongLLMLingua 시간·메모리 (r=0.5) |
| `ll_quality_*.json` | 노트북 CPU LongLLMLingua 품질 맛보기 (근거 인용 잔존). 1.5B 는 중단해서 1건 |
| `scenario_sizes.json` | 20개 시나리오 턴별 기록 토큰, 고유 조각 수 |
| `hybrid_embed_stats.json` | 첫 hybrid 측정의 임베딩 통계 (다운로드와 겹쳐 느림. 단독 측정값은 본문 193 토큰/초) |
| `eval_summary.csv` | 채점 108행 요약 (답변 원문 제외) |

커밋하지 않은 큰 중간 결과는 저장소의 `results/feasibility/` (git 제외)에 둔다:
Colab 압축 결과 `ll_outputs_<모델>.jsonl` (각 약 450KB), 입력 `ll_inputs_samples.jsonl` (약 810KB),
채점 원본 `eval_rows.jsonl` (답변 원문 포함), `hybrid_rows.json`. 스크립트가 같은 위치에 다시 만든다.

## 다시 돌리기

```powershell
python docs/experiments/feasibility/hybrid.py
```

```powershell
python docs/experiments/feasibility/export_inputs.py --samples --types recall
```

```powershell
python docs/experiments/feasibility/make_colab_notebook.py
```

Colab 결과 `ll_outputs_<모델>.jsonl` 을 `results/feasibility/` 에 넣은 뒤:

```powershell
python docs/experiments/feasibility/eval_compare.py --run
```

```powershell
python docs/experiments/feasibility/quality_table.py
```

hybrid 는 Ollama `bge-m3` (기존 EMBED 설정), 답변·채점은 `.env` 의 ANSWER_*·JUDGE_* 설정을 쓴다.
이 문서의 토큰 수는 `.env` 의 `TOKENIZER=tiktoken:o200k_base` 로 센 값이다 (예산 r x 기록 토큰도 이 기준).
`.env` 없이 기본 토크나이저(Qwen2.5)로 세면 토큰 수가 약 5% 크게 나온다 (근거 잔존 판정은 같다).
