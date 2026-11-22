import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from final_experiment import bootstrap,clusters,BodyParser,parse_json_response

class AnalysisTests(unittest.TestCase):
    def test_constant_paired_effect_bootstrap(self):
        for cluster in [False,True]:
            interval=bootstrap([.5]*4,['a','a','b','b'],1000,7,cluster)
            self.assertEqual(interval['low'],.5)
            self.assertEqual(interval['high'],.5)
        self.assertIsNone(bootstrap([1,0],['a','a'],100,7,True))

    def test_bootstrap_seed_reproducible(self):
        a=bootstrap([-.5,0,.5,1],['a','a','b','c'],1000,7)
        b=bootstrap([-.5,0,.5,1],['a','a','b','c'],1000,7)
        self.assertEqual(a,b)
        self.assertLessEqual(a['low'],.25)
        self.assertGreaterEqual(a['high'],.25)

    def test_shared_documents_form_connected_clusters(self):
        items=[{'id':'a','source_files':['d1']},{'id':'b','source_files':['d2']},
               {'id':'bridge','source_files':['d1','d2']},{'id':'c','source_files':['d3']}]
        groups=clusters(items)
        self.assertEqual(groups['a'],groups['b'])
        self.assertEqual(groups['a'],groups['bridge'])
        self.assertNotEqual(groups['a'],groups['c'])

    def test_html_extracts_main_body_and_preserves_code(self):
        p=BodyParser();p.feed('<div>nav</div><div role="main"><h1>API</h1><div><pre>x = 1\n</pre></div><p>Only if enabled.</p></div><div>footer</div>')
        text=''.join(p.out)
        self.assertNotIn('nav',text);self.assertNotIn('footer',text)
        self.assertIn('```python\nx = 1',text)
        self.assertIn('Only if enabled.',text)
        self.assertEqual(parse_json_response('```json\n[{"x":1}]\n```'),[{'x':1}])

if __name__=='__main__':unittest.main()
