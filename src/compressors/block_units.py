"""Conservative Markdown units. Every unit is an unchanged source slice."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

DOCUMENT = re.compile(r'^## Document:\s*(.*?)\s*$')
HEADING = re.compile(r'^ {0,3}(#{1,6})\s+\S')
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
LIST = re.compile(r'^\s*(?:[-+*]\s+|\d+[.)]\s+|>\s*|!!!\s+)')
TABLE_RULE = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$')


@dataclass(frozen=True)
class BlockUnit:
    id: int
    kind: str
    start: int
    end: int
    document: int
    document_ref: str
    headings: tuple[int, ...]
    paragraph: int
    text: str


def _sentences(text: str, start: int, end: int):
    """Only split at clear sentence boundaries outside inline backticks."""
    begin = pos = start
    tick = 0
    while pos < end:
        if text[pos] == '`':
            count = 1
            while pos + count < end and text[pos + count] == '`':
                count += 1
            if tick == 0:
                tick = count
            elif tick == count:
                tick = 0
            pos += count
            continue
        if not tick and text[pos] in '.!?' and pos + 1 < end and text[pos + 1].isspace():
            nxt = pos + 1
            while nxt < end and text[nxt].isspace():
                nxt += 1
            word = text[begin:pos + 1].split()[-1].lower()
            abbreviation = word in {'e.g.', 'i.e.', 'etc.', 'dr.', 'mr.', 'mrs.', 'vs.'}
            if nxt < end and (text[nxt].isupper() or '\uac00' <= text[nxt] <= '\ud7a3') and not abbreviation:
                yield begin, nxt
                begin = nxt
        pos += 1
    if begin < end:
        yield begin, end


@lru_cache(maxsize=64)
def split_units(text: str) -> tuple[BlockUnit, ...]:
    lines = text.splitlines(keepends=True)
    starts, offset = [], 0
    for line in lines:
        starts.append(offset)
        offset += len(line)
    starts.append(offset)
    units: list[BlockUnit] = []
    document, ref, doc_header = 0, '', None
    headings: list[tuple[int, int]] = []
    first_content = True
    paragraph = 0

    def add(kind, first, last, sentence=False):
        nonlocal paragraph
        paragraph += 1
        ancestors = tuple(([doc_header] if doc_header is not None else []) + [u for _, u in headings])
        spans = _sentences(text, starts[first], starts[last]) if sentence else [(starts[first], starts[last])]
        for a, b in spans:
            units.append(BlockUnit(len(units), kind, a, b, document, ref, ancestors, paragraph, text[a:b]))

    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\r\n')
        if not line.strip():
            i += 1
            continue
        match = DOCUMENT.match(line)
        if match:
            document += 1
            ref, doc_header, headings = match.group(1), None, []
            add('document', i, i + 1)
            doc_header = units[-1].id
            first_content = True
            i += 1
            continue
        if first_content and line.strip() == '---':
            j = i + 1
            while j < len(lines) and lines[j].strip() not in {'---', '...'}:
                j += 1
            if j == len(lines):
                raise ValueError('Unclosed frontmatter')
            add('frontmatter', i, j + 1)
            first_content = False
            i = j + 1
            continue
        first_content = False
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            j = i + 1
            while j < len(lines):
                closing = FENCE.match(lines[j])
                if closing and closing.group(1)[0] == marker[0] and len(closing.group(1)) >= len(marker) and not lines[j][closing.end():].strip():
                    break
                j += 1
            if j == len(lines):
                raise ValueError('Unclosed fenced code block')
            add('code', i, j + 1)
            i = j + 1
            continue
        match = HEADING.match(line)
        if match:
            level = len(match.group(1))
            while headings and headings[-1][0] >= level:
                headings.pop()
            add('heading', i, i + 1)
            headings.append((level, units[-1].id))
            i += 1
            continue
        if i + 1 < len(lines) and '|' in line and TABLE_RULE.match(lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].strip() and '|' in lines[j]:
                j += 1
            add('table', i, j)
            i = j
            continue
        if LIST.match(line):
            j = i + 1
            while j < len(lines):
                if DOCUMENT.match(lines[j].strip()) or HEADING.match(lines[j]) or FENCE.match(lines[j]):
                    break
                if not lines[j].strip():
                    nxt = j + 1
                    while nxt < len(lines) and not lines[nxt].strip():
                        nxt += 1
                    if nxt < len(lines) and (LIST.match(lines[nxt]) or lines[nxt].startswith(('  ', '\t'))):
                        j = nxt
                        continue
                    break
                # Unindented prose after a list starts a new unit.
                if not LIST.match(lines[j]) and not lines[j].startswith(('  ', '\t')):
                    break
                j += 1
            add('list', i, j)
            i = j
            continue
        j = i + 1
        while j < len(lines) and lines[j].strip():
            if DOCUMENT.match(lines[j].strip()) or HEADING.match(lines[j]) or FENCE.match(lines[j]) or LIST.match(lines[j]):
                break
            if j + 1 < len(lines) and '|' in lines[j] and TABLE_RULE.match(lines[j + 1]):
                break
            j += 1
        add('prose', i, j, sentence=True)
        i = j
    return tuple(units)


def render_units(source: str, units: tuple[BlockUnit, ...], selected: set[int]) -> str:
    """Keep source order and exact unit text; separate non-adjacent units."""
    pieces = []
    previous = None
    for unit in units:
        if unit.id not in selected:
            continue
        if previous is not None:
            gap = source[previous.end:unit.start]
            pieces.append(gap if not gap.strip() else '\n\n')
        pieces.append(unit.text)
        previous = unit
    return ''.join(pieces)
