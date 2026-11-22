"""UCWIT staged study: dev -> freeze -> independent dataset -> independent eval.
No historical answers/gold labels are passed to the compression decision function.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import asdict
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/analysis/final-experiment'
sys.path.insert(0,str(ROOT/'src'))
os.environ.update({'ANSWER_BACKEND':'openai','ANSWER_MODEL':'gpt-6.1-terra',
'ANSWER_BASE_URL':'https://api.openai.com','JUDGE_BACKEND':'openai','JUDGE_MODEL':'deepseek-flash',
'JUDGE_BASE_URL':'https://api.deepseek.com','TOKENIZER':'tiktoken:o200k_base',
'ANSWER_REASONING_EFFORT':'none','JUDGE_REASONING_EFFORT':'','LLM_TEMPERATURE':'0',
'LLM_SEED':'42','LLM_NUM_CTX':'16384','EVAL_DIR':'data/evalsets/claude-v1',
'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
from config import CFG
from compressors import PromptParts,get_compressor
from compressors.question_preserve import QuestionPreserveCompressor
from experiment import load_answer_prompt,build_context
from corpus import load_corpus
from grader import grade_answer_accuracy,is_not_found_answer,FACT_JUDGE_PROMPT_HASH,parse_yes_no
from llm import LLM,count_tokens,count_message_tokens


def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def cfg():return load(OUT/'config.json')
def append(p,x):
    with p.open('a') as f:f.write(json.dumps(x,ensure_ascii=False)+'\n');f.flush()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def code_files():
    return sorted([ROOT/'scripts/final_experiment.py',OUT/'config.json',ROOT/'tests/test_question_preserve.py',
                   *list((ROOT/'src').glob('*.py')),*list((ROOT/'src/compressors').glob('*.py')),
                   ROOT/'src/prompts/answer_v1.md'])


def fingerprint(paths):return {str(p.relative_to(ROOT)):sha(p) for p in paths}
def check_hashes(hashes):
    bad=[n for n,h in hashes.items() if not (ROOT/n).exists() or sha(ROOT/n)!=h]
    if bad:raise ValueError('Hash mismatch: '+str(bad))


def public_runtime():
    prompt=load_answer_prompt('v1')
    return {'models':CFG.models_info(),'seed':CFG.seed,'temperature':CFG.temperature,
      'answer_reasoning_effort':CFG.answer_reasoning_effort,'judge_reasoning_effort':CFG.judge_reasoning_effort,
      'answer_max_tokens':512,'fact_judge_max_tokens':4096,'judge_mode':'per_fact',
      'answer_prompt_hash':prompt.sha256,'fact_judge_hash':FACT_JUDGE_PROMPT_HASH,
      'packages':{p:importlib.metadata.version(p) for p in ['requests','tiktoken','torch','transformers','llmlingua','numpy']}}


def client(role,max_tokens=512):
    c=LLM(role=role,max_tokens=max_tokens,max_retries=1,timeout=90)
    if role=='answer':c.unsupported.add('max_tokens')
    CFG.network_retry_waits=()
    if not c.api_key:raise ValueError('Missing credentials: '+role)
    return c


def result_dict(r):return {k:v for k,v in asdict(r).items() if k!='raw'}
def answer_messages(q,context):
    p=load_answer_prompt('v1');return p.messages(p.parts(context,q['question'],q['type']))


def clusters(items):
    parent={q['id']:q['id'] for q in items}
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    docs={}
    for q in items:
        for doc in q.get('source_files',q.get('evidence_pages',[])):
            if doc in docs:parent[find(q['id'])]=find(docs[doc])
            else:docs[doc]=q['id']
    return {q['id']:find(q['id']) for q in items}


def prepare(split):
    if split=='independent':verify_freeze()
    path=OUT/split
    if (path/'plan.json').exists():raise ValueError('Plan already exists; resume run, do not overwrite')
    path.mkdir(exist_ok=True)
    if split=='dev':
        dataset=ROOT/'data/evalsets/claude-v1/qa_dev.json';items=load(dataset)
        corpus=load_corpus();raw={q['id']:build_context(corpus,q) for q in items}
    else:
        dataset=OUT/'independent_dataset.json';items=load(dataset)
        raw={q['id']:(ROOT/q['context_path']).read_text() for q in items}
    group=clusters(items);manifest=[];compression_records=[]
    (path/'contexts').mkdir(exist_ok=True)
    for q in items:
        qid=q['id'];context=raw[qid];parts=load_answer_prompt('v1').parts(context,q['question'],q['type'])
        # This is the only PromptParts passed downstream; both diagnostic fields are empty.
        assert not parts.evidence and not parts.answer_core
        def total(text):return count_message_tokens(answer_messages(q,text))
        outputs={};infos={};durations={}
        for condition in ['none','llmlingua2_r50','llmlingua2_r30']:
            cache=path/'contexts'/f'{qid}.{condition}.json'
            if cache.exists():c=load(cache);assert c['source_sha256']==hashlib.sha256(context.encode()).hexdigest()
            else:
                t=time.perf_counter();res=get_compressor(condition).compress(parts)
                c={'context':res.context,'info':res.info,'duration_sec':time.perf_counter()-t,
                   'source_sha256':hashlib.sha256(context.encode()).hexdigest()};dump(cache,c)
            outputs[condition]=c['context'];infos[condition]=c['info'];durations[condition]=c['duration_sec']
        budget=total(outputs['llmlingua2_r30'])
        for mode in ['identifiers','sentences','combined']:
            compressor=QuestionPreserveCompressor(mode=mode,protected_fraction=cfg()['protected_fraction'],max_spans=cfg()['max_spans'])
            condition=compressor.name;cache=path/'contexts'/f'{qid}.{condition}.json'
            if cache.exists():c=load(cache);assert c['source_sha256']==hashlib.sha256(context.encode()).hexdigest()
            else:
                res=compressor.compress_budget(q['question'],context,parts.system,budget,total,count_tokens)
                c={'context':res.context,'info':res.info,'duration_sec':res.info['duration_sec'],
                   'source_sha256':hashlib.sha256(context.encode()).hexdigest()};dump(cache,c)
            outputs[condition]=c['context'];infos[condition]=c['info'];durations[condition]=c['duration_sec']
        for condition in cfg()['conditions']:
            p=path/'contexts'/f'{qid}.{condition}.md';p.write_text(outputs[condition])
            rec={'qid':qid,'condition':condition,'context_path':str(p.relative_to(ROOT)),
                 'context_sha256':sha(p),'input_tokens_est':total(outputs[condition]),
                 'raw_input_tokens_est':total(context),'target_input_tokens':budget,
                 'budget_difference':total(outputs[condition])-budget,
                 'duration_sec':durations[condition],'info':infos[condition]}
            compression_records.append(rec)
        print('COMPRESSED',split,qid,'target',budget,'deltas',{k:total(v)-budget for k,v in outputs.items()},flush=True)
        manifest.append({'item':q,'cluster':group[qid]})
    schedule=[{'qid':q['id'],'condition':c} for q in items for c in cfg()['conditions']]
    random.Random(cfg()['schedule_seed']).shuffle(schedule)
    protected_originals=list((ROOT/'results/runs').rglob('*'))+list((ROOT/'data/evalsets/claude-v1').rglob('*'))
    protected_originals=[p for p in protected_originals if p.is_file()]
    plan={'split':split,'created_utc':now(),'items':manifest,'schedule':schedule,'compression':compression_records,
       'code_hashes':fingerprint(code_files()),'dataset':str(dataset.relative_to(ROOT)),'dataset_sha256':sha(dataset),
       'runtime':public_runtime(),'branch':git('branch','--show-current'),'git_commit':git('rev-parse','HEAD'),
       'git_diff':git('diff','--stat'),'original_input_hashes':fingerprint(protected_originals),
       'dry_run':{'answer_calls':len(schedule),'fact_judge_calls_max':sum(len(q['key_facts']) for q in items)*len(cfg()['conditions']),
         'answer_input_est':sum(r['input_tokens_est'] for r in compression_records),
         'answer_output_cap':len(schedule)*512,'compression_llm_api_calls':0,
         'note':'Compression uses local LLMLingua-2; tokenizer full chat estimates vs actual API usage both reported.'}}
    dump(path/'plan.json',plan);dump(path/'compression.json',compression_records)
    dump(path/'preflight.json',{'plan_sha256':sha(path/'plan.json'),'dataset_sha256':sha(dataset),
         'code_hashes':plan['code_hashes'],'runtime':plan['runtime'],'dry_run':plan['dry_run'],
         'tests':'5 question_preserve unit tests passed before dev preparation; see test logs'})
    print(json.dumps(plan['dry_run'],indent=2),flush=True)


def run(split):
    if split=='independent':verify_freeze()
    path=OUT/split;plan=load(path/'plan.json');check_hashes(plan['code_hashes'])
    assert sha(ROOT/plan['dataset'])==plan['dataset_sha256']
    assert public_runtime()==plan['runtime']
    old=[json.loads(s) for s in (path/'trials.jsonl').read_text().splitlines()] if (path/'trials.jsonl').exists() else []
    done={(r['qid'],r['condition']) for r in old if r['status']=='complete'}
    items={x['item']['id']:x for x in plan['items']};comp={(r['qid'],r['condition']):r for r in plan['compression']}
    cache_dir=path/'answer_cache';cache_dir.mkdir(exist_ok=True)
    import threading
    lock=threading.Lock()
    def task(t):
        q=items[t['qid']]['item'];cr=comp[(t['qid'],t['condition'])];context_path=ROOT/cr['context_path']
        assert sha(context_path)==cr['context_sha256']
        context=context_path.read_text();cache=cache_dir/f"{t['qid']}.{t['condition']}.json"
        if cache.exists():a=load(cache);assert a['context_sha256']==cr['context_sha256']
        else:
            answer=client('answer');res=answer.chat(answer_messages(q,context))
            assert res.model=='gpt-6.1-terra' or res.model.startswith('gpt-6.1-terra-')
            a={'response':res.text,'result':result_dict(res),'sampling':answer.sampling_info(),
               'request_id':res.raw.get('id'),'system_fingerprint':res.raw.get('system_fingerprint'),
               'context_sha256':cr['context_sha256']};dump(cache,a)
        fact=client('judge',4096)
        fg=grade_answer_accuracy(q['question'],q['answer'],q['key_facts'],a['response'],fact,mode='per_fact')
        row={**t,'status':'complete','time_utc':now(),'split':split,'qtype':q['type'],
          'document_cluster':items[t['qid']]['cluster'],'source_files':q.get('source_files',q.get('evidence_pages',[])),
          'question':q['question'],'reference_answer':q['answer'],'key_facts':q['key_facts'],
          'response':a['response'],'answer_model':a['result']['model'],'answer':a,
          'fact_grade':asdict(fg),'judge_sampling':fact.sampling_info(),'answer_accuracy':fg.answer_accuracy,
          'fully_correct':fg.answer_accuracy==1 if fg.answer_accuracy is not None else None,
          'not_found':is_not_found_answer(a['response']),'compression':cr,
          'compression_api_tokens':0,'compression_api_calls':0}
        with lock:append(path/'trials.jsonl',row)
        print('EVAL',split,t['qid'],t['condition'],fg.answer_accuracy,flush=True)
    tasks=[t for t in plan['schedule'] if (t['qid'],t['condition']) not in done]
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs={pool.submit(task,t):t for t in tasks}
        for f in as_completed(fs):
            try:f.result()
            except Exception as e:
                error={**fs[f],'time_utc':now(),'type':type(e).__name__,
                       'http_status':getattr(getattr(e,'response',None),'status_code',None)}
                append(path/'errors.jsonl',error);print('ERROR',error,flush=True)
    summarize(split)


def bootstrap(deltas,groupids,reps,seed,cluster=False):
    import numpy as np
    if not deltas:return None
    rng=np.random.default_rng(seed);arr=np.array(deltas,dtype=float)
    if not cluster:
        means=arr[rng.integers(0,len(arr),size=(reps,len(arr)))].mean(axis=1)
    else:
        groups=sorted(set(groupids))
        if len(groups)<2:return None
        sums=np.array([sum(d for d,g in zip(deltas,groupids) if g==key) for key in groups])
        sizes=np.array([groupids.count(key) for key in groups]);idx=rng.integers(0,len(groups),size=(reps,len(groups)))
        means=sums[idx].sum(axis=1)/sizes[idx].sum(axis=1)
    return {'low':float(np.quantile(means,.025)),'high':float(np.quantile(means,.975)),
            'replicates':reps,'seed':seed,'clusters':len(set(groupids)),'unit':'document-connected-component' if cluster else 'question'}


def summarize(split):
    path=OUT/split;plan=load(path/'plan.json')
    rows=[json.loads(s) for s in (path/'trials.jsonl').read_text().splitlines()]
    keys={(r['qid'],r['condition']) for r in rows};assert len(keys)==len(rows)
    def avg(vals):
        xs=[x for x in vals if x is not None];return sum(xs)/len(xs) if xs else None
    stats={}
    for condition in cfg()['conditions']:
        rs=[r for r in rows if r['condition']==condition];valid=[r for r in rs if r['answer_accuracy'] is not None]
        stats[condition]={'n':len(rs),'valid_n':len(valid),'answer_accuracy':avg([r['answer_accuracy'] for r in rs]),
           'fully_correct_rate':avg([r['fully_correct'] for r in valid]),'not_found_rate':avg([r['not_found'] for r in rs]),
           'input_tokens_est':avg([r['compression']['input_tokens_est'] for r in rs]),
           'api_input_tokens':avg([r['answer']['result']['prompt_tokens'] for r in rs]),
           'input_reduction_pct_est':avg([100*(1-r['compression']['input_tokens_est']/r['compression']['raw_input_tokens_est']) for r in rs]),
           'compression_seconds_mean':avg([r['compression']['duration_sec'] for r in rs]),
           'compression_failure_n':sum('fallback' in r['compression']['info'].get('status','') for r in rs),
           'compression_api_calls':0,'compression_api_tokens':0,
           'overflow_n':sum(r['compression']['budget_difference']>0 for r in rs) if condition.startswith('qp_') else None,
           'by_type':{t:{'n':sum(r['qtype']==t for r in rs),'accuracy':avg([r['answer_accuracy'] for r in rs if r['qtype']==t]),
                        'not_found_rate':avg([r['not_found'] for r in rs if r['qtype']==t])} for t in cfg()['types']}}
    index={(r['qid'],r['condition']):r for r in rows};pairs={};case_deltas=[]
    for condition in cfg()['conditions']:
        if condition in ['none','llmlingua2_r30']:continue
        matched=[]
        for q in plan['items']:
            qid=q['item']['id'];b=index.get((qid,'llmlingua2_r30'));r=index.get((qid,condition))
            if not b or not r or b['answer_accuracy'] is None or r['answer_accuracy'] is None:continue
            delta=r['answer_accuracy']-b['answer_accuracy'];matched.append((delta,q['cluster'],r,b))
            case_deltas.append({'qid':qid,'qtype':r['qtype'],'condition':condition,'delta_accuracy':delta,
              'baseline_accuracy':b['answer_accuracy'],'condition_accuracy':r['answer_accuracy'],
              'estimated_token_difference':r['compression']['input_tokens_est']-b['compression']['input_tokens_est'],
              'api_token_difference':r['answer']['result']['prompt_tokens']-b['answer']['result']['prompt_tokens'],
              'baseline_response':b['response'],'condition_response':r['response'],'question':r['question']})
        ds=[x[0] for x in matched];gs=[x[1] for x in matched]
        pairs[condition]={'paired_n':len(ds),'delta_accuracy':avg(ds),'improved':sum(x>0 for x in ds),'worsened':sum(x<0 for x in ds),'unchanged':sum(x==0 for x in ds),
          'question_bootstrap_95ci':bootstrap(ds,gs,cfg()['bootstrap_replicates'],cfg()['bootstrap_seed']),
          'document_cluster_bootstrap_95ci':bootstrap(ds,gs,cfg()['bootstrap_replicates'],cfg()['bootstrap_seed'],True),
          'mean_api_token_difference':avg([r['answer']['result']['prompt_tokens']-b['answer']['result']['prompt_tokens'] for _,_,r,b in matched]),
          'max_abs_api_token_difference':max((abs(r['answer']['result']['prompt_tokens']-b['answer']['result']['prompt_tokens']) for _,_,r,b in matched),default=None),
          'within_one_token_n':sum(abs(r['answer']['result']['prompt_tokens']-b['answer']['result']['prompt_tokens'])<=1 for _,_,r,b in matched)}
        # Strict matched-budget sensitivity, declared before outcomes, never drop from primary table.
        tight=[x for x in matched if abs(x[2]['answer']['result']['prompt_tokens']-x[3]['answer']['result']['prompt_tokens'])<=1]
        pairs[condition]['strict_budget_subset']={'n':len(tight),'mean_delta':avg([x[0] for x in tight]),'question_bootstrap_95ci':bootstrap([x[0] for x in tight],[x[1] for x in tight],cfg()['bootstrap_replicates'],cfg()['bootstrap_seed'])}
    usage={'answer_input':sum(r['answer']['result']['prompt_tokens'] for r in rows),
           'answer_output':sum(r['answer']['result']['completion_tokens'] for r in rows),
           'judge_input':sum(r['fact_grade']['judge_prompt_tokens'] for r in rows),
           'judge_output':sum(r['fact_grade']['judge_completion_tokens'] for r in rows),
           'answer_calls_completed':len(rows),'fact_judge_calls':sum(r['fact_grade']['judge_calls'] for r in rows),
           'compression_llm_api_calls':0,'compression_llm_api_tokens':0}
    summary={'split':split,'expected_trials':len(plan['schedule']),'completed_trials':len(rows),'distinct_qids':len(plan['items']),
      'document_clusters':len(set(x['cluster'] for x in plan['items'])),'conditions':stats,'paired_vs_r30':pairs,'usage':usage,
      'dataset_sha256':plan['dataset_sha256'],'plan_sha256':sha(path/'plan.json'),'runtime':plan['runtime']}
    dump(path/'summary.json',summary);dump(path/'case_deltas.json',case_deltas)
    flat=[{'qid':r['qid'],'type':r['qtype'],'condition':r['condition'],'answer_accuracy':r['answer_accuracy'],
           'fully_correct':r['fully_correct'],'not_found':r['not_found'],'input_tokens_est':r['compression']['input_tokens_est'],
           'api_input_tokens':r['answer']['result']['prompt_tokens'],'raw_input_tokens_est':r['compression']['raw_input_tokens_est'],
           'target_input_tokens':r['compression']['target_input_tokens'],'budget_difference':r['compression']['budget_difference'],
           'response':r['response'],'question':r['question'],'gold':r['reference_answer'],
           'fact_results':json.dumps(r['fact_grade']['fact_results'],ensure_ascii=False)} for r in rows]
    if flat:
        with (path/'trials.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    print(json.dumps({'split':split,'completed':len(rows),'conditions':{k:round(v['answer_accuracy'],4) if v['answer_accuracy'] is not None else None for k,v in stats.items()}},indent=2),flush=True)


def freeze():
    if (OUT/'algorithm_freeze.json').exists():raise ValueError('Already frozen')
    summary=load(OUT/'dev/summary.json');plan=load(OUT/'dev/plan.json')
    assert summary['completed_trials']==summary['expected_trials']==210
    assert all(s['valid_n']==s['n'] for s in summary['conditions'].values())
    check_hashes(plan['code_hashes'])
    dump(OUT/'algorithm_freeze.json',{'time_utc':now(),'code_hashes':fingerprint(code_files()),
         'dev_plan_sha256':sha(OUT/'dev/plan.json'),'dev_summary_sha256':sha(OUT/'dev/summary.json'),
         'config':cfg(),'runtime':public_runtime(),'statement':'No policy changes after this freeze. Independent sources/data not downloaded/generated before this point. Dev outcome does not trigger test tuning.'})
    print('FROZEN',sha(OUT/'algorithm_freeze.json'),flush=True)


def verify_freeze():
    f=load(OUT/'algorithm_freeze.json');check_hashes(f['code_hashes']);assert public_runtime()==f['runtime']


class BodyParser(HTMLParser):
    def __init__(self):super().__init__();self.active=False;self.depth=0;self.skip=0;self.out=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if not self.active and attrs.get('role')=='main':self.active=True;self.depth=1;return
        if not self.active:return
        if tag=='div':self.depth+=1
        if tag in ['script','style']:self.skip+=1
        if tag=='pre':self.out.append('\n```python\n')
        elif tag in ['p','li','h1','h2','h3','h4','dt','dd','tr']:self.out.append('\n')
    def handle_endtag(self,tag):
        if not self.active:return
        if tag=='div':
            self.depth-=1
            if self.depth==0:self.active=False
        if tag in ['script','style']:self.skip=max(0,self.skip-1)
        if tag=='pre':self.out.append('\n```\n')
        elif tag in ['p','li','h1','h2','h3','h4','dt','dd','tr']:self.out.append('\n')
    def handle_data(self,data):
        if self.active and not self.skip:self.out.append(data)


GEN_PROMPT='''Create exactly four grounded technical QA items from the supplied document, one each of fact, code, procedure, multi. Use only facts explicitly supported by this source. Questions must name the module/API to disambiguate. The procedure must ask a documented ordered process, not invented advice. The code question asks for a concrete exact API/expression, not executing arbitrary code. multi combines two distinct documented facts. Avoid trivia about page navigation. All four questions should cover different sections. Return ONLY a JSON array of objects with keys type, question, answer, key_facts (1-3 independently scorable strings), evidence (list of objects with quote copied EXACTLY as a contiguous substring of the supplied source). No Markdown fences around JSON. Questions must not state their own answer. Every fact must be supported by at least one quote. No missing details or inferred defaults. Document follows:\n\n'''
AUDIT_PROMPT='''Audit this synthetic QA item against the source text. Are the answer and EVERY key_fact fully supported, is the question unambiguous, and are the key_facts complete enough to score the question fairly? A procedure needs explicitly documented order. Reject questions that reveal their own answer. Reply only YES if ALL checks pass, else NO.\nITEM:\n{item}\nSOURCE:\n{source}'''


def parse_json_response(text):
    text=text.strip()
    if text.startswith('```'):text=re.sub(r'^```(?:json)?\s*|\s*```$','',text).strip()
    return json.loads(text)


def independent_data():
    import requests
    verify_freeze()
    if (OUT/'independent_dataset.json').exists():raise ValueError('Dataset already frozen')
    source_dir=OUT/'sources';source_dir.mkdir(exist_ok=True)
    oldsets=[ROOT/'data/evalsets/claude-v1'/n for n in ['qa_dev.json','qa_test.json']]
    olditems=[q for p in oldsets for q in load(p)]
    olddocs={f for q in olditems for f in q.get('source_files',q.get('evidence_pages',[]))}
    oldtext='\n'.join((ROOT/'data/openwiki/en'/f).read_text() for f in sorted(olddocs))
    def shingles(text):
        words=re.findall(r'\w+',text.lower());return {' '.join(words[i:i+12]) for i in range(max(0,len(words)-11))}
    oldshingles=shingles(oldtext);accepted=[];sources=[];audit=[]
    for module in cfg()['independent_documents']:
        src=source_dir/f'{module}.md';source_record=source_dir/f'{module}.source.json'
        if src.exists():sr=load(source_record);text=src.read_text()
        else:
            url=cfg()['source_url_template'].format(module=module)
            response=requests.get(url,timeout=60);response.raise_for_status()
            (source_dir/f'{module}.html').write_bytes(response.content)
            parser=BodyParser();parser.feed(response.text)
            raw=re.sub(r'\n{3,}','\n\n',''.join(parser.out)).replace('¶','')
            # Cap by whole lines, preserve complete fences. Only this fixed prefix is evaluated.
            lines=raw.splitlines(keepends=True);kept=[];inside=False
            for line in lines:
                if count_tokens(''.join(kept)+line)>cfg()['independent_doc_token_cap'] and not inside:break
                kept.append(line)
                if line.startswith('```'):inside=not inside
            text='## Document: python314/'+module+'.html\n\n'+''.join(kept).strip()
            assert count_tokens(text)>300,'Extraction failed: '+module
            src.write_text(text)
            newshingles=shingles(text);overlap=len(newshingles&oldshingles)/max(1,len(newshingles))
            assert overlap<=.05,'Source overlap too high'
            sr={'module':module,'url':url,'fetched_utc':now(),'html_sha256':sha(source_dir/f'{module}.html'),
                'text_sha256':sha(src),'context_tokens':count_tokens(text),'prefix_cap':cfg()['independent_doc_token_cap'],
                'old_document_overlap_ids':sorted(olddocs&{'python314/'+module+'.html'}),
                'old_corpus_12word_shingle_overlap_fraction':overlap,
                'license':'Python documentation, PSF license; https://docs.python.org/3.14/license.html',
                'freeze_sha256':sha(OUT/'algorithm_freeze.json')};dump(source_record,sr)
        sources.append(sr)
        genfile=source_dir/f'{module}.generation.json'
        if genfile.exists():gen=load(genfile)
        else:
            genclient=client('answer',4096);res=genclient.ask(GEN_PROMPT+text)
            gen={'prompt':GEN_PROMPT,'source_sha256':sha(src),'response':res.text,'result':result_dict(res),
                 'sampling':genclient.sampling_info(),'request_id':res.raw.get('id')};dump(genfile,gen)
        try:candidates=parse_json_response(gen['response']);assert isinstance(candidates,list) and len(candidates)==4
        except Exception:
            audit.append({'module':module,'accepted':False,'reason':'invalid generation JSON/schema; no regeneration'});continue
        module_types=Counter(q.get('type') for q in candidates)
        if set(module_types)!=set(cfg()['types']) or any(n!=1 for n in module_types.values()):
            audit.append({'module':module,'accepted':False,'reason':'not exactly one of each type; no regeneration'});continue
        for i,q in enumerate(candidates):
            qid=f'ind_{module}_{i+1}';schema_ok=(all(isinstance(q.get(k),str) and q[k].strip() for k in ['type','question','answer'])
                and isinstance(q.get('key_facts'),list) and 1<=len(q['key_facts'])<=3
                and all(isinstance(f,str) and f.strip() for f in q['key_facts'])
                and isinstance(q.get('evidence'),list) and bool(q['evidence'])
                and all(isinstance(e,dict) and isinstance(e.get('quote'),str) and e['quote'].strip() and e['quote'] in text for e in q['evidence']))
            af=source_dir/f'{qid}.audit.json'
            if not schema_ok:
                audit.append({'qid':qid,'accepted':False,'reason':'schema or exact quote validation failed','candidate':q});continue
            if af.exists():ar=load(af)
            else:
                judge=client('judge',4096);res=judge.ask(AUDIT_PROMPT.format(item=json.dumps(q),source=text))
                ok,error=parse_yes_no(res)
                ar={'qid':qid,'accepted':ok is True,'judge_error':error,'judge_response':res.text,
                    'result':result_dict(res),'sampling':judge.sampling_info(),'candidate':q,
                    'source_sha256':sha(src),'prompt_sha256':hashlib.sha256(AUDIT_PROMPT.encode()).hexdigest()};dump(af,ar)
            audit.append(ar)
            if ar['accepted']:
                accepted.append({**q,'id':qid,'split':'independent','context_path':str(src.relative_to(ROOT)),
                    'source_files':['python314/'+module+'.html'],'evidence_pages':['python314/'+module+'.html'],
                    'source_url':sr['url'],'automatic_audit_only':True})
        print('DATASET',module,'accepted total',len(accepted),flush=True)
    assert len(accepted)>=16,'Too few accepted questions; retain all artifacts and stop without evaluation/tuning'
    dump(OUT/'independent_dataset.json',accepted);dump(OUT/'dataset_audit.json',audit)
    dump(OUT/'dataset_metadata.json',{'created_utc':now(),'freeze_sha256':sha(OUT/'algorithm_freeze.json'),
          'dataset_sha256':sha(OUT/'independent_dataset.json'),'n':len(accepted),'types':dict(Counter(q['type'] for q in accepted)),
          'sources':sources,'old_dataset_sha256':fingerprint(oldsets),'generation_prompt':GEN_PROMPT,
          'audit_prompt':AUDIT_PROMPT,'selection':'Only schema, exact source quotes, automatic source-grounding audit; no answer performance inspected',
          'limitations':'Synthetic data; generator equals answer model; no independent human gold audit; API audit may err; no training-data independence claim.'})
    print('DATASET FROZEN',len(accepted),sha(OUT/'independent_dataset.json'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','run','summarize','freeze','dataset']);parser.add_argument('--split',choices=['dev','independent'],default='dev');args=parser.parse_args()
    if args.action in ['prepare','run','summarize']:{'prepare':prepare,'run':run,'summarize':summarize}[args.action](args.split)
    elif args.action=='freeze':freeze()
    else:independent_data()
