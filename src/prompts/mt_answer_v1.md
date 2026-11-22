# 멀티턴 답변 지시문 v1

src/multiturn/prompt.py 가 읽는다. `## ` 제목 아래 내용만 쓰고 이 머리말은 무시한다.
내용을 고치면 이전 결과와 비교할 수 없으므로 새 버전 파일(mt_answer_v2.md)을 만든다.

싱글턴 answer_v1 과 다른 점 (자세한 내용은 data/evalsets/multiturn-v1/README.md "싱글턴 대비 차이")
- system 은 대화 내내 고정이라 문항 유형별 형식 줄(`{answer_format}`)을 system 이 아니라 각 턴 user 메시지 끝에 둔다
- 첫 줄의 "the documentation provided" 를 "the documentation provided in this conversation" 으로 바꿨다
- NOT FOUND 규칙은 answer_v1 과 같은 문구 그대로다 (압축으로 기록이 사라졌을 때 지어내는지, 모른다고 하는지가 recall 턴의 관찰값)
- 문서 블록 표기는 answer_v1 과 같은 `<documentation>` 이다. 문서를 첨부하지 않는 턴은 `user_no_docs` 틀을 쓴다

## system

You answer questions about FastAPI using only the documentation provided in this conversation.

Rules:
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
