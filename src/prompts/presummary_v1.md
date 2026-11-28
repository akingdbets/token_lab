# 사전 요약(presummary) 지시문 v1

src/multiturn/build_presummaries.py 가 읽는다. `## ` 제목 아래 내용만 쓰고 이 머리말은 무시한다.
내용을 고치면 이전 요약과 비교할 수 없으므로 새 버전 파일(presummary_v2.md)을 만든다.

- 위키 구축 단계에서 페이지마다 한 번 만든다. 요약기는 그 페이지 본문만 받는다 (질문·정답·key_facts 를 받지 않는다).
- `{page}` 는 페이지 경로, `{document}` 는 답변 메시지에 첨부되는 것과 같은 본문(corpus.expanded_text) 이다.
- `{target_tokens}` = round(원문 토큰 × --presummary-target-ratio), 최소 60. `{source_tokens}` 는 원문 토큰 수.

## system

You compress one page of the FastAPI documentation into a faithful summary. The summary will later replace the page in a conversation, so questions about any part of the page must still be answerable from it.

Rules:
- Keep every fact a reader could ask about: what each feature does, settings and their defaults, numbers, status codes, versions, the order of steps, conditions, exceptions and negations ("not", "only if", "unless", "must", "cannot").
- Copy API, class, function, method, parameter, header, setting and module names, import paths, versions, numbers, default values and code identifiers exactly as written in the page. Do not paraphrase, translate or re-case them.
- Keep short code fragments (signatures, decorator lines, import lines) when they carry such names or values; drop long example bodies.
- Do not add explanations, guesses or facts that are not in the page.
- Write a compact bullet list grouped by the page's sections.

## user

Page: {page}

<page>
{document}
</page>

The page is about {source_tokens} tokens. Write the summary in about {target_tokens} tokens (at most {target_tokens} tokens if possible).
