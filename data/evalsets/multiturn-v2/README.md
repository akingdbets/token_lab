# multiturn-v2 (FastAPI 정식 시나리오)

설계: [`docs/experiments/multiturn_v2/DESIGN.md`](../../../docs/experiments/multiturn_v2/DESIGN.md). 스키마 검사: `src/multiturn/scenario_v2.py`.
상태: **샘플 2개 (draft, 검수 전)**. `reviewed` 가 되기 전에는 본 실험에 쓰지 않는다.

## 가정과 범위

- 별도의 문맥 한도를 설정하지 않은 일반적인 LLM 사용 상황을 가정한다. 문맥 한도 근처에서 강제로 요약하는 compaction 은 일어나지 않으므로 범위에서 뺀다.
- 연구 대상은 **문맥 한도 안에서 토큰을 줄이려고 매 턴 미리 하는 압축(선제 압축)** 이다.
- 압축 예산(r25 / r50 / r75, 절대 예산 2000·4000·8000)은 문맥 한도가 아니라 **압축 강도**다.
- `rolling_summary` 는 compaction 이 아니라 선제 요약(계획서 기법 2: 재귀 요약)이다.
- 답변 모델 gpt-6-luna 의 문맥 창은 1,050,000 토큰, 최대 입력 922,000 토큰이다
  ([OpenAI 모델 문서](https://developers.openai.com/api/docs/models/gpt-6-luna), 2026-11-27 확인). 시나리오 최대 기록은 약 21k 토큰이다.
- 프롬프트 캐시는 평가에서 뺀다 (문맥 토큰과 정확도로만 본다).

## 문항 제외 원칙

**모델 성능을 보고 문항을 거르거나 다시 만들지 않는다.** 제외 사유는 아래 세 가지뿐이고, 제외할 때마다 아래 표에 남긴다.

1. 근거 확인 실패 (`check_grounding_v2`: 인용문·key_entity 가 원문에 없음)
2. closed-book 검사 결과: 제외하지 않고 `closed_book.correct` 로 표시만 한다. 분석에서 따로 집계한다
3. 사람 검수의 "제외" 판정 (`docs/review/` 검수 시트)

생성 단계의 재요청은 스키마·규칙 위반(형식 오류)일 때 1회만 한다. 정답률을 보고 다시 생성하지 않는다.

| 시나리오 | 턴 | 사유 | 날짜 | 결정한 사람 |
|---|---|---|---|---|
| (아직 없음) | | | | |

## 파일

| 파일 | 내용 |
|---|---|
| `v2_01_auth_switch.json` | 인증 방식 전환 (헤더 토큰·쿠키·API 키), 19턴, draft |
| `v2_02_response_design.json` | 응답 상태·형식 설계 (upsert 응답 계약), 19턴, draft |

생성 기록(프롬프트·요청 설정·응답 원문): `results/scenario_gen/<run_id>/` (git 제외). 시나리오의 `generation.run_id` 로 찾는다.

## 다시 만들기·검사

```powershell
python src/multiturn/scenario_gen.py --bundle v2_01 --scenario-id v2_01_auth_switch
```

```powershell
python src/multiturn/closed_book_v2.py data/evalsets/multiturn-v2/v2_01_auth_switch.json data/evalsets/multiturn-v2/v2_02_response_design.json
```

```powershell
python src/multiturn/review_sheet.py data/evalsets/multiturn-v2/v2_01_auth_switch.json data/evalsets/multiturn-v2/v2_02_response_design.json --name multiturn_v2_samples
```

```powershell
python src/multiturn/scenario_report.py data/evalsets/multiturn-v2/v2_01_auth_switch.json data/evalsets/multiturn-v2/v2_02_response_design.json
```

## 채점 버전

사람 라벨 80행 비교([`docs/results/judge_version_agreement_v2_v3.md`](../../../docs/results/judge_version_agreement_v2_v3.md))에서
v3 가 v2 보다 1행 낮아 규칙대로 **fact_judge_v2** 를 쓴다. `accept_alternatives` 는 분석용으로만 쓴다.
