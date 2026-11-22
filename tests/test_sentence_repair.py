import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from compressors import PromptParts, get_compressor
from compressors.base import Compressor
from compressors.repair import SentenceRepairCompressor, sentences

class Base(Compressor):
    targets = ('context',)
    def __init__(self, text): self.text = text
    def compress_context(self, question, context): return self.text

class RepairTest(unittest.TestCase):
    def make(self, output, **kwargs):
        return SentenceRepairCompressor(base=Base(output),
            token_counter=lambda t: len(t.split()), **kwargs)

    def test_low_similarity_restores_original_in_place(self):
        text = 'Tasks run in the order they were added. Cats sleep.'
        c = self.make('Tasks after. Cats sleep.', embed=lambda t: [1, 0] if 'order' in t else [0, 1])
        # Use a true subsequence so alignment is unambiguous.
        c.base = Base('Tasks. Cats sleep.')
        out = c.compress(PromptParts('sys', text, 'In what order do Tasks run?'))
        self.assertIn('Tasks run in the order they were added.', out.context)
        self.assertTrue(out.context.index('Tasks') < out.context.index('Cats'))
        self.assertEqual(out.info['restored_sentences'], 1)
        self.assertEqual(out.system, 'sys')

    def test_high_similarity_keeps_compression(self):
        c = self.make('Tasks run.', embed=lambda t: [1, 0])
        out = c.compress(PromptParts('', 'Tasks run after the response.', 'Tasks?'))
        self.assertEqual(out.context, 'Tasks run.')
        self.assertEqual(out.info['restored_sentences'], 0)

    def test_budget_blocks_restore(self):
        c = self.make('Tasks.', max_added_tokens=0, embed=lambda t: [1, 0] if 'run' in t else [0, 1])
        out = c.compress(PromptParts('', 'Tasks run after response.', 'Tasks?'))
        self.assertEqual(out.context, 'Tasks.')
        self.assertEqual(out.info['selected_sentences'][0]['action'], 'skip_budget')

    def test_missing_sentence_restored_before_next_sentence(self):
        c = self.make('Cats sleep.', embed=lambda t: [1, 0])
        out = c.compress(PromptParts('', 'Tasks run first. Cats sleep.', 'Tasks?'))
        self.assertLess(out.context.index('Tasks'), out.context.index('Cats'))

    def test_embedding_failure_is_logged_without_api_retry(self):
        def fail(t): raise RuntimeError('offline')
        c = self.make('Tasks.', embed=fail)
        out = c.compress(PromptParts('', 'Tasks run first.', 'Tasks?'))
        self.assertEqual(out.context, 'Tasks.')
        self.assertEqual(out.info['selected_sentences'][0]['action'], 'skip_embedding_error')

    def test_unrelated_question_no_embedding(self):
        c = self.make('Cats.', embed=lambda t: self.fail('unexpected embedding'))
        self.assertEqual(c.compress(PromptParts('', 'Cats sleep.', 'Planets?')).context, 'Cats.')

    def test_sentence_boundaries_preserve_versions_and_code(self):
        text = '## Document: x\nUse `x.y` in version 0.95.0. Next step.\n```py\nfoo.bar()\n```\n'
        values = [text[a:b] for a,b in sentences(text)]
        self.assertEqual(values, ['Use `x.y` in version 0.95.0.', 'Next step.'])

    def test_registry_and_invalid_settings(self):
        self.assertEqual(get_compressor('llmlingua2_repair_v1_r30').name, 'llmlingua2_repair_v1_r30')
        with self.assertRaises(ValueError): SentenceRepairCompressor(threshold=2)

    def test_unaligned_text_is_not_modified(self):
        c = self.make('Entirely different output', embed=lambda t: self.fail('unexpected embedding'))
        out = c.compress(PromptParts('', 'Tasks run first.', 'Tasks?'))
        self.assertEqual(out.info['status'], 'skipped_uncertain_alignment')

if __name__ == '__main__': unittest.main()
