"""Local BM25 relevance over the given context; no answers or model calls."""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

STOPWORDS = frozenset('a an the is are was were be been being do does did to of in on at for from with and or as by it its this that these those what which who how when where why please give explain tell'.split())
WORD = re.compile(r'\w+', re.UNICODE)
CAMEL = re.compile(r'[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+')
SCORER_VERSION = 'bm25-identifiers-v1'


def terms(text: str) -> list[str]:
    result = []
    for match in WORD.finditer(text):
        word = match.group()
        low = word.lower()
        if low not in STOPWORDS:
            result.append(low)
        components = []
        for part in word.split('_'):
            if part.isascii():
                components.extend(CAMEL.findall(part))
            else:
                components.append(part)
        for part in components:
            part = part.lower()
            if part != low and part not in STOPWORDS:
                result.append(part)
    return result


def identifiers(text: str) -> set[str]:
    """Explicit inline names, snake_case and CamelCase names for link rules."""
    names = set(re.findall(r'\b(?:[A-Za-z]\w*_\w+|[A-Z][a-z]+[A-Z]\w*)\b', text))
    for inline in re.findall(r'`([^`\n]+)`', text):
        names.update(WORD.findall(inline))
    return {x.lower() for x in names if x.lower() not in STOPWORDS and len(x) > 1}


def bm25_scores(question: str, texts: Sequence[str], *, k1: float = 1.5, b: float = 0.75) -> list[float]:
    if k1 <= 0 or not 0 <= b <= 1 or not math.isfinite(k1) or not math.isfinite(b):
        raise ValueError('Invalid BM25 parameters')
    counts = [Counter(terms(text)) for text in texts]
    lengths = [sum(c.values()) for c in counts]
    average = sum(lengths) / len(lengths) if lengths else 0
    if not average:
        return [0.0] * len(texts)
    df = Counter(term for count in counts for term in count)
    query = set(terms(question))
    scores = []
    for count, length in zip(counts, lengths):
        score = 0.0
        for term in sorted(query):
            frequency = count[term]
            if frequency:
                idf = math.log(1 + (len(texts) - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * frequency * (k1 + 1) / (frequency + k1 * (1 - b + b * length / average))
        scores.append(score)
    return scores
