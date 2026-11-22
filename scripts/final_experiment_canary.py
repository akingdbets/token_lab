"""Resume two real pending tasks to validate changed credentials without throwaway calls."""
import json
import re
from dataclasses import asdict
import final_experiment as f
from grader import grade_answer_accuracy,is_not_found_answer


def main():
    path=f.OUT/'dev';plan=f.load(path/'plan.json');f.check_hashes(plan['code_hashes'])
    f.check_hashes(plan['original_input_hashes']);assert f.public_runtime()==plan['runtime']
    old=[json.loads(s) for s in (path/'trials.jsonl').read_text().splitlines()]
    done={(r['qid'],r['condition']) for r in old}
    items={x['item']['id']:x for x in plan['items']};comp={(r['qid'],r['condition']):r for r in plan['compression']}
    diagnostics=[]
    for stage in ['cached_judge','new_answer_and_judge']:
        def eligible(t):
            if (t['qid'],t['condition']) in done:return False
            cache=path/'answer_cache'/f"{t['qid']}.{t['condition']}.json"
            if stage=='new_answer_and_judge':return not cache.exists()
            return cache.exists() and bool(f.load(cache)['response'].strip()) and not is_not_found_answer(f.load(cache)['response'])
        t=next((t for t in plan['schedule'] if eligible(t)),None)
        if t is None:continue
        q=items[t['qid']]['item'];cr=comp[(t['qid'],t['condition'])];cache=path/'answer_cache'/f"{t['qid']}.{t['condition']}.json"
        try:
            if cache.exists():a=f.load(cache);assert a['context_sha256']==cr['context_sha256']
            else:
                answer=f.client('answer');res=answer.chat(f.answer_messages(q,(f.ROOT/cr['context_path']).read_text()))
                assert res.model=='gpt-6.1-terra' or res.model.startswith('gpt-6.1-terra-')
                a={'response':res.text,'result':f.result_dict(res),'sampling':answer.sampling_info(),
                  'request_id':res.raw.get('id'),'system_fingerprint':res.raw.get('system_fingerprint'),
                  'context_sha256':cr['context_sha256']};f.dump(cache,a)
            fact=f.client('judge',4096)
            fg=grade_answer_accuracy(q['question'],q['answer'],q['key_facts'],a['response'],fact,mode='per_fact')
            row={**t,'status':'complete','time_utc':f.now(),'split':'dev','qtype':q['type'],
              'document_cluster':items[t['qid']]['cluster'],'source_files':q.get('source_files',q.get('evidence_pages',[])),
              'question':q['question'],'reference_answer':q['answer'],'key_facts':q['key_facts'],
              'response':a['response'],'answer_model':a['result']['model'],'answer':a,'fact_grade':asdict(fg),
              'judge_sampling':fact.sampling_info(),'answer_accuracy':fg.answer_accuracy,
              'fully_correct':fg.answer_accuracy==1 if fg.answer_accuracy is not None else None,
              'not_found':is_not_found_answer(a['response']),'compression':cr,'compression_api_tokens':0,'compression_api_calls':0}
            f.append(path/'trials.jsonl',row);done.add((t['qid'],t['condition']))
            d={'stage':stage,'task':t,'success':True,'accuracy':fg.answer_accuracy}
        except Exception as e:
            response=getattr(e,'response',None)
            try:body=response.json()
            except Exception:body={}
            error=body.get('error',{});error=error if isinstance(error,dict) else {}
            d={'stage':stage,'task':t,'success':False,'http_status':getattr(response,'status_code',None),
              'error_type':error.get('type'),'error_code':error.get('code'),
              'message':re.sub(r'sk-[A-Za-z0-9_-]+','[REDACTED]',str(error.get('message','')))[:400]}
            diagnostics.append(d);f.dump(f.OUT/'api_resume_diagnostics.json',{'time_utc':f.now(),'diagnostics':diagnostics})
            print(json.dumps(d),flush=True);raise SystemExit('Credential check failed; bulk evaluation not started')
        diagnostics.append(d);print(json.dumps(d),flush=True)
    f.dump(f.OUT/'api_resume_diagnostics.json',{'time_utc':f.now(),'diagnostics':diagnostics})

if __name__=='__main__':main()
