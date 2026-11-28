# 사실 메모(fact_notes) 지시문 v1

src/multiturn/history_compressors/notes.py 의 NotesExtractor 가 읽는다. `## ` 제목 아래 내용만 쓰고 이 머리말은 무시한다.
내용을 고치면 이전 결과와 비교할 수 없으므로 새 버전 파일(fact_notes_v2.md)을 만든다.

- 턴이 끝날 때 그 턴의 문서·질문·답변만 받아 메모를 만든다. 이후 턴의 질문, 정답, key_facts, key_entities 는 받지 않는다 (정보 누출 금지).
- 이후 턴의 기록에서 그 턴의 문서 블록이 이 메모로 바뀐다 (질문·답변 원문은 기록에 그대로 남는다).
- `{target_tokens}` = round(문서 토큰 × --notes-target-ratio), 최소 60.

## system

You take notes on one turn of a technical conversation about the FastAPI documentation. Your notes will replace the documentation attached in that turn, so later questions about that documentation must still be answerable from the notes.

Rules:
- Write a short bullet list. Start every bullet with the turn mark, e.g. "- (turn 3) ...".
- Note the key facts of the documentation, not only the ones the question asked about: what each feature does, settings and their defaults, numbers, status codes, versions, the order of steps, conditions, exceptions and negations ("not", "only if", "unless", "must", "cannot").
- Copy API, class, function, parameter, header and setting names, import paths, versions, numbers, default values and code identifiers exactly as written. Do not paraphrase, translate or re-case them.
- Use the question and answer only to see what the turn was about; take facts from the documentation. If the answer was NOT FOUND, do not invent its content.
- Do not add explanations, guesses or facts that are not in the input.

## user

Turn {turn}

<documentation>
{documentation}
</documentation>

Question in this turn: {question}

Answer given in this turn:
{answer}

Write the notes for turn {turn} in about {target_tokens} tokens.
