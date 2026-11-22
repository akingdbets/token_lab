"""Run: python3 -m unittest discover -s scripts -p 'test_compression*.py'"""
import json
import tempfile
import unittest
from pathlib import Path
from compression_failure_review import build, locate, review_rows, complete, ROOT


class ReviewTests(unittest.TestCase):
    def test_locator_does_not_call_missing_quote_deleted(self):
        self.assertEqual(locate('abc', 'abc abc')['exact_offsets'], [0, 4])
        self.assertEqual(locate('abc', 'axc')['status'], 'candidate_unverified')
        self.assertEqual(locate('abc', None)['status'], 'unavailable')

    def test_real_pairs_and_human_defaults(self):
        run = ROOT/'results/runs/20261104-165320'
        if not run.exists():
            self.skipTest('Local experimental logs unavailable')
        records, denoms, issues, _ = build(run, ROOT/'data/evalsets/claude-v1/qa_test.json', 2, 42)
        self.assertFalse(issues)
        self.assertEqual(sum(r['cohort']=='decline' and r['compressor']=='llmlingua2_r30' for r in records),29)
        self.assertEqual(sum(r['cohort']=='decline' and r['compressor']=='llmlingua2_r50' for r in records),12)
        self.assertEqual(sum(d['paired'] for d in denoms),278)
        self.assertEqual(sum(d['sampled_success'] for d in denoms),16)
        rows=list(review_rows(records))
        self.assertEqual(len({r['review_id'] for r in rows}),len(rows))
        self.assertTrue(all(r['primary_cause']=='' and r['evidence_deleted']=='' and r['automatic_status']=='unverified' for r in rows))
        self.assertEqual([r['trial_id'] for r in records], [r['trial_id'] for r in build(run, ROOT/'data/evalsets/claude-v1/qa_test.json',2,42)[0]])

    def test_join_failure_and_partial_accuracy(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'contexts').mkdir()
            (p/'summary.json').write_text('{}')
            rows=[{'qid':'q','compressor':c,'qtype':'multi','answer_accuracy':a} for c,a in [('none',.75),('llmlingua2_r30',.5)]]
            (p/'trials.jsonl').write_text('\n'.join(map(json.dumps,rows)))
            dataset=p/'dataset.json';dataset.write_text('[]')
            records,_,issues,_=build(p,dataset,0,42)
            self.assertEqual(len(records),1)
            self.assertTrue(issues)
            self.assertIsNone(records[0]['original_context'])
            self.assertEqual(records[0]['dataset_item'],{})
            rows.append(rows[0]);(p/'trials.jsonl').write_text('\n'.join(map(json.dumps,rows)))
            self.assertEqual(build(p,dataset,0,42)[0],[])
            self.assertFalse(complete({'config':{'n_items':1},'results':{'none':{'n':1}}},rows))

if __name__=='__main__':
    unittest.main()
