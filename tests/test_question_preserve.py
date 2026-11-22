import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from compressors.question_preserve import QuestionPreserveCompressor,units,bm25,terms
from compressors import REGISTRY

class Engine:
    def compress_prompt(self,**kwargs):return {'compressed_prompt':kwargs['context'][0]}
class Broken:
    def compress_prompt(self,**kwargs):raise RuntimeError('deliberate failure')

def tokens(x):return len(x.split())
def total(x):return 8+tokens(x)

class QuestionPreserveTests(unittest.TestCase):
    def test_units_and_bm25(self):
        text='## Document: demo\nUnrelated words here.\nIf release 2.9.0 is used, call `fetch_item`.\n```python\nfetch_item(x)\n```\n'
        spans=units(text);self.assertTrue(any(k=='code' for a,z,k in spans))
        self.assertTrue(all(0<=a<z<=len(text) for a,z,k in spans))
        scores=bm25('Which release allows fetch_item?',text,spans)
        self.assertIn('2.9.0',text[spans[scores.index(max(scores))][0]:spans[scores.index(max(scores))][1]])

    def test_all_modes_obey_budget_and_copy_protected_spans(self):
        text='## Document: demo\nIf cache_enabled is True, APIClient.fetch requires release 2.9.0 and never returns None.\nOther information about workers and memory appears in a separate paragraph.\nMore unrelated details for the context budget repair.\n'
        for mode in ['identifiers','sentences','combined']:
            c=QuestionPreserveCompressor(mode=mode,engine_factory=Engine)
            r=c.compress_budget('When does APIClient.fetch return None?',text,'system',35,total,tokens)
            self.assertLessEqual(total(r.context),35)
            self.assertEqual(r.question,'When does APIClient.fetch return None?')
            for span in r.info['protected_spans']:
                self.assertEqual(text[span['start']:span['end']],span['text'])
                self.assertIn(span['text'],r.context)
            self.assertEqual(r.info['compression_api_calls'],0)

    def test_failures_are_explicit_and_label_free_signature(self):
        import inspect
        c=QuestionPreserveCompressor(engine_factory=Broken)
        r=c.compress_budget('cache?', 'cache uses APIClient with 2.9.0\nOther content.', 'sys',20,total,tokens)
        self.assertEqual(r.info['status'],'inference_failure_extractive_fallback')
        self.assertIsNotNone(r.info['inference_error'])
        args=set(inspect.signature(c.compress_budget).parameters)
        self.assertFalse(args & {'answer','evidence','key_facts','qid','response','answer_core'})

    def test_impossible_budget_is_reported(self):
        c=QuestionPreserveCompressor(engine_factory=Engine)
        r=c.compress_budget('question','A document about APIClient.','sys',1,total,tokens)
        self.assertGreater(r.info['overflow_tokens'],0)
        self.assertIsNotNone(r.info['overflow_reason'])

    def test_registration_leaves_baselines_intact(self):
        for key in ['qp_identifiers_r30','qp_sentences_r30','qp_combined_r30']:self.assertIn(key,REGISTRY)
        self.assertEqual(REGISTRY['llmlingua2_r30'].retain_ratio,.3)
        self.assertEqual(REGISTRY['llmlingua2_r50'].retain_ratio,.5)

if __name__=='__main__':unittest.main()
