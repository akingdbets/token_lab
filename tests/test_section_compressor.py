"""Structural, chain and resume tests; no remote calls or model downloads."""
import argparse
from dataclasses import replace
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from answer_prompts import load_answer_prompt
from compressors import Chain, PromptParts, get_compressor
from compressors.llmlingua2 import LLMLingua2Compressor
from compressors.section_select import SectionSelectCompressor, configure_section_compressor


TEXT = '''## Document: login.md
---
title: Login
source: hash
---
# Login
## Failure handling
When login fails, return the error.
```python
def login(user):
    if not user:
        raise Error(401)
```
## Gardening
Plant flowers. Water the garden every day.
## Storage
Store files in a clean directory. Back them up regularly.
'''


def messages(parts):
    return [{'role': 'system', 'content': parts.system},
            {'role': 'user', 'content': parts.context + '\nQuestion: ' + parts.question}]


def count(msgs):
    return sum(len(m['content']) for m in msgs) + 10


def compressor(**kwargs):
    return SectionSelectCompressor(message_builder=messages, message_counter=count, **kwargs)


class EchoEngine:
    def __init__(self): self.calls = []
    def compress_prompt(self, **kw):
        self.calls.append(kw)
        return {'compressed_prompt': kw['context'][0], 'origin_tokens': 100, 'compressed_tokens': 100}


class SectionTests(unittest.TestCase):
    def test_atomic_sections_and_nested_prefix(self):
        parts = PromptParts('system', TEXT, 'What happens when login fails?')
        a = compressor(retain_ratio=.8).compress(parts)
        b = compressor(retain_ratio=.5).compress(parts)
        self.assertLessEqual(set(b.info['selected_ids']), set(a.info['selected_ids']))
        self.assertEqual((b.system, b.question), (parts.system, parts.question))
        self.assertIn('def login(user):\n    if not user:\n        raise Error(401)\n```', b.context)
        self.assertIn('When login fails, return the error.', b.context)
        self.assertNotIn('source: hash', b.context)
        self.assertEqual(b.context, compressor(retain_ratio=.5).compress(parts).context)

    def test_budget_override_and_intact_best_section(self):
        parts = PromptParts('system', TEXT, 'login fails')
        c = compressor(retain_ratio=.9, input_budget=1)
        r = c.compress(parts)
        self.assertEqual(r.info['target_input_tokens'], 1)
        self.assertEqual(r.info['status'], 'best_section_exceeds_budget')
        self.assertTrue(r.info['budget_exceeded'])
        self.assertTrue(r.info['fixed_input_exceeds_budget'])
        self.assertEqual(len(r.info['selected_sections']), 1)
        self.assertIn('raise Error(401)', r.context)

    def test_no_gold_read_and_error_fallback(self):
        parts = PromptParts('s', TEXT, 'login', evidence=('injected untrusted answer marker',))
        normal = compressor().compress(parts)
        without = compressor().compress(replace(parts, evidence=()))
        self.assertEqual(normal.context, without.context)
        with patch('compressors.section_select.split_units', side_effect=ValueError('private secret')):
            result = compressor().compress(parts)
        self.assertEqual(result.context, TEXT)
        self.assertTrue(result.info['trace']['used_original'])
        self.assertNotIn('private secret', str(result.info))

    def test_source_order_and_zero_overlap_trace(self):
        r = compressor(retain_ratio=.8).compress(PromptParts('', TEXT, 'zzzzunknown'))
        self.assertFalse(r.info['query_overlap'])
        self.assertEqual(r.info['ranking'], list(range(len(r.info['sections']))))
        self.assertEqual(r.info['selected_ids'], sorted(r.info['selected_ids']))

    def test_validation_and_identity(self):
        for bad in [0, -1, 1.1, True, float('nan'), float('inf')]:
            with self.assertRaises(ValueError): compressor(retain_ratio=bad)
        for bad in [0, -1, True, .5]:
            with self.assertRaises(ValueError): compressor(input_budget=bad)
        parts = PromptParts('s', TEXT, 'q')
        self.assertEqual(compressor(retain_ratio=1).compress(parts).context, TEXT)
        self.assertEqual(compressor().compress(PromptParts('', '', '')).context, '')
        self.assertEqual(compressor().compress(PromptParts('', '# Heading only\n', '')).info['status'], 'no_content_sections')

    def test_rule_before_section_uses_stage_input_budget(self):
        parts = PromptParts('s', TEXT, 'login failure')
        rule = get_compressor('rule')
        section = compressor(retain_ratio=.5)
        cleaned = rule.compress(parts)
        r = Chain([rule, section]).compress(parts)
        trace = r.info['2:section_bm25']
        self.assertEqual(trace['input_tokens_raw'], count(messages(cleaned.parts)))
        self.assertEqual(trace['target_input_tokens'], count(messages(cleaned.parts)) // 2)
        self.assertEqual(r.context, section.compress(cleaned.parts).context)
        after = Chain([section, rule]).compress(parts)
        self.assertEqual(after.context, rule.compress(section.compress(parts).parts).context)
        self.assertIn('1:section_bm25', after.info)
        self.assertIn('2:rule', after.info)

    def test_llmlingua_both_orders_and_three_stage_chain(self):
        parts = PromptParts('s', TEXT, 'login failure', evidence=('quote',))
        for before in (False, True):
            engine = EchoEngine()
            lingua = LLMLingua2Compressor(engine_factory=lambda: engine)
            section = compressor()
            stages = [lingua, section] if before else [get_compressor('rule'), section, lingua]
            chain = Chain(stages)
            r = chain.compress(parts)
            self.assertEqual(len(engine.calls), 1)
            self.assertEqual((r.system, r.question), (parts.system, parts.question))
            self.assertIn('raise Error(401)', r.context)
            self.assertFalse(any(stage.get('trace', {}).get('used_original') for stage in r.info.values()))

    def test_registry_and_nested_configuration(self):
        chain = get_compressor('rule>section_bm25>llmlingua2')
        nested = Chain([get_compressor('none'), chain])
        configure_section_compressor(nested, messages, .7, 200)
        self.assertEqual(chain.stages[1].config()['input_budget'], 200)
        self.assertEqual(chain.stages[1].config()['retain_ratio'], .7)
        configure_section_compressor(chain, load_answer_prompt('v1').messages)

    def test_experiment_chain_resume_and_prompt_compatibility(self):
        import experiment as E
        from config import CFG
        from llm import LLM, LLMResult
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(E.load_answer_prompt('v1').sha256, 'd12495bd1412')
        def args(**updates):
            values = dict(compressors='none,rule>section_bm25>llmlingua2', split='dev', limit=1,
                ids=None, no_judge=True, judge_mode='per_fact', semantic=False, answer_prompt='v1',
                resume=None, section_retain_ratio=.8, section_input_budget=None)
            values.update(updates)
            return argparse.Namespace(**values)
        def fake_chat(self, msgs, **kw):
            return LLMResult(text='value', prompt_tokens=10, completion_tokens=1, latency=0,
                             model=self.model, finish_reason='stop')
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(CFG, 'root', Path(temp)), \
             patch.object(CFG, 'results_dir', Path(temp)/'results'), \
             patch.object(CFG, 'eval_dir', root/'data/evalsets/claude-v1'), \
             patch.object(LLM, 'chat', fake_chat), \
             patch.object(LLMLingua2Compressor, '_get_engine', return_value=EchoEngine()), \
             patch('llm.count_message_tokens', count), \
             patch('llm.count_tokens', len), \
             patch('experiment.count_message_tokens', count), \
             patch('experiment.count_tokens', len), \
             patch('sys.stdout', new_callable=io.StringIO):
            out = E.run(args())
            E.run(args(resume=out.name, section_retain_ratio=.2, section_input_budget=1))
            rows = [json.loads(l) for l in (out/'trials.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            meta = json.loads((out/'args.json').read_text())
            self.assertEqual(meta['args']['section_retain_ratio'], .8)
            self.assertIsNone(meta['args']['section_input_budget'])
            report = json.loads((out/'summary.json').read_text())
            self.assertEqual(report['compressors']['rule>section_bm25>llmlingua2']['2:section_bm25']['retain_ratio'], .8)
            with patch.object(CFG, 'results_dir', Path(temp)/'legacy_results'):
                legacy = E.run(args(compressors='none'))
                old_meta = json.loads((legacy/'args.json').read_text())
                for key in E.SECTION_ARG_DEFAULTS:
                    old_meta['args'].pop(key)
                (legacy/'args.json').write_text(json.dumps(old_meta))
                E.run(args(resume=legacy.name, section_retain_ratio=.2, section_input_budget=1))
                restored = json.loads((legacy/'args.json').read_text())['args']
                self.assertEqual(restored['section_retain_ratio'], .5)
                self.assertIsNone(restored['section_input_budget'])


if __name__ == '__main__': unittest.main()
