"""Question-based whole-section compression, with a stable ranked prefix.

Ratios refer to the complete messages entering this stage, including in a Chain.
Keep the best section intact even if it exceeds the target; report the overrun.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import math
from typing import Callable

from compressors.base import Chain, CompressResult, Compressor, PromptParts
from compressors.block_scoring import SCORER_VERSION, bm25_scores
from compressors.block_units import render_units, split_units

DEFAULT_SECTION_RETAIN_RATIO = 0.5
SECTION_VERSION = 'section-bm25-prefix-v1'


class SectionSelectCompressor(Compressor):
    name = 'section_bm25'
    targets = ('context',)

    def __init__(self, *, retain_ratio: float = DEFAULT_SECTION_RETAIN_RATIO,
                 input_budget: int | None = None, message_builder: Callable | None = None,
                 message_counter: Callable | None = None):
        self._messages = message_builder
        self._counter = message_counter
        self.set_budget(retain_ratio, input_budget)

    def set_budget(self, retain_ratio: float, input_budget: int | None = None):
        if isinstance(retain_ratio, bool) or not math.isfinite(retain_ratio) or not 0 < retain_ratio <= 1:
            raise ValueError('section retain ratio must be finite and in (0, 1]')
        if input_budget is not None and (type(input_budget) is not int or input_budget <= 0):
            raise ValueError('section input budget must be a positive integer')
        self.retain_ratio = retain_ratio
        self.input_budget = input_budget

    def config(self) -> dict:
        return {'method': self.name, 'implementation_version': SECTION_VERSION,
                'scorer_version': SCORER_VERSION, 'retain_ratio': self.retain_ratio,
                'input_budget': self.input_budget, 'budget_scope': 'stage_input_answer_messages',
                'selection': 'fixed_bm25_ranking_prefix', 'keep_best_section': True,
                'ancestor_headings': True, 'code_policy': 'whole_section_or_excluded',
                'frontmatter': 'excluded_from_candidates', 'zero_overlap_policy': 'source_order_ties'}

    def compress(self, parts: PromptParts) -> CompressResult:
        from llm import count_message_tokens
        from answer_prompts import load_answer_prompt

        messages = self._messages or load_answer_prompt('v1').messages
        counter = self._counter or count_message_tokens

        def size(context):
            return counter(messages(replace(parts, context=context)))

        raw_tokens = size(parts.context)
        fixed_tokens = size('')
        budget = self.input_budget if self.input_budget is not None else math.floor(raw_tokens * self.retain_ratio)
        info = {'method': self.name, 'implementation_version': SECTION_VERSION,
                'input_tokens_raw': raw_tokens, 'fixed_input_tokens': fixed_tokens,
                'target_input_tokens': budget, 'budget_scope': 'stage_input_answer_messages',
                'sections': [], 'ranking': [], 'selected_sections': [], 'selected_ids': [],
                'deletions': []}

        def result(context, status, fallback=False):
            tokens = size(context)
            info.update(status=status, input_tokens=tokens, budget_exceeded=tokens > budget,
                        fixed_input_exceeds_budget=fixed_tokens > budget,
                        input_reduction_pct=100*(1-tokens/raw_tokens) if raw_tokens else 0,
                        trace={'used_original': fallback})
            return CompressResult(parts.system, context, parts.question, info=info)

        if not parts.context.strip():
            return result(parts.context, 'unchanged_empty_input')
        if raw_tokens <= budget:
            return result(parts.context, 'unchanged_within_budget')
        try:
            units = split_units(parts.context)
            groups = defaultdict(set)
            for unit in units:
                if unit.kind in {'prose', 'code', 'list', 'table'}:
                    groups[(unit.document, unit.headings)].add(unit.id)
            blocks = list(groups.values())
            if not blocks:
                return result('', 'no_content_sections')
            scores = bm25_scores(parts.question, [
                '\n'.join(units[i].text for i in sorted(block)) for block in blocks])
            ranking = sorted(range(len(blocks)), key=lambda i: (-scores[i], min(blocks[i])))
            info['ranking'] = ranking
            info['query_overlap'] = any(score > 0 for score in scores)

            def assemble(kept):
                ids = set().union(*(blocks[i] for i in kept))
                for index in list(ids):
                    ids.update(units[index].headings)
                return render_units(parts.context, units, ids), sorted(ids)

            active = list(ranking)
            context, ids = assemble(active)
            tokens = size(context)
            while len(active) > 1 and tokens > budget:
                removed = active.pop()
                before = tokens
                context, ids = assemble(active)
                tokens = size(context)
                info['deletions'].append({'section_id': removed,
                                          'tokens_before': before, 'tokens_after': tokens})
            info['selected_sections'], info['selected_ids'] = active, ids
            info['sections'] = [
                {'id': i, 'score': scores[i], 'unit_ids': sorted(block),
                 'document_ref': units[min(block)].document_ref,
                 'heading_ids': list(units[min(block)].headings),
                 'heading': ' / '.join(units[h].text.strip() for h in units[min(block)].headings),
                 'start': min(units[j].start for j in block),
                 'end': max(units[j].end for j in block), 'selected': i in active}
                for i, block in enumerate(blocks)]
            return result(context, 'best_section_exceeds_budget' if tokens > budget else 'compressed')
        except Exception as error:
            info['error_type'] = type(error).__name__
            return result(parts.context, 'fallback_error', fallback=True)


def configure_section_compressor(comp: Compressor, message_builder: Callable,
                                 retain_ratio: float = DEFAULT_SECTION_RETAIN_RATIO,
                                 input_budget: int | None = None):
    """Apply the answer prompt and budget to standalone and nested chain stages."""
    if isinstance(comp, Chain):
        for stage in comp.stages:
            configure_section_compressor(stage, message_builder, retain_ratio, input_budget)
    elif isinstance(comp, SectionSelectCompressor):
        comp._messages = message_builder
        comp.set_budget(retain_ratio, input_budget)
