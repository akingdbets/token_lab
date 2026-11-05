"""Export an allowlisted, compact review bundle from local research artifacts.

Read-only source. No LLM/API calls. Raw trials, responses, credentials, local paths,
request IDs, worktree status, caches and original run directories are not copied.
"""
import argparse
import csv
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write_csv(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)

class LicenseParser(HTMLParser):
    def __init__(self):super().__init__();self.active=False;self.depth=0;self.out=[]
    def handle_starttag(self,tag,attrs):
        if not self.active and dict(attrs).get('role')=='main':self.active=True;self.depth=1;return
        if self.active:
            if tag=='div':self.depth+=1
            if tag in ['p','li','h1','h2','h3','pre']:self.out.append('\n')
    def handle_endtag(self,tag):
        if self.active:
            if tag in ['p','li','h1','h2','h3','pre']:self.out.append('\n')
            if tag=='div':
                self.depth-=1
                if self.depth==0:self.active=False
    def handle_data(self,text):
        if self.active:self.out.append(text)


def export(source,out):
    final=source/'docs/analysis/final-experiment';oracle=source/'docs/analysis/oracle-pilot'
    out.mkdir(parents=True,exist_ok=False);data=out/'data';data.mkdir();corpus=out/'corpus';corpus.mkdir()
    metrics=[]
    for split in ['dev','independent']:
        plan=load(final/split/'plan.json');order={x['item']['id']:i for i,x in enumerate(plan['items'])}
        for row in map(json.loads,(final/split/'trials.jsonl').read_text().splitlines()):
            c=row['compression']
            metrics.append({'split':split,'qid':row['qid'],'question_order':order[row['qid']],
              'qtype':row['qtype'],'document_cluster':row['document_cluster'],'condition':row['condition'],
              'accuracy':row['answer_accuracy'],'fully_correct':row['fully_correct'],'not_found':row['not_found'],
              'input_tokens_est':c['input_tokens_est'],'api_input_tokens':row['answer']['result']['prompt_tokens'],
              'target_input_tokens':c['target_input_tokens'],'context_sha256':c['context_sha256']})
    write_csv(data/'metrics.csv',metrics)
    orows=[]
    for row in map(json.loads,(oracle/'trials.jsonl').read_text().splitlines()):
        orows.append({'qid':row['qid'],'category':row['category'],'condition':row['condition'],'repeat':row['repeat'],
          'accuracy':row['answer_accuracy'],'historical_none_accuracy':row['historical_none_accuracy'],
          'not_found':row['not_found'],'api_input_tokens':row['answer']['result']['prompt_tokens'],'insert_tokens':row['insert_tokens']})
    write_csv(data/'oracle_metrics.csv',orows)
    meta=load(final/'dataset_metadata.json');sources=[]
    for s in meta['sources']:
        module=s['module'];src=final/'sources'/f'{module}.md';(corpus/src.name).write_bytes(src.read_bytes())
        sources.append({k:s[k] for k in ['module','url','fetched_utc','html_sha256','text_sha256','context_tokens','prefix_cap','old_document_overlap_ids','old_corpus_12word_shingle_overlap_fraction','license']})
    qa=[]
    for q in load(final/'independent_dataset.json'):
        qa.append({k:q[k] for k in ['id','type','question','answer','key_facts','evidence','source_files','source_url','automatic_audit_only']})
    dump(data/'independent_qa.json',qa);dump(data/'sources.json',sources)
    dump(data/'audit_decisions.json',[{k:a[k] for k in ['qid','accepted','judge_error'] if k in a} for a in load(final/'dataset_audit.json')])
    license_parser=LicenseParser();license_parser.feed((final/'sources/python314-license.html').read_bytes().decode('utf-8'))
    (corpus/'LICENSE.txt').write_text('Python documentation copyright and license\nSource: https://docs.python.org/3.14/license.html\n\n'+''.join(license_parser.out).strip()+'\n',encoding='utf-8')
    freeze=load(final/'algorithm_freeze.json');dev=load(final/'dev/plan.json');op=load(oracle/'plan.json')
    relevant=['scripts/final_experiment.py','src/compressors/question_preserve.py','src/compressors/llmlingua2.py','src/grader.py','src/config.py','src/llm.py','src/experiment.py','src/prompts/answer_v1.md']
    provenance={'schema_version':1,'experiment_base_commit':dev['git_commit'],
      'measured_worktree_had_uncommitted_research_code':True,'algorithm_freeze_utc':freeze['time_utc'],
      'algorithm_freeze_sha256':sha(final/'algorithm_freeze.json'),'dataset_frozen_utc':meta['created_utc'],
      'original_dataset_sha256':meta['dataset_sha256'],
      'original_code_hashes':{k:v for k,v in freeze['code_hashes'].items() if k in relevant},
      'original_runtime':dev['runtime'],'configuration':freeze['config'],
      'original_summary_hashes':{s:sha(final/s/'summary.json') for s in ['dev','independent']},
      'oracle':{'plan_sha256':sha(oracle/'plan.json'),'code_hashes':{k:v for k,v in op['input_sha256'].items() if k in ['scripts/oracle_pilot.py','src/grader.py','src/llm.py','src/prompts/answer_v1.md']},
                'config':op['configuration'],'answer_prompt_hash':op['answer_prompt_hash'],'fact_judge_hash':op['fact_judge_hash']},
      'export_notes':['Metrics and QA content are copied, not re-evaluated.','Published QA omits original output paths; original dataset hash identifies the private full artifact.','Source markdown bytes are frozen extracts, including documented encoding artifacts.','No raw experiment logs, model responses, API request IDs or local absolute paths are exported.']}
    dump(data/'provenance.json',provenance)
    review=load(source/'docs/analysis/terra-review-20261104/metadata.json')
    dump(data/'damage_counts.json',{'test_run':Path(review['test']['path']).name,'dev_run':Path(review['dev']['path']).name,
      'denominators':review['denominators'],'join_issues':review['join_issues'],
      'source_summary_git_commit':review['test']['summary']['git_head'],
      'note':'Declines are compressed accuracy < paired none; A/B are preliminary source-checked candidate labels, not population prevalence.'})
    dump(data/'preprocessing_diagnostic.json',load(final/'preprocessing_diagnostic.json'))
    dump(data/'costs.json',load(final/'costs.json'))
    dump(data/'manifest.json',{str(p.relative_to(out)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()})
    print(f'Exported {len(metrics)} study + {len(orows)} oracle metric rows to {out}')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'docs/analysis/evidence-preservation');a=p.parse_args();export(a.source_root.resolve(),a.output.resolve())

if __name__=='__main__':main()
