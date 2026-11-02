"""Reproduce committed section-selection inputs without answer/judge/model calls."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from answer_prompts import load_answer_prompt
from compressors.section_select import SectionSelectCompressor
from corpus import load_corpus
from experiment import build_context


def main():
    record = json.loads((ROOT / 'docs/04_실험결과/섹션선택_개발평가_근거_20261103.json').read_text())
    items = {x['id']: x for x in json.loads((ROOT / 'data/evalsets/claude-v1/qa_dev.json').read_text())}
    prompt = load_answer_prompt('v1')
    assert prompt.sha256 == record['answer_prompt']['sha256']
    corpus = load_corpus()
    count = 0
    for case in record['cases']:
        item = items[case['qid']]
        assert item['question'] == case['question']
        raw = build_context(corpus, item)
        assert hashlib.sha256(raw.encode()).hexdigest() == case['raw_context_sha256']
        parts = prompt.parts(raw, item['question'], item['type'])
        for state in case['states']:
            result = SectionSelectCompressor(input_budget=state['tokens'], message_builder=prompt.messages).compress(parts)
            assert result.info['input_tokens'] == state['tokens'], (case['qid'], state['name'])
            assert result.info['selected_sections'] == state['sections'], (case['qid'], state['name'])
            assert hashlib.sha256(result.context.encode()).hexdigest() == state['context_sha256']
            count += 1
    print(f'{count}/{count} historical contexts, tokens and section selections reproduced. No answer/judge calls.')


if __name__ == '__main__':
    main()
