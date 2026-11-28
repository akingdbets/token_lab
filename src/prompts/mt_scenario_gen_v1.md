# mt_scenario_gen_v1

multiturn-v2 시나리오 후보 생성 프롬프트 (생성 모델 gpt-6.1-sol). `src/multiturn/scenario_gen.py` 가 읽는다.
`{pages}` 는 묶음 페이지 원문, `{bundle}` 은 페이지 경로 목록, `{scenario_id}`·`{topic}` 은 bundles.json 의 값이다.
`## repair` 는 검사 오류가 있을 때 1회만 보내는 재요청이다.

## system

You design evaluation scenarios for a study of conversation-history compression in multi-turn LLM assistants.
A scenario is a realistic multi-turn conversation in which a developer builds something with FastAPI and asks an assistant
questions. The assistant only knows what the documentation pages attached in the conversation say.
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
- "standalone_question": the same question rewritten so it is understandable WITHOUT the conversation and asks for exactly the same facts
- "answer": the reference answer (concise, correct according to the pages)
- "key_facts": 1 to 3 short sentences, each one essential fact a correct answer must convey
- "fact_meta": one object per key fact, in the same order: {{"accept_alternatives": [...], "tags": [...]}}
- "key_entities": exact identifiers or values from the page text that a correct answer contains (copy them exactly as they appear in the page)
- "evidence_pages": the page paths attached to THIS user message ([] when no page is attached)
- "depends_on": earlier turn numbers whose information is needed to answer (never the current or a later turn)
- "evidence": [{{"quote": ..., "page": ..., "fact_idx": ...}}] at least one quote per key fact
- "alt_evidence": [{{"quote": ..., "page": ..., "fact_idx": ..., "alt_idx": ...}}] one quote per accepted alternative ([] if none)
- "changes": update turns only, [{{"what": ..., "from": ..., "to": ...}}]; otherwise null
- "affects": update turns only, the later turn numbers that must be answered under the changed condition; otherwise null
- "source_turn": same_doc_new_topic turns only, the earlier turn where that page was attached; otherwise null

# Turn types

- new: attaches one or two pages from the bundle (in "evidence_pages") and asks about them.
- followup: continues the immediately previous turn (depends_on contains the previous turn); no page attached.
- recall: needs information from an earlier turn without re-attaching anything. Refer to it only through the conversation
  ("the header name we used earlier", "that timeout"), never by naming a page, tutorial or document.
- synthesis: combines information from two or more earlier turns; no page attached.
- update: the user CHANGES a condition or requirement stated earlier ("let's switch from X to Y", "actually the limit should be ...").
  The update turn itself also asks a question that can be answered under the new condition.
  List what changed in "changes" and the later turns that must follow the new condition in "affects";
  every turn in "affects" must have the update turn in its depends_on, and its reference answer must follow the NEW condition.
- same_doc_new_topic: asks about a DIFFERENT section (different "##" heading) of a page attached at least 3 turns earlier,
  without re-attaching it. Set "source_turn" to the turn that attached the page and include it in depends_on.
  Its evidence quotes must come from that page, from a section that no earlier turn quoted.

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
- Use values and names that look alike across the bundle pages (for example different status codes, defaults, ports,
  header names or parameter names that appear in several pages). Ask questions where mixing them up gives a wrong answer.
  Tag such key facts "confusable" (at least 2 in the scenario).
- Include at least 3 key facts whose correctness depends on a condition, a negation or a range
  ("only when", "does not", "below 200", "at least"). Tag them "condition", "negation" or "range".
- Prefer facts that a model would NOT know without the pages (specific example values, the exact behavior these pages describe).
  The standalone_question will be asked without the pages to check this.
- accept_alternatives: list another answer ONLY if the pages explicitly present it as an equally valid way to satisfy the question
  (for example two documented ways to change a status code). Give each alternative its own alt_evidence quote. Usually [].

# Evidence quotes

- Copy each quote EXACTLY from the page text above: same characters, same backticks, same punctuation. Do not paraphrase,
  do not join pieces from different places, do not add "...". Keep quotes short (one sentence or one code line, under 200 characters).
- A quote's page must be attached in this turn or in a turn this turn depends on (directly or through its depends_on chain).
- key_entities must appear verbatim in those pages.

Return only the JSON object.

## repair

The scenario you returned failed automatic checks. Fix ONLY the listed problems, keep everything else the same, and return the complete corrected JSON object only.

Problems:
{errors}
