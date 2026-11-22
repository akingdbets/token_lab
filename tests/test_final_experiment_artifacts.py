"""Offline checks on the frozen independent study artifacts; no model calls."""
import hashlib
import json
import unittest
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/analysis/final-experiment'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class FrozenArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (OUT/'independent_dataset.json').exists():raise unittest.SkipTest('Independent dataset not yet created')
        cls.data=load(OUT/'independent_dataset.json');cls.meta=load(OUT/'dataset_metadata.json');cls.freeze=load(OUT/'algorithm_freeze.json')

    def test_freeze_and_dataset_provenance(self):
        self.assertEqual(self.meta['freeze_sha256'],sha(OUT/'algorithm_freeze.json'))
        self.assertEqual(self.meta['dataset_sha256'],sha(OUT/'independent_dataset.json'))
        for name,digest in self.freeze['code_hashes'].items():self.assertEqual(sha(ROOT/name),digest)
        for source in self.meta['sources']:
            self.assertGreaterEqual(datetime.fromisoformat(source['fetched_utc']),datetime.fromisoformat(self.freeze['time_utc']))
            self.assertEqual(source['text_sha256'],sha(OUT/'sources'/f"{source['module']}.md"))
            self.assertLessEqual(source['old_corpus_12word_shingle_overlap_fraction'],.05)
            self.assertEqual(source['old_document_overlap_ids'],[])

    def test_admission_uses_exact_sources_and_audit(self):
        old=[q for name in ['qa_dev.json','qa_test.json'] for q in load(ROOT/'data/evalsets/claude-v1'/name)]
        self.assertFalse({q['id'] for q in self.data}&{q['id'] for q in old})
        olddocs={d for q in old for d in q.get('source_files',[])}
        self.assertEqual(len({q['id'] for q in self.data}),len(self.data))
        self.assertEqual(len({q['question'] for q in self.data}),len(self.data))
        for q in self.data:
            self.assertFalse(set(q['source_files'])&olddocs)
            self.assertTrue(load(OUT/'sources'/f"{q['id']}.audit.json")['accepted'])
            context=(ROOT/q['context_path']).read_text()
            for e in q['evidence']:self.assertIn(e['quote'],context)

    def test_full_evaluation_if_present(self):
        p=OUT/'independent/summary.json'
        if not p.exists():self.skipTest('Independent evaluation not yet finished')
        s=load(p);rows=[json.loads(x) for x in (OUT/'independent/trials.jsonl').read_text().splitlines()]
        self.assertEqual(s['completed_trials'],len(self.data)*6)
        self.assertEqual(len(rows),len({(r['qid'],r['condition']) for r in rows}))
        for r in rows:
            self.assertEqual(r['compression_api_calls'],0)
            self.assertEqual(r['compression_api_tokens'],0)
            self.assertEqual(r['answer_model'],'gpt-6.1-terra')
            self.assertEqual(r['judge_sampling']['model'],'deepseek-flash')
            self.assertEqual(r['answer']['sampling']['seed'],42)
            self.assertEqual(sha(ROOT/r['compression']['context_path']),r['compression']['context_sha256'])

if __name__=='__main__':unittest.main()
