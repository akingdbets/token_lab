# 평가셋 후보 (Claude 생성)

질문 후보는 Ollama 대신 Claude Code가 직접 만들고, 검사·필터·저장은 `dataset_builder.py --import` 로 했다.
문서 없이 풀기(closed-book)와 종합형 한 페이지 검사는 실험 모델(qwen2.5:7b) 기준으로 Ollama에서 실행한다.

| 항목 | 값 |
|---|---|
| 생성 모델 | Claude Opus 5.5 (`claude-opus-5-5`, Claude Code 세션) |
| 생성 일시 | 2026-10-06 (KST) |
| 문서 원천 | `data/openwiki/en` 본문 페이지 49개 (corpus kind="page"). 웹 검색·사전 지식 사용 안 함 |
| 대상·짝 | `targets.json` (`dataset_builder.py --list-targets` 결과) |

## 파일

| 파일 | 내용 |
|---|---|
| `claude_20261006_pilot.jsonl` | 시험 생성 17개 (페이지 5개 + 종합형 2쌍). 전체 파일에 그대로 포함됨 |
| `claude_20261006.jsonl` | 전체 후보 175개 (fact 55, code 55, procedure 48, multi 17) |
| `targets.json` | 페이지별 split·토큰 수·종합형 짝 후보 |

## 분량과 예외

- 페이지당 fact·code·procedure 각 1개.
- dev 페이지(6개)는 dev 문항이 모자라서 fact·code 를 1개씩 더 만들었다 (dev 문항 확보 목적).
- multi 17개: dev 3 (jwt↔password-flow 2, async-tests↔testing-dependencies 1), test 14. 모두 `targets.json` 의 링크 짝, 같은 split.
- 건너뛴 유형: `about/features-and-ecosystem.md` 의 procedure — 개요 페이지라 따라 할 절차가 없음.

## 생성 규칙 (전문)

근거와 내용은 오직 data/openwiki/en 의 본문 페이지(corpus kind="page")에서만. 웹 검색, 사전 지식 사용 금지.
quickstart.md, index.md 들은 질문 대상이 아니다. --list-targets 결과로 대상과 짝을 정한다.

생성 규칙 (dataset_builder 의 검사를 통과하도록 맞춘 것)
- 유형별 답 길이: fact·code 15단어 이하(값·이름·식별자만), procedure "1) ... 2) ..." 형식 2단계 이상 60단어 이하, multi 40단어 이하
- fact: 근거 중 최소 하나가 코드 블록 밖 문장. code: 근거 중 최소 하나가 코드 블록 안의 그 줄
- multi: --list-targets 의 짝(같은 split, 링크로 연결된 페이지)만 사용. key_entities 에 A 페이지에만 있는 것 1개 이상,
  B 페이지에만 있는 것 1개 이상. 두 페이지 모두에서 근거 인용. 두 페이지 사이에 실제로 있는 연결(링크된 맥락)을 묻고,
  관련 없는 두 주제를 억지로 엮지 말 것
- evidence: 정답을 "직접" 뒷받침하는 줄을 페이지 원문 그대로 복사 (백틱·따옴표 포함 그대로). 관련 없는 줄은 넣지 말 것
- key_entities: 1~5개, 페이지에 그대로 있는 문자열. 정답 값 자체를 반드시 포함. token, fields, example 같은 일반 단어 금지
- key_facts: 정답이 담아야 할 사실을 하나씩 독립적으로 검증 가능한 짧은 문장으로. 정답 값이 들어간 사실을 반드시 포함
- 질문: 페이지 제목 없이도 이해되게 주제를 넣고("In FastAPI, ..."), 페이지 문장을 6단어 이상 연속으로 베끼지 말 것,
  질문에 정답을 넣지 말 것, 한 가지만 물을 것, 질문과 답이 정확히 대응할 것
- 일반 웹 개발 상식이나 FastAPI 사용자가 문서 없이도 알 법한 내용은 피하고, 이 페이지에만 있는 구체적 값·설정·단계를 물을 것
- "문서에 언급 없음" 같은 답이 나오는 질문은 만들지 말 것
- persona
  * beginner: 어떤 기능을 구현하려면 무엇을 어떤 순서로 해야 하는지 (주로 procedure)
  * intermediate: 여러 기능을 함께 쓰는 법, 설정 방법 (procedure, multi)
  * advanced: 정확한 파라미터·기본값·코드 식별자만 (fact, code)

분량: 페이지당 fact, code, procedure 각 1개 (페이지 내용상 억지스러우면 그 유형은 건너뛰고 README 에 사유 기록),
multi 는 짝 15쌍 내외.

이번 생성의 persona 배정: fact·code → advanced, procedure → beginner, multi → intermediate.

## 알려진 한계

- 문서 없이 풀기 검사가 느슨하다. Qwen이 특정 문서를 가리키는 질문에 `UNKNOWN` 으로 답하는 경우가 많고,
  단어가 그대로 이어져야 정답으로 보는 규칙이라 뜻은 맞게 답해도 "모른다"로 판정될 수 있다 (채점 개선은 별도 작업).
- 정답은 위키(OpenWiki 생성물) 기준이다. 위키 내용이 FastAPI 원문과 다르면 위키를 따른다.
