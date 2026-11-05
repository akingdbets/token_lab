import json
import unittest
from pathlib import Path
from oracle_pilot import OUT, ROOT, CONDITIONS, load, validate, matched_placebo, messages, count_message_tokens, load_answer_prompt


class OracleTests(unittest.TestCase):
    def setUp(self):
        if not (OUT/'plan.json').exists():
            self.skipTest('Private raw oracle artifacts are not checked into Git')
        self.plan=load(OUT/'plan.json')

    def test_frozen_inputs_and_selection(self):
        validate(self.plan)
        self.assertEqual(len(self.plan['cases']),10)
        self.assertEqual(sum(c['category']=='A' for c in self.plan['cases']),5)
        keys={(t['qid'],t['condition'],t['repeat']) for t in self.plan['schedule']}
        self.assertEqual(len(keys),90)
        self.assertEqual({t['condition'] for t in self.plan['schedule']},set(CONDITIONS))
        self.assertEqual(len(load(OUT/'selection_audit.json')),41)

    def test_restoration_is_verbatim_and_inputs_are_matched(self):
        prompt=load_answer_prompt('v1')
        for c in self.plan['cases']:
            base=(ROOT/c['contexts']['baseline']).read_text()
            original=(ROOT/c['contexts']['original']).read_text()
            for quote in c['oracle_quotes']:
                source=(ROOT/'data/openwiki/en'/quote['page']).read_text()
                self.assertEqual(source[quote['source_char_start']:quote['source_char_start']+len(quote['text'])],quote['text'])
                self.assertIn(quote['text'],original)
            restored='\n'.join(q['text'] for q in c['oracle_quotes'])
            self.assertEqual((ROOT/c['contexts']['oracle']).read_text(),base+'\n\n'+restored)
            self.assertEqual((ROOT/c['contexts']['placebo']).read_text(),base+'\n\n'+c['placebo_quote'])
            self.assertIn(c['placebo_quote'],(ROOT/c['placebo_source']).read_text())
            for condition in ['oracle','placebo']:
                tokens=count_message_tokens(messages(prompt,c['item'],(ROOT/c['contexts'][condition]).read_text()))
                self.assertEqual(tokens,c['token_matching'][condition+'_total_input_est'])
            self.assertLessEqual(abs(c['token_matching']['placebo_minus_oracle_est']),1)

    def test_completed_results_if_available(self):
        path=OUT/'results.json'
        if not path.exists():
            self.skipTest('Experiment still running')
        rows=load(path)
        self.assertEqual(len(rows),90)
        self.assertEqual(len({(r['qid'],r['condition'],r['repeat']) for r in rows}),90)
        for r in rows:
            self.assertEqual(r['status'],'complete')
            self.assertIsNotNone(r['answer_accuracy'])
            self.assertEqual(r['fact_grade']['total_count'],len(r['key_facts']))
            self.assertEqual(r['answer']['result']['model'],'gpt-6.1-terra')
            self.assertEqual(r['answer']['sampling']['seed'],42)
            self.assertEqual(r['fact_sampling']['model'],'deepseek-flash')
        summary=load(OUT/'summary.json')
        self.assertEqual(summary['completed'],90)
        for s in summary['conditions']:
            self.assertEqual(s['n'],30 if s['category']=='all' else 15)

    def test_matching_does_not_invent_padding(self):
        case=self.plan['cases'][0];prompt=load_answer_prompt('v1')
        pool='Workers share a port and each worker uses independent memory. Kubernetes replicates containers.'
        text,stats=matched_placebo('base','A short sentence.',pool,prompt,case['item'])
        self.assertTrue(pool.startswith(text))
        self.assertTrue(text)


class PlaceboUnitTests(unittest.TestCase):
    def test_padding_is_a_verbatim_source_prefix_without_artifacts(self):
        from unittest.mock import patch
        class Prompt:
            def parts(self,context,question,qtype):return context
            def messages(self,context):return [{'role':'user','content':context}]
        pool='Workers share ports and use separate memory. A manager distributes requests.'
        with patch('oracle_pilot.count_message_tokens',lambda messages:len(messages[0]['content'].split())+8):
            text,stats=matched_placebo('base','A short sentence.',pool,Prompt(),{'question':'q','type':'fact'})
        self.assertTrue(text)
        self.assertTrue(pool.startswith(text))
        self.assertLessEqual(abs(stats['placebo_minus_oracle_est']),1)

if __name__=='__main__':unittest.main()
