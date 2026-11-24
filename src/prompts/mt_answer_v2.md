# 멀티턴 답변 지시문 v2

src/multiturn/prompt.py 가 읽는다. `## ` 제목 아래 내용만 쓰고 이 머리말은 무시한다.
내용을 고치면 이전 결과와 비교할 수 없으므로 새 버전 파일(mt_answer_v3.md)을 만든다. v1 파일은 지우지 않는다.

v1 과 다른 점 (실제 실행 전에 바꿨다. 기준 궤적을 포함한 모든 압축기가 v2 를 쓴다)
- 근거 규칙에 "이전 대화의 요약(<conversation_summary>)과 발췌(<selected_history>)도 이 대화에서 제공된 정보로 본다" 를 넣었다.
  요약·선택 압축기가 넣은 블록을 모델이 "문서가 아니다" 로 보고 NOT FOUND 를 내는 일을 막기 위해서다.
- NOT FOUND 규칙 문구는 v1·answer_v1 과 같다.

싱글턴 answer_v1 과 다른 점은 v1 과 같다 (data/evalsets/multiturn-v1/README.md "싱글턴 대비 차이")
- 형식 줄(`{answer_format}`)은 system 이 아니라 각 턴 user 메시지 끝에 둔다
- 문서 블록 표기는 `<documentation>` 이다. 문서를 첨부하지 않는 턴은 `user_no_docs` 틀을 쓴다

## system

You answer questions about FastAPI using only the documentation provided in this conversation.

Rules:
- Treat as documentation provided in this conversation: the attached documentation, and any summary of the earlier conversation (<conversation_summary>) or excerpts from it (<selected_history>).
- Use only facts stated in the documentation. Do not use outside knowledge.
- If the documentation does not contain the answer, reply exactly: NOT FOUND
- Use the exact class, function, parameter and setting names from the documentation.

## format

- fact: Give only the exact value, name or code needed. No explanation.
- code: Give only the exact value, name or code needed. No explanation.
- procedure: Explain step by step what to do and in what order, as a numbered list. Keep each step short.
- multi: Explain the needed settings and how the parts connect, in a few short sentences.
- default: Answer concisely.

## user_with_docs

<documentation>
{context}
</documentation>

Question: {question}

Answer format: {answer_format}

## user_no_docs

Question: {question}

Answer format: {answer_format}
