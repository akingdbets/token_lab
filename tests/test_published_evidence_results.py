import csv
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_evidence_results import DATA,read_metrics,analyze,oracle_summary

class PublishedResultsTests(unittest.TestCase):
    def test_published_pairs_and_statistics(self):
        result=analyze(read_metrics(DATA/'metrics.csv'))
        self.assertEqual(result['splits']['dev']['questions'],35)
        independent=result['splits']['independent']
        self.assertEqual(independent['questions'],31)
        self.assertEqual(independent['document_clusters'],8)
        self.assertAlmostEqual(independent['conditions']['llmlingua2_r30']['accuracy'],.6397849462365591)
        self.assertAlmostEqual(independent['conditions']['qp_combined_r30']['accuracy'],.8709677419354839)
        c=independent['contrasts']['qp_combined_r30 - llmlingua2_r30']
        self.assertEqual((c['improved'],c['worsened'],c['unchanged']),(10,1,20))
        self.assertAlmostEqual(c['question_ci'][0],.06451612903225808)
        self.assertAlmostEqual(c['question_ci'][1],.39247311827956993)
        self.assertLessEqual(independent['conditions']['qp_combined_r30']['max_abs_token_delta_vs_r30'],1)
        expected=json.loads((DATA/'statistics.json').read_text())
        self.assertEqual(result['splits'],expected['splits'])

    def test_missing_or_duplicate_pair_is_rejected(self):
        with (DATA/'metrics.csv').open(newline='') as f:
            reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        for bad in [rows[:-1],rows+[rows[0]]]:
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'metrics.csv'
                with p.open('w',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(bad)
                with self.assertRaises(ValueError):read_metrics(p)

    def test_corpus_and_quotes_match_export_manifest(self):
        root=DATA.parent;manifest=json.loads((DATA/'manifest.json').read_text())
        for name,entry in manifest.items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),entry['sha256'])
        sources={s['url']:s for s in json.loads((DATA/'sources.json').read_text())}
        for q in json.loads((DATA/'independent_qa.json').read_text()):
            source=sources[q['source_url']];text=(root/'corpus'/f"{source['module']}.md").read_text()
            self.assertEqual(source['text_sha256'],hashlib.sha256(text.encode()).hexdigest())
            for e in q['evidence']:self.assertIn(e['quote'],text)
        provenance=json.loads((DATA/'provenance.json').read_text())
        path='src/compressors/question_preserve.py'
        self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),provenance['original_code_hashes'][path])

    def test_oracle_recovery_excludes_already_correct_baselines(self):
        result=oracle_summary(DATA/'oracle_metrics.csv')
        self.assertEqual(result['oracle']['n'],30)
        self.assertEqual(result['oracle']['recovery_eligible_n'],28)
        self.assertEqual(result['oracle']['recovered_to_none_n'],28)
        self.assertEqual(result['baseline']['fully_correct_rate'],2/30)

if __name__=='__main__':unittest.main()
