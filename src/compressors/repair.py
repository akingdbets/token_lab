"""Question-guided post-compression sentence repair, experimental v1.

Uses no answers, facts or annotated evidence. Alignment is heuristic and logged.
"""
import math
import re
from collections import Counter
from difflib import SequenceMatcher

from compressors.base import Compressor, PromptParts
from compressors.llmlingua2 import LLMLingua2Compressor, _split_fenced_blocks

_WORD = re.compile(r'\w+|[^\w\s]', re.UNICODE)
_STOP = set('a an the is are was were do does how what which when where with in on of to and for'.split())


def sentences(text):
    """Line-bounded sentences; skip fences/headers/frontmatter; protect inline dots."""
    offset = 0
    frontmatter = False
    for code, chunk in _split_fenced_blocks(text):
        if code:
            offset += len(chunk)
            continue
        for line in chunk.splitlines(keepends=True):
            if line.strip() == '---':
                frontmatter = not frontmatter
            elif not frontmatter and line.strip() and not line.lstrip().startswith('#'):
                # Inline code is kept intact during boundary detection.
                masked = re.sub(r'(`+).*?\1', lambda m: 'x' * len(m[0]), line)
                start = 0
                for end in [m.end() for m in re.finditer(r'[.!?](?=\s+[A-Z]|\s*$)', masked)] + [len(line)]:
                    if end <= start:
                        continue
                    a = start + len(line[start:end]) - len(line[start:end].lstrip())
                    b = end - (len(line[start:end]) - len(line[start:end].rstrip()))
                    if a < b:
                        yield offset + a, offset + b
                    start = end
            offset += len(line)


def relevance(question, sentence):
    q = Counter(w.lower() for w in re.findall(r'\w+', question) if w.lower() not in _STOP)
    s = Counter(w.lower() for w in re.findall(r'\w+', sentence) if w.lower() not in _STOP)
    denom = math.sqrt(sum(v*v for v in q.values()) * sum(v*v for v in s.values()))
    return sum(v*s[k] for k, v in q.items()) / denom if denom else 0.0


def cosine(a, b):
    if len(a) != len(b) or not a:
        raise ValueError('Invalid embedding dimensions')
    denom = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    if not denom:
        raise ValueError('Zero embedding')
    score = sum(x*y for x, y in zip(a, b)) / denom
    if not math.isfinite(score):
        raise ValueError('Non-finite similarity')
    return max(-1.0, min(1.0, score))


class SentenceRepairCompressor(Compressor):
    targets = ('context',)

    def __init__(self, retain_ratio=0.3, *, top_k=3, threshold=0.85,
                 max_added_tokens=256, base=None, embed=None, token_counter=None):
        if top_k < 1 or not -1 <= threshold <= 1 or max_added_tokens < 0:
            raise ValueError('Invalid repair configuration')
        self.base = base or LLMLingua2Compressor(retain_ratio=retain_ratio)
        self.top_k, self.threshold = top_k, threshold
        self.max_added_tokens = max_added_tokens
        self._embed, self._count = embed, token_counter
        self._custom_embed = embed is not None
        self.name = f'llmlingua2_repair_v1_r{round(retain_ratio*100):02d}'

    def config(self):
        from config import CFG
        return dict(method='sentence-repair-v1', base=self.base.config(), top_k=self.top_k,
                    threshold=self.threshold, max_added_tokens=self.max_added_tokens,
                    relevance='word-cosine-v1', preservation='embedding-cosine',
                    embed_model=getattr(CFG, 'embed_model', None),
                    embedding_source='injected' if self._custom_embed else 'configured-embed-role',
                    alignment='sequence-matcher-v1', max_passes=1)

    def compress_context(self, question, context):
        selected = sorted(((relevance(question, context[a:b]), a, b)
                           for a, b in sentences(context)), key=lambda x: (-x[0], x[1]))
        selected = [s for s in selected if s[0] > 0][:self.top_k]
        base = self.base.compress(PromptParts('', context, question))
        compressed = base.context
        self.add_info(method='sentence-repair-v1', base=base.info, config=self.config(),
                      selected_sentences=[], restored_sentences=0)
        if not selected or compressed == context:
            self.add_info(status='unchanged_base', added_tokens=0)
            return compressed
        if self._count is None:
            from llm import count_tokens
            self._count = count_tokens
        if self._embed is None:
            from llm import LLM
            self._embed = LLM(role='embed').embed
        original = list(_WORD.finditer(context))
        shortened = list(_WORD.finditer(compressed))
        matches = SequenceMatcher(None, [m[0] for m in original],
                                  [m[0] for m in shortened], autojunk=False).get_matching_blocks()
        mapping = {i+k: j+k for i, j, n in matches for k in range(n)}
        coverage = len(mapping) / max(1, len(shortened))
        self.add_info(alignment_coverage=coverage)
        if shortened and coverage < 0.9:
            self.add_info(status='skipped_uncertain_alignment', added_tokens=0)
            return compressed
        changes, audit = [], []
        initial_tokens = self._count(compressed)
        def assemble(edits):
            result = compressed
            for lo, hi, value in sorted(edits, reverse=True):
                result = result[:lo] + value + result[hi:]
            return result
        for rel, a, b in selected:
            indices = [i for i, m in enumerate(original) if a <= m.start() and m.end() <= b]
            kept = [mapping[i] for i in indices if i in mapping]
            if kept:
                lo, hi = shortened[min(kept)].start(), shortened[max(kept)].end()
                excerpt = compressed[lo:hi]
            else:
                following = [j for i, j in mapping.items() if original[i].start() >= b]
                lo = hi = shortened[min(following)].start() if following else len(compressed)
                excerpt = ''
            row = dict(start=a, end=b, relevance=rel, original=context[a:b],
                       compressed=excerpt, action='keep')
            try:
                score = cosine(self._embed(context[a:b]), self._embed(excerpt)) if excerpt else 0.0
            except Exception as exc:
                row.update(action='skip_embedding_error', error_type=type(exc).__name__)
                audit.append(row)
                continue
            row['similarity'] = score
            if not excerpt or score < self.threshold:
                # Avoid assigning an unmatched fragment from another sentence to this one.
                if any((lo < y and hi > x) or (lo == hi == x == y) for x, y, _ in changes):
                    row['action'] = 'skip_overlap'
                else:
                    edit = (lo, hi, ' ' + context[a:b] + ' ')
                    candidate = assemble(changes + [edit])
                    if self._count(candidate) - initial_tokens <= self.max_added_tokens:
                        changes.append(edit)
                        row['action'] = 'restore'
                    else:
                        row['action'] = 'skip_budget'
            audit.append(row)
        result = assemble(changes)
        self.add_info(status='repaired' if changes else 'compressed', selected_sentences=audit,
                      restored_sentences=len(changes), added_tokens=self._count(result)-initial_tokens,
                      base_context_tokens=initial_tokens, final_context_tokens=self._count(result))
        return result
