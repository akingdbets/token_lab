# multiturn-v2 (FastAPI 정식 시나리오)

설계: [`docs/experiments/multiturn_v2/DESIGN.md`](../../../docs/experiments/multiturn_v2/DESIGN.md). 스키마 검사: `src/multiturn/scenario_v2.py`.
상태: **샘플 2개 (draft, 검수 전, 생성 프롬프트 `mt_scenario_gen_v2`)**. `reviewed` 가 되기 전에는 본 실험에 쓰지 않는다.
2026-11-28 설계 변경 내용과 이유는 DESIGN.md 9절 변경 이력.

## 가정과 범위

- 별도의 문맥 한도를 설정하지 않은 일반적인 LLM 사용 상황을 가정한다. 문맥 한도 근처에서 강제로 요약하는 compaction 은 일어나지 않으므로 범위에서 뺀다.
- 연구 대상은 **문맥 한도 안에서 토큰을 줄이려고 매 턴 미리 하는 압축(선제 압축)** 이다.
- 압축 예산(r25 / r50 / r75, 절대 예산 2000·4000·8000)은 문맥 한도가 아니라 **압축 강도**다.
- `rolling_summary` 는 compaction 이 아니라 선제 요약(계획서 기법 2: 재귀 요약)이다.
- 답변 모델 gpt-6-luna 의 문맥 창은 1,050,000 토큰, 최대 입력 922,000 토큰이다
  ([OpenAI 모델 문서](https://developers.openai.com/api/docs/models/gpt-6-luna), 2026-11-27 확인). 시나리오 최대 기록은 약 21k 토큰이다.
- 프롬프트 캐시는 평가에서 뺀다 (문맥 토큰과 정확도로만 본다).

## key_fact 출처 (source=doc | user)

- `doc`: 첨부 문서에 있는 사실. 근거는 페이지 인용 `{quote, page, fact_idx}`.
- `user`: 사용자가 대화 중 정한 프로젝트 고유 값 (토큰 만료 17분, 헤더 이름 X-Tenant-Key 같은 것). 근거는 사용자 발화 인용
  `{quote, user_turn, fact_idx}`. recall·synthesis·update 의 대상으로 쓰고, recall·synthesis 턴 key_fact 중 30~50% 를 user 로 둔다.
- **두 출처를 섞는 이유.** 문서 블록만 압축하는 기법(per_message, presummary, fact_notes)은 사용자 발화를 원문으로 둔다.
  문서 출처 사실만 물으면 이 기법들은 손실이 생기는 쪽만, 사용자 출처 사실만 물으면 손실이 없는 쪽만 시험하게 된다.
  두 출처를 섞어야 모든 압축기를 공정하게 시험할 수 있다. **분석은 출처별로 따로 한다** (출처별 정확도를 따로 내고 합치지 않는다).
- 사용자 값은 문서에 없으므로 closed-book 으로 맞힐 수 없다 (사전 지식 오염이 없다).

## 문항 제외 원칙

**모델 성능을 보고 문항을 거르거나 다시 만들지 않는다.** 제외 사유는 아래 세 가지뿐이고, 제외할 때마다 아래 표에 남긴다.

1. 근거 확인 실패 (`check_grounding_v2`: 인용문·key_entity 가 원문에 없음)
2. closed-book 검사 결과: 제외하지 않고 표시만 한다. 분석에서 따로 집계한다. 두 종류를 턴마다 둔다
   - `closed_book_knowledge`: 문서 없이 물어 사전 지식으로 맞히는지 (모르면 UNKNOWN)
   - `closed_book_grounded`: 실험 답변 지시문(mt_answer_v2, NOT FOUND 규칙)으로 문서·기록 없이 물어 NOT FOUND 대신 정답을 내는지.
     **압축 결과를 오염시키는 쪽은 이것이다** (압축으로 정보를 잃어도 맞힐 수 있으므로)
3. 사람 검수의 "제외" 판정 (`docs/review/` 검수 시트)

생성 단계의 재요청은 스키마·규칙 위반(형식 오류)일 때 1회만 한다. 정답률을 보고 다시 생성하지 않는다.

| 시나리오 | 턴 | 사유 | 날짜 | 결정한 사람 |
|---|---|---|---|---|
| (아직 없음) | | | | |

## 파일

| 파일 | 내용 |
|---|---|
| `v2_01_auth_switch.json` | 묶음 v2_01 (보안·인증), draft |
| `v2_02_response_design.json` | 묶음 v2_02 (응답 상태·형식), draft |

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

**fact_judge_v3** 를 쓴다 (none 포함 모든 압축기와 closed-book 검사에 똑같이, 결과에 채점 버전을 기록).

- 대안(accept_alternatives)이 없는 fact 에서는 v3 가 v2 와 글자 그대로 같은 프롬프트임을 테스트로 확인했다 (`tests/test_fact_judge_v3.py`).
- 사람 라벨 80행 비교([`docs/results/judge_version_agreement_v2_v3.md`](../../../docs/results/judge_version_agreement_v2_v3.md))의
  v2 0.863 / v3 0.850 차이(1행)는 같은 프롬프트에서의 채점기 변동이다 (80행에는 대안이 없다). v3 가 나쁘다는 근거가 아니다.
- 대안 블록이 붙은 판정은 이 비교로 잴 수 없으므로, v2 시나리오 검수 때 사람 라벨로 따로 확인한다
  (검수 시트의 `alt_judgments` 열에 판정, `alt_judge_label` 열에 맞음 / 틀림).
