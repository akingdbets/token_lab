"""Question-only BM25 preservation under a measured whole-message budget.

No answers, gold facts, evidence labels, historical responses or qids are accepted
by compress_budget. Selected source spans are copied verbatim. LLMLingua-2 handles
only the residual text. Budget repair never removes protected source spans.
"""
from __future__ import annotations
import math
import re
import time
from collections import Counter
from .base import Compressor, PromptParts, CompressResult
from .llmlingua2 import _load_engine, DEFAULT_FORCE_TOKENS

VERSION='question-preserve-v1'
STOP=set('a an the of to in on for from is are was be with and or how what which when why does do can should it its this that as by fastapi according documentation docs python'.split())
TECH=re.compile(r'`[^`\n]{1,100}`|(?<![\w.])\d+(?:\.\d+)*(?![\w.])|\b[A-Za-z][\w]*(?:[._-][\w]+)+\b|\b[A-Z][a-z]+[A-Z]\w*\b')
REL=re.compile(r'\b(if|unless|when|before|after|not|no|never|without|only|except|than|between|until|requires?|defaults?|precedence|first|last|order|less|greater|range)\b',re.I)


def terms(text):
    text=re.sub(r'([a-z])([A-Z])',r'\1 \2',text)
    return [w for w in re.findall(r'[a-z]+|\d+(?:\.\d+)*',text.lower()) if w not in STOP]


def units(text):
    """Exact source offsets: fences atomic; prose split at lines/sentence boundaries."""
    out=[];pos=0;buffer='';start=0;fence=None
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(('```','~~~')):
            if fence is None:
                fence=line.lstrip()[:3];start=pos;buffer=line
            else:
                buffer+=line
                if line.lstrip().startswith(fence):
                    out.append((start,pos+len(line),'code'));buffer='';fence=None
        elif fence is not None:buffer+=line
        else:
            cursor=0
            for part in re.split(r'(?<=[.!?])\s+(?=[A-Z`])',line):
                offset=line.find(part,cursor);cursor=offset+len(part)
                if part.strip():out.append((pos+offset,pos+cursor,'header' if part.startswith('## Document:') else 'prose'))
        pos+=len(line)
    if fence is not None:out.append((start,len(text),'code'))
    return out


def bm25(question,text,spans,k1=1.2,b=.75):
    docs=[terms(text[a:z]) for a,z,_ in spans];q=set(terms(question));n=len(docs)
    df=Counter(t for d in docs for t in set(d));avg=sum(map(len,docs))/max(1,n)
    scores=[]
    for d in docs:
        tf=Counter(d);score=0.
        for t in q:
            if tf[t]:score+=math.log(1+(n-df[t]+.5)/(df[t]+.5))*tf[t]*(k1+1)/(tf[t]+k1*(1-b+b*len(d)/max(1,avg)))
        scores.append(score)
    return scores


class QuestionPreserveCompressor(Compressor):
    targets=('context',)
    def __init__(self,mode='combined',protected_fraction=.35,max_spans=18,engine_factory=None):
        if mode not in ('identifiers','sentences','combined'):raise ValueError(mode)
        self.mode=mode;self.protected_fraction=protected_fraction;self.max_spans=max_spans
        self.name={'identifiers':'qp_identifiers_r30','sentences':'qp_sentences_r30','combined':'qp_combined_r30'}[mode]
        self.engine_factory=engine_factory

    def config(self):
        return {'method':VERSION,'mode':self.mode,'protected_fraction':self.protected_fraction,
                'max_spans':self.max_spans,'bm25_k1':1.2,'bm25_b':.75,'relation_boost':.25,
                'target':'fresh LLMLingua-2 r30 whole-message input tokens',
                'model_name':'microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank',
                'model_revision':'5f0c827','decision_inputs':['question','source_context','system','numeric_budget'],
                'budget_repair':'drop residual words then greedily add original units/prefixes; protected spans never cut'}

    def compress(self,parts):
        # Discard diagnostic labels at the interface boundary before any compressor call.
        from experiment import load_answer_prompt
        from llm import count_message_tokens,count_tokens
        from .llmlingua2 import LLMLingua2Compressor
        prompt=load_answer_prompt('v1')
        clean=PromptParts(system=parts.system,context=parts.context,question=parts.question)
        anchor=LLMLingua2Compressor(retain_ratio=.3).compress(clean)
        def total(context):
            return count_message_tokens(prompt.messages(PromptParts(system=clean.system,context=context,question=clean.question)))
        return self.compress_budget(clean.question,clean.context,clean.system,total(anchor.context),total,count_tokens)

    def compress_budget(self,question,context,system,budget,total_tokens,text_tokens):
        started=time.perf_counter();spans=units(context);scores=bm25(question,context,spans)
        cap=max(0,int((budget-total_tokens(''))*self.protected_fraction));selected=[];used=0
        def add(a,z):
            nonlocal used
            if len(selected)>=self.max_spans or any(a<y and z>x for x,y in selected):return False
            cost=text_tokens(context[a:z])
            if used+cost>cap:return False
            selected.append((a,z));used+=cost;return True
        # All document headers are mandatory when feasible; otherwise explicitly logged.
        for a,z,kind in spans:
            if kind=='header':add(a,z)
        rank=sorted(range(len(spans)),key=lambda i:(-(scores[i]*(1+.25*bool(REL.search(context[spans[i][0]:spans[i][1]]))) if self.mode=='combined' else -scores[i]),spans[i][0]))
        if self.mode in ('sentences','combined'):
            sentence_cap=cap if self.mode=='sentences' else int(cap*.85)
            for i in rank:
                a,z,kind=spans[i]
                if scores[i]<=0 or kind=='header':continue
                cost=text_tokens(context[a:z])
                if used+cost<=sentence_cap:add(a,z)
        if self.mode in ('identifiers','combined'):
            candidates=[]
            for i in rank:
                a,z,kind=spans[i]
                if kind=='header':continue
                for m in TECH.finditer(context[a:z]):
                    candidates.append((-(scores[i]+len(set(terms(m.group()))&set(terms(question)))),a+m.start(),a+m.end()))
            for _,a,z in sorted(candidates):add(a,z)
        selected.sort();masked=[];markers=[];cursor=0
        for i,(a,z) in enumerate(selected):
            marker=f'QPPROTECT{i:03d}UNIT'
            while marker in context:marker='Q'+marker
            masked.extend([context[cursor:a],marker]);markers.append((marker,context[a:z]));cursor=z
        masked.append(context[cursor:]);masked=''.join(masked)
        def restore(text):
            for marker,value in markers:text=text.replace(marker,value)
            return text
        overhead=total_tokens('');available=max(0,budget-overhead-used)
        residual=max(1,text_tokens(context)-used)
        rate=max(.02,min(.95,available/residual))
        engine=self.engine_factory() if self.engine_factory else _load_engine(self.config()['model_name'],'5f0c827','cpu')
        engine_started=time.perf_counter();failure=None
        try:
            result=engine.compress_prompt(context=[masked],rate=rate,use_context_level_filter=False,
                use_token_level_filter=True,force_tokens=list(DEFAULT_FORCE_TOKENS)+[m for m,_ in markers],force_reserve_digit=True)
            output=result['compressed_prompt']
            if any(output.count(m)!=1 for m,_ in markers):raise ValueError('protected_marker_missing_or_duplicate')
            if [output.index(m) for m,_ in markers]!=sorted(output.index(m) for m,_ in markers):raise ValueError('protected_marker_reordered')
        except Exception as exc:
            # Failed model inference is NOT silently reported as successful compression.
            failure=type(exc).__name__+':'+str(exc)[:100]
            output='\n'.join(m for m,_ in markers)
        engine_sec=time.perf_counter()-engine_started
        before=total_tokens(restore(output));removed=0
        # Split around protected markers; remove only residual whitespace-delimited words.
        pattern='('+'|'.join(re.escape(m) for m,_ in markers)+')' if markers else None
        chunks=re.split(pattern,output) if pattern else [output]
        nodes=[]
        marker_set={m for m,_ in markers}
        for chunk in chunks:
            if chunk in marker_set:nodes.append([chunk,True])
            else:nodes.extend([[m.group(),False] for m in re.finditer(r'\S+\s*|\s+',chunk)])
        def rendered():return restore(''.join(x[0] for x in nodes))
        while total_tokens(rendered())>budget:
            candidates=[i for i,x in enumerate(nodes) if x[0] and not x[1]]
            if not candidates:break
            # Lowest query overlap first, deterministic tail tie-break.
            i=min(candidates,key=lambda i:(len(set(terms(nodes[i][0]))&set(terms(question))),-i))
            nodes[i][0]='';removed+=1
        final=rendered();added=[]
        # Spend unused budget on source text. This is also question-only and label-free.
        for i in rank:
            a,z,kind=spans[i];unit=context[a:z].strip()
            if not unit or unit in final or kind=='header' or any(a<y and z>x for x,y in selected):continue
            candidate=final+'\n'+unit
            if total_tokens(candidate)<=budget:final=candidate;added.append([a,z])
        # Last small remainder: exact source word-boundary prefixes (no synthetic padding).
        for i in rank:
            if budget-total_tokens(final)<=1:break
            a,z,kind=spans[i];unit=context[a:z].strip()
            if not unit or unit in final or kind=='header' or any(a<y and z>x for x,y in selected):continue
            best=''
            for m in re.finditer(r'\s+|$',unit):
                prefix=unit[:m.start()]
                if prefix and prefix not in final and total_tokens(final+'\n'+prefix)<=budget:best=prefix
            if best:final+='\n'+best;added.append([a,a+len(best)])
        actual=total_tokens(final)
        assert all(value in final for _,value in markers)
        info={**self.config(),'status':'inference_failure_extractive_fallback' if failure else 'compressed',
            'inference_error':failure,'target_input_tokens':budget,'actual_input_tokens':actual,
            'budget_difference':actual-budget,'overflow_tokens':max(0,actual-budget),
            'overflow_reason':'protected_spans_or_prompt_overhead_exceed_budget' if actual>budget else None,
            'protected_token_cap':cap,'protected_tokens_sum':used,
            'protected_spans':[{'start':a,'end':z,'text':context[a:z]} for a,z in selected],
            'unit_scores':[{'start':a,'end':z,'kind':k,'bm25':s} for (a,z,k),s in zip(spans,scores)],
            'residual_rate_requested':rate,'input_before_budget_repair':before,'residual_words_removed':removed,
            'source_spans_added_for_budget':added,'engine_seconds':engine_sec,'duration_sec':time.perf_counter()-started,
            'compression_api_calls':0,'compression_api_tokens':0}
        return CompressResult(system=system,context=final,question=question,info=info)
