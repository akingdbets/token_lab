"""Recompute published study statistics offline; never imports API/model clients."""
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'docs/analysis/evidence-preservation/data'
CONDITIONS=('none','llmlingua2_r50','llmlingua2_r30','qp_identifiers_r30','qp_sentences_r30','qp_combined_r30')


def read_metrics(path):
    with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    seen=set()
    for r in rows:
        key=(r['split'],r['qid'],r['condition'])
        if key in seen:raise ValueError('Duplicate metric row: '+str(key))
        seen.add(key)
        if r['condition'] not in CONDITIONS:raise ValueError('Unknown condition')
        r['accuracy']=float(r['accuracy'])
        if not math.isfinite(r['accuracy']) or not 0<=r['accuracy']<=1:raise ValueError('Invalid accuracy')
        for k in ['question_order','input_tokens_est','api_input_tokens','target_input_tokens']:
            r[k]=int(r[k])
            if r[k]<0:raise ValueError('Negative count')
        for k in ['fully_correct','not_found']:
            if r[k] not in ['True','False']:raise ValueError('Invalid boolean')
            r[k]=r[k]=='True'
        if r['fully_correct']!=(r['accuracy']==1):raise ValueError('Inconsistent full-correct label')
    grouped=defaultdict(set)
    for r in rows:grouped[(r['split'],r['qid'])].add(r['condition'])
    if any(c!=set(CONDITIONS) for c in grouped.values()):raise ValueError('Incomplete paired conditions')
    return rows


def ci(ds,groups,reps=10000,seed=20261104,cluster=False):
    if not ds:return None
    rng=np.random.default_rng(seed);a=np.asarray(ds,dtype=float)
    if cluster:
        keys=sorted(set(groups))
        if len(keys)<2:return None
        sums=np.asarray([sum(d for d,g in zip(ds,groups) if g==k) for k in keys])
        sizes=np.asarray([groups.count(k) for k in keys]);idx=rng.integers(0,len(keys),size=(reps,len(keys)))
        means=sums[idx].sum(axis=1)/sizes[idx].sum(axis=1)
    else:means=a[rng.integers(0,len(a),size=(reps,len(a)))].mean(axis=1)
    return [float(np.quantile(means,.025)),float(np.quantile(means,.975))]


def analyze(rows,reps=10000,seed=20261104):
    out={}
    for split in sorted({r['split'] for r in rows}):
        rs=[r for r in rows if r['split']==split]
        index={(r['qid'],r['condition']):r for r in rs}
        qids=sorted({r['qid'] for r in rs},key=lambda q:index[(q,'none')]['question_order'])
        groups=[index[(q,'none')]['document_cluster'] for q in qids]
        conditions={}
        for c in CONDITIONS:
            cr=[index[(q,c)] for q in qids]
            delta=[r['api_input_tokens']-index[(r['qid'],'llmlingua2_r30')]['api_input_tokens'] for r in cr]
            conditions[c]={'n':len(cr),'accuracy':sum(r['accuracy'] for r in cr)/len(cr),
              'fully_correct_rate':sum(r['fully_correct'] for r in cr)/len(cr),
              'not_found_rate':sum(r['not_found'] for r in cr)/len(cr),
              'mean_api_input_tokens':sum(r['api_input_tokens'] for r in cr)/len(cr),
              'macro_reduction_pct':sum(100*(1-r['api_input_tokens']/index[(r['qid'],'none')]['api_input_tokens']) for r in cr)/len(cr),
              'aggregate_reduction_pct':100*(1-sum(r['api_input_tokens'] for r in cr)/sum(index[(r['qid'],'none')]['api_input_tokens'] for r in cr)),
              'mean_token_delta_vs_r30':sum(delta)/len(delta),'max_abs_token_delta_vs_r30':max(map(abs,delta)),
              'within_one_token':sum(abs(x)<=1 for x in delta),
              'by_type':{t:{'n':sum(r['qtype']==t for r in cr),
                 'accuracy':sum(r['accuracy'] for r in cr if r['qtype']==t)/sum(r['qtype']==t for r in cr),
                 'not_found_rate':sum(r['not_found'] for r in cr if r['qtype']==t)/sum(r['qtype']==t for r in cr)} for t in sorted({r['qtype'] for r in cr})}}
        contrasts={}
        for a,b in [('qp_identifiers_r30','llmlingua2_r30'),('qp_sentences_r30','llmlingua2_r30'),
                    ('qp_combined_r30','llmlingua2_r30'),('qp_combined_r30','qp_identifiers_r30'),('qp_combined_r30','qp_sentences_r30')]:
            ds=[index[(q,a)]['accuracy']-index[(q,b)]['accuracy'] for q in qids]
            contrasts[a+' - '+b]={'n':len(ds),'delta':sum(ds)/len(ds),'improved':sum(d>0 for d in ds),
               'worsened':sum(d<0 for d in ds),'unchanged':sum(d==0 for d in ds),
               'question_ci':ci(ds,groups,reps,seed),'cluster_ci':ci(ds,groups,reps,seed,True)}
        out[split]={'questions':len(qids),'document_clusters':len(set(groups)),'conditions':conditions,'contrasts':contrasts}
    return {'bootstrap_replicates':reps,'bootstrap_seed':seed,'splits':out}


def oracle_summary(path):
    with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    index={}
    for r in rows:
        key=(r['qid'],r['condition'],int(r['repeat']))
        if key in index:raise ValueError('Duplicate oracle row')
        index[key]=r
    result={}
    for condition in ['baseline','placebo','oracle']:
        rs=[r for r in rows if r['condition']==condition]
        result[condition]={'n':len(rs),'accuracy':sum(float(r['accuracy']) for r in rs)/len(rs),
            'fully_correct_rate':sum(float(r['accuracy'])==1 for r in rs)/len(rs)}
        eligible=[r for r in rs if float(index[(r['qid'],'baseline',int(r['repeat']))]['accuracy'])<float(r['historical_none_accuracy'])]
        result[condition]['recovery_eligible_n']=len(eligible)
        result[condition]['recovered_to_none_n']=sum(float(r['accuracy'])>=float(r['historical_none_accuracy']) for r in eligible)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--metrics',type=Path,default=DATA/'metrics.csv');p.add_argument('--output',type=Path);args=p.parse_args()
    result=analyze(read_metrics(args.metrics));oracle=args.metrics.with_name('oracle_metrics.csv')
    if oracle.exists():result['oracle']=oracle_summary(oracle)
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    else:print(text,end='')

if __name__=='__main__':main()
