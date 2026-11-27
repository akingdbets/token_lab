# mt_scenario_gen_v2

multiturn-v2 시나리오 후보 생성 프롬프트 (생성 모델 gpt-6.1-sol). `src/multiturn/scenario_gen.py` 가 읽는다.
`{pages}` 는 묶음 페이지 원문, `{bundle}` 은 페이지 경로 목록, `{scenario_id}`·`{topic}` 은 bundles.json 의 값이다.
`## repair` 는 검사 오류가 있을 때 1회만 보내는 재요청이다.

v1 과 다른 점 (2026-11-28, 샘플 closed-book 검사 결과에 따른 설계 변경. DESIGN.md 변경 이력)
- standalone_question 에 원래 질문에 없던 key_entity·답 내용을 넣지 않는다 (검사기가 오류로 잡는다)
- 사용자가 대화 중 정하는 프로젝트 고유 값 (source=user) 과 사용자 발화 인용 {quote, user_turn, fact_idx}
- fact_meta.source (doc | user), recall·synthesis key_fact 의 user 비율 30~50%, user 값을 바꾸는 update 1개 이상
- 문서 고유 예시 값 우선, 태그 example
- synthesis 외 턴은 1~2가지만 묻는다 (asks 필드), key_fact 턴당 최대 3개

## system

You design evaluation scenarios for a study of conversation-history compression in multi-turn LLM assistants.
A scenario is a realistic multi-turn conversation in which a developer builds something with FastAPI and asks an assistant
questions. The assistant only knows what the documentation pages attached in the conversation say, plus what the user
said earlier in the conversation.
You write the user turns, the reference answers, the key facts a correct answer must convey, and verbatim evidence quotes.
You output one JSON object and nothing else.

## user

Write scenario `{scenario_id}` (topic: {topic}) using ONLY the documentation pages below.

# Pages (bundle)

{bundle}

{pages}

# Output format

Return ONE JSON object with exactly these top-level fields:
"schema_version": 2, "scenario_id": "{scenario_id}", "title": <short English title>, "topic": "{topic}", "status": "draft",
"bundle": <the page list above>, "generation": {{}}, "turns": [ ... ]

Each turn object has these fields (all required; use [] or null where a field does not apply):
- "turn": 0-based index, in order
- "turn_type": one of "new", "followup", "recall", "synthesis", "update", "same_doc_new_topic"
- "type": answer format, one of "fact" (a short value), "code" (a code snippet), "procedure" (steps), "multi" (several facts combined), "default"
- "question": what the user types in the conversation (English)
- "asks": a list of the distinct things this question asks for, one short phrase each (see "Question size")
- "standalone_question": the question rewritten so it is understandable WITHOUT the conversation (see "Standalone question")
- "answer": the reference answer (concise, correct according to the pages and the values the user set)
- "key_facts": 1 to 3 short sentences, each one essential fact a correct answer must convey
- "fact_meta": one object per key fact, in the same order: {{"source": "doc" | "user", "accept_alternatives": [...], "tags": [...]}}
- "key_entities": exact identifiers or values that a correct answer contains, copied exactly from the page text
  or from a user message this turn may rely on
- "evidence_pages": the page paths attached to THIS user message ([] when no page is attached)
- "depends_on": earlier turn numbers whose information is needed to answer (never the current or a later turn)
- "evidence": at least one quote per key fact. A quote from a page is {{"quote": ..., "page": ..., "fact_idx": ...}}.
  A quote from a user message is {{"quote": ..., "user_turn": <turn number>, "fact_idx": ...}}
- "alt_evidence": [{{"quote": ..., "page": ..., "fact_idx": ..., "alt_idx": ...}}] one quote per accepted alternative ([] if none)
- "changes": update turns only, [{{"what": ..., "from": ..., "to": ...}}]; otherwise null
- "affects": update turns only, the later turn numbers that must be answered under the changed condition; otherwise null
- "source_turn": same_doc_new_topic turns only, the earlier turn where that page was attached; otherwise null

# Turn types

- new: attaches one or two pages from the bundle (in "evidence_pages") and asks about them.
- followup: continues the immediately previous turn (depends_on contains the previous turn); no page attached.
- recall: needs information from an earlier turn without re-attaching anything. Refer to it only through the conversation
  ("the header name we picked", "that expiry"), never by naming a page, tutorial or document.
- synthesis: combines information from two or more earlier turns; no page attached.
- update: the user CHANGES a condition, requirement or project value stated earlier ("let's switch from X to Y",
  "actually make the expiry 45 minutes"). The update turn itself also asks a question that can be answered under the new condition.
  List what changed in "changes" and the later turns that must follow the new condition in "affects";
  every turn in "affects" must have the update turn in its depends_on, and its reference answer must follow the NEW condition.
- same_doc_new_topic: asks about a DIFFERENT section (different "##" heading) of a page attached at least 3 turns earlier,
  without re-attaching it. Set "source_turn" to the turn that attached the page and include it in depends_on.
  Its page evidence quotes must come from that page, from a section that no earlier turn quoted.

# Project values the user decides (source = "user")

The developer makes project-specific decisions during the conversation and states them in their own messages, for example
"our access tokens should expire after 17 minutes", "we'll send the tenant id in a header called X-Tenant-Key",
"our API version prefix is /v3". These values are NOT in the pages; a model can only know them from the conversation.

- Introduce 3 to 5 such values in the "question" text of new or followup turns (state the value plainly in the user's words).
  Pick values that are unusual enough that nobody could guess them (17 minutes, not 30 minutes; X-Tenant-Key, not X-Token),
  and invent your own: do not reuse the example values in this paragraph.
- Reference answers of later turns must use these values where they apply (for example the code uses timedelta(minutes=17)).
- A key fact whose essential value comes from what the user said has "source": "user", and its evidence quotes the user's
  message: {{"quote": <exact words from that turn's "question">, "user_turn": <that turn>, "fact_idx": ...}}.
  The quoted user turn must be this turn or a turn reachable through depends_on (directly or through the chain).
- Every other key fact has "source": "doc" and at least one page quote.
- Use these values as targets of recall, synthesis and update:
  among all key facts of recall and synthesis turns, 30% to 50% must have "source": "user" (the rest "doc"; keep both).
  At least one update turn changes a user value (its key facts include a "source": "user" fact quoting the update turn itself).

# Standalone question

- "standalone_question" asks for exactly the same facts as "question", understandable without the conversation.
- It must NOT reveal the answer: never put in it a key_entity, value, name or code that the original "question" does not
  already contain. The validator rejects any key_entity that appears in standalone_question but not in question.
- Refer to conversation-only information generically instead of stating it: "the access-token expiry the team chose",
  "the custom header name the project uses", "the status code the endpoint was changed to".
  It is expected and fine that such a question cannot be answered without the conversation.

# Question size

- Every turn except synthesis asks about 1 or 2 things only. "asks" lists them (1 or 2 entries; synthesis may have more).
  Do not chain several questions into one message.
- At most 3 key facts per turn.

# Required structure (the validator checks all of these)

- 16 to 20 turns. Turns 0 and 1 are "new".
- Every bundle page is attached exactly once across the scenario (so the conversation history grows past 15k tokens).
  Split the turns into thirds by index; each third must contain at least 2 turns that attach pages.
- Minimum counts: new 7, followup 2, recall 3, synthesis 2, update 2, same_doc_new_topic 2.
- At least 2 recall turns whose distance (current turn minus the smallest depends_on) is 6 or more.
- At least 1 synthesis turn that depends on 3 or more different earlier turns.
- The last 3 turns contain one recall with distance 6 or more and one synthesis.
- No update turn in the last 3 turns. Never more than 3 consecutive turns of the same type.

Recommended skeleton (19 turns; you may change it only if every rule above still holds):
0 new, 1 new, 2 followup, 3 new, 4 update, 5 new, 6 followup, 7 same_doc_new_topic, 8 new, 9 recall (distance >= 6),
10 new, 11 update, 12 new, 13 synthesis (3+ turns), 14 same_doc_new_topic, 15 new, 16 recall (distance >= 6), 17 recall, 18 synthesis.

# Difficulty rules

- Questions never contain source cues: no page titles, file names, "tutorial", "guide", "the first/earlier/other doc/page",
  "going back to", "in the docs". Point back only through the conversation itself.
- Prefer facts a model would NOT know without the pages: the specific example values these pages use
  (example tokens, secrets, usernames, item names, numbers, header values in the examples) and the exact behavior they describe.
  Avoid general FastAPI/HTTP knowledge (what 404 means, that Depends injects dependencies).
  Tag key facts that ask for such a page-specific example value "example" (aim for at least a third of the "doc" facts).
- Use values and names that look alike across the bundle pages (different status codes, defaults, ports, header names or
  parameter names in several pages) only where mixing them up actually gives a wrong answer. Tag only those key facts
  "confusable" (at least 2 in the scenario, and only when a concrete look-alike value exists in the bundle or conversation).
- Include at least 3 key facts whose correctness depends on a condition, a negation or a range
  ("only when", "does not", "below 200", "at least"). Tag them "condition", "negation" or "range".
- accept_alternatives: list another answer ONLY if the pages explicitly present it as an equally valid way to satisfy the question
  (for example two documented ways to change a status code). Give each alternative its own alt_evidence quote. Usually [].

# Evidence quotes

- Copy each quote EXACTLY from the page text or from the user's "question" text: same characters, same backticks, same
  punctuation. Do not paraphrase, do not join pieces from different places, do not add "...".
  Keep quotes short (one sentence or one code line, under 200 characters).
- A page quote's page must be attached in this turn or in a turn this turn depends on (directly or through its depends_on chain).
- key_entities must appear verbatim in those pages or in those user messages.

Return only the JSON object.

## repair

The scenario you returned failed automatic checks. Fix ONLY the listed problems, keep everything else the same, and return the complete corrected JSON object only.

Problems:
{errors}
