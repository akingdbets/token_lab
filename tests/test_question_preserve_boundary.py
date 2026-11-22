import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from compressors.question_preserve import QuestionPreserveCompressor
from compressors.base import CompressResult

class PoisonedParts:
    system='Answer from context.'
    context='The APIClient requires release 2.9.0. If use_cache is False, recompute the value.'
    question='Which release does APIClient require?'
    @property
    def evidence(self):raise AssertionError('Evidence label accessed')
    @property
    def answer_core(self):raise AssertionError('Answer label accessed')

class Engine:
    def compress_prompt(self,**kw):return {'compressed_prompt':kw['context'][0]}

class BoundaryTests(unittest.TestCase):
    def test_public_compress_discards_gold_fields(self):
        def baseline(_,parts):
            self.assertEqual(parts.evidence,())
            self.assertEqual(parts.answer_core,())
            return CompressResult(system=parts.system,context=parts.context,question=parts.question)
        with patch('compressors.llmlingua2.LLMLingua2Compressor.compress',baseline), \
             patch('llm.count_tokens',lambda text:len(text.split())), \
             patch('llm.count_message_tokens',lambda messages:sum(len(m['content'].split()) for m in messages)+8):
            c=QuestionPreserveCompressor(engine_factory=Engine)
            r=c.compress(PoisonedParts())
        self.assertEqual(r.question,PoisonedParts.question)
        self.assertEqual(r.llm_prompt_tokens,0)

if __name__=='__main__':unittest.main()
