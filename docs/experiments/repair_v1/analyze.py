"""Reproduce descriptive and paired statistics from local raw runs; no APIs."""
import argparse,json,math,random
from collections import Counter
from pathlib import Path
from statistics import mean

def valid(x):return isinstance(x,(int,float)) and math.isfinite(x)
def percentile(xs,q):
 xs=sorted(xs);p=(len(xs)-1)*q;i=int(p);j=math.ceil(p)
 return xs[i]+(xs[j]-xs[i])*(p-i)
def stats(rows):
 scores=[r['answer_accuracy'] for r in rows if valid(r['answer_accuracy'])]
 return dict(n=len(rows),scored=len(scores),accuracy=mean(scores) if scores else None,
  full=sum(x==1 for x in scores),not_found=sum(r['not_found'] for r in rows),
  input_reduction_pct=100*(1-sum(r['input_tokens'] for r in rows)/sum(r['input_tokens_raw'] for r in rows)),
  mean_output_tokens=mean(r['completion_tokens'] for r in rows))
def paired(a,b):
 a={r['qid']:r for r in a};b={r['qid']:r for r in b}
 qs=sorted(q for q in a.keys()&b.keys() if valid(a[q]['answer_accuracy']) and valid(b[q]['answer_accuracy']))
 assert all(a[q]['question']==b[q]['question'] and a[q]['answer']==b[q]['answer'] for q in qs)
 ds=[b[q]['answer_accuracy']-a[q]['answer_accuracy'] for q in qs];rng=random.Random(42)
 boots=[mean(rng.choices(ds,k=len(ds))) for _ in range(10000)]
 gain=sum(a[q]['answer_accuracy']<1 and b[q]['answer_accuracy']==1 for q in qs)
 loss=sum(a[q]['answer_accuracy']==1 and b[q]['answer_accuracy']<1 for q in qs)
 n=gain+loss;p=min(1,2*sum(math.comb(n,i) for i in range(min(gain,loss)+1))/2**n) if n else 1
 return dict(n=len(qs),old_mean=mean(a[q]['answer_accuracy'] for q in qs),new_mean=mean(b[q]['answer_accuracy'] for q in qs),
  delta=mean(ds),ci95=[percentile(boots,.025),percentile(boots,.975)],mcnemar_p=p,
  gains_full=gain,losses_full=loss,improved=sum(d>0 for d in ds),worsened=sum(d<0 for d in ds))
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--runs-root',type=Path,default=Path(__file__).resolve().parents[3]/'results/runs');args=parser.parse_args()
 runs={}
 for name in ['20261103-001108','20261104-211703','repair-luna-default-20261105']:
  path=args.runs_root/name/'trials.jsonl'
  if not path.is_file():parser.error(f'Local raw run required: {path}')
  rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
  if name=='20261103-001108':rows=[r for r in rows if r['compressor'] in ['none','llmlingua2_r50','llmlingua2_r30']]
  runs[name]={'rows':rows}
 out={'runs':{},'baseline_vs_repair':{},'repair_settings':{}}
 for name,run in runs.items():
  out['runs'][name]={}
  for c in sorted({r['compressor'] for r in run['rows']}):
   rs=[r for r in run['rows'] if r['compressor']==c]
   out['runs'][name][c]=dict(overall=stats(rs),by_type={t:stats([r for r in rs if r['qtype']==t]) for t in sorted({r['qtype'] for r in rs})},
    repair_statuses=dict(Counter(r['info'].get('status') for r in rs)),
    actions=dict(Counter(s['action'] for r in rs for s in r['info'].get('selected_sentences',[]))))
 for rate in ['50','30']:
  old=[r for r in runs['20261103-001108']['rows'] if r['compressor']=='llmlingua2_r'+rate]
  repair=[r for r in runs['20261104-211703']['rows'] if r['compressor']=='llmlingua2_repair_v1_r'+rate]
  default=[r for r in runs['repair-luna-default-20261105']['rows'] if r['compressor']=='llmlingua2_repair_v1_r'+rate]
  out['baseline_vs_repair'][rate]=paired(old,repair)
  out['repair_settings'][rate]={t:paired([r for r in repair if t=='all' or r['qtype']==t],[r for r in default if t=='all' or r['qtype']==t]) for t in ['all','multi','procedure']}
 order=sorted(out['baseline_vs_repair'],key=lambda k:out['baseline_vs_repair'][k]['mcnemar_p']);prev=0
 for i,k in enumerate(order):
  prev=max(prev,min(1,(2-i)*out['baseline_vs_repair'][k]['mcnemar_p']));out['baseline_vs_repair'][k]['holm_p']=prev
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
