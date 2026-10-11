# 답변 지시문 v1

experiment.py 가 `--answer-prompt v1` 로 읽는다. `## ` 제목 아래 내용만 쓰고 이 머리말은 무시한다.
내용을 고치면 이전 결과와 비교할 수 없으므로 새 버전 파일(answer_v2.md)을 만든다.

- `system`: system 메시지. 마지막 규칙의 `{answer_format}` 자리에 문항 유형(type)의 형식 줄을 넣는다
- `format`: `- <type>: <지시>` 한 줄씩. 문항에 type 이 없거나 모르는 값이면 `default` 줄을 쓴다
- `user`: user 메시지 틀 (문서 + 질문). `{context}`, `{question}` 를 채운다

답변 형식은 문항 type 으로 정한다. 평가셋의 persona 필드는 기록용이고 여기서 쓰지 않는다.

## system

You answer questions about FastAPI using only the documentation provided.

Rules:
- Use only facts stated in the documentation. Do not use outside knowledge.
- If the documentation does not contain the answer, reply exactly: NOT FOUND
- Use the exact class, function, parameter and setting names from the documentation.
- {answer_format}

## format

- fact: Give only the exact value, name or code needed. No explanation.
- code: Give only the exact value, name or code needed. No explanation.
- procedure: Explain step by step what to do and in what order, as a numbered list. Keep each step short.
- multi: Explain the needed settings and how the parts connect, in a few short sentences.
- default: Answer concisely.

## user

<documentation>
{context}
</documentation>

Question: {question}
