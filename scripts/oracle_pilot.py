"""Prepare, run and report a frozen, token-matched oracle diagnostic pilot."""
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
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
# Fix public run settings before config loads .env (credentials remain environment-owned).
os.environ.update({'ANSWER_BACKEND':'openai','ANSWER_MODEL':'gpt-6.1-terra',
 'ANSWER_BASE_URL':'https://api.openai.com','JUDGE_BACKEND':'openai',
 'JUDGE_MODEL':'deepseek-flash','JUDGE_BASE_URL':'https://api.deepseek.com',
 'TOKENIZER':'tiktoken:o200k_base','ANSWER_REASONING_EFFORT':'none',
 'JUDGE_REASONING_EFFORT':'','LLM_TEMPERATURE':'0','LLM_SEED':'42',
 'LLM_NUM_CTX':'16384','EVAL_DIR':'data/evalsets/claude-v1'})
from config import CFG
from experiment import load_answer_prompt
from grader import (grade_answer_accuracy, grade, is_not_found_answer,
                    FACT_JUDGE_PROMPT_HASH, FACT_JUDGE_SINGLE_PROMPT, JUDGE_PROMPT, is_short)
from llm import LLM, count_tokens, count_message_tokens

OUT = ROOT/'docs/analysis/oracle-pilot'
CONDITIONS = ('baseline','placebo','oracle')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def messages(prompt, item, context):
    return prompt.messages(prompt.parts(context, item['question'], item['type']))


def matched_placebo(base, oracle, pool, prompt, item):
    target = count_message_tokens(messages(prompt,item,base+'\n\n'+oracle))
    candidates = []
    for m in re.finditer(r'\s+',pool):
        end=m.start()
        if end==0:continue
        text=pool[:end]
        n=count_message_tokens(messages(prompt,item,base+'\n\n'+text))
        candidates.append((abs(n-target),end,n,text))
    _,end,n,text=min(candidates)
    return text, {'oracle_total_input_est':target,'placebo_total_input_est':n,
                 'placebo_minus_oracle_est':n-target,'placebo_prefix_characters':end}


def prepare():
    if (OUT/'plan.json').exists():
        raise ValueError('Frozen plan already exists; do not overwrite')
    cfg=load(OUT/'selection_config.json')
    review=ROOT/cfg['review_source'];run=ROOT/cfg['source_run']
    payload=load(review/'review_data.json');meta=load(review/'metadata.json')
    summary=load(run/'summary.json')
    prompt=load_answer_prompt('v1')
    assert prompt.sha256==summary['config']['answer_prompt']['sha256']
    assert FACT_JUDGE_PROMPT_HASH==summary['config']['fact_judge']['prompt_hash']
    assert summary['config']['models']==CFG.models_info(), 'Model endpoint or tokenizer differs'
    failures={r['qid']+'/'+r['compressor']:r for r in payload['records'] if r['cohort']=='decline'}
    assert len(failures)==41
    with (review/'review_template.csv').open(encoding='utf-8-sig',newline='') as f:
        csv_trials={r['trial_id'] for r in csv.DictReader(f)}
    source=ROOT/cfg['placebo_source'];source_text=source.read_text()
    pool=source_text.split(cfg['placebo_start'],1)[1].split(cfg['placebo_end'],1)[0]
    pool=cfg['placebo_start']+pool.rstrip()
    inputs={}
    def record_input(p):
        inputs[str(p.relative_to(ROOT))]=digest(p.read_bytes())
    for p in [OUT/'selection_config.json',review/'review_data.json',review/'review_template.csv',review/'metadata.json',run/'summary.json',run/'args.json',run/'trials.jsonl',source,ROOT/'data/evalsets/claude-v1/qa_test.json',ROOT/'src/prompts/answer_v1.md',Path(__file__)]:record_input(p)
    for name in ['config.py','llm.py','grader.py','experiment.py']:record_input(ROOT/'src'/name)
    (OUT/'contexts').mkdir(exist_ok=True)
    cases=[]
    for spec in cfg['cases']:
        r=failures[spec['qid']+'/llmlingua2_r30'];q=r['dataset_item'];qid=r['qid']
        assert r['trial_id'] in csv_trials and not r['join_errors']
        assert qid not in cfg['suspected_D_qids']
        base=(run/'contexts'/f'{qid}.llmlingua2_r30.md').read_text()
        original=(run/'contexts'/f'{qid}.none.md').read_text()
        assert base==r['compressed_context'] and original==r['original_context']
        for c in ['none','llmlingua2_r30']:record_input(run/'contexts'/f'{qid}.{c}.md')
        if spec.get('missing_literal'):assert spec['missing_literal'].casefold() not in base.casefold(),qid
        for anchor in spec.get('surviving_anchors',[]):assert anchor.casefold() in base.casefold(),(qid,anchor)
        if spec.get('lost_link'):assert spec['lost_link'].casefold() not in base.casefold(),qid
        quotes=[]
        for idx in spec['evidence_indices']:
            e=q['evidence'][idx];quote=spec.get('quote_prefix',e['quote'])
            assert quote in e['quote'] and quote in original
            page=ROOT/'data/openwiki/en'/e['page'];record_input(page)
            text=page.read_text();assert quote in text
            quotes.append({'text':quote,'page':e['page'],'source_char_start':text.index(quote),
                           'source_line':text[:text.index(quote)].count('\n')+1,
                           'original_context_char_start':original.index(quote)})
        if spec.get('extra_source_line_contains'):
            page=ROOT/'data/openwiki/en'/spec['extra_source_page'];record_input(page)
            text=page.read_text();line=next(s for s in text.splitlines() if spec['extra_source_line_contains'] in s)
            assert line in original
            quotes.insert(0,{'text':line,'page':spec['extra_source_page'],'source_char_start':text.index(line),
                             'source_line':text[:text.index(line)].count('\n')+1,'original_context_char_start':original.index(line)})
        oracle='\n'.join(x['text'] for x in quotes)
        placebo,tokens=matched_placebo(base,oracle,pool,prompt,q)
        assert placebo in source_text and all(x['text'] in original for x in quotes)
        contexts={'baseline':base,'placebo':base+'\n\n'+placebo,'oracle':base+'\n\n'+oracle,'original':original}
        paths={};hashes={}
        for name,text in contexts.items():
            p=OUT/'contexts'/f'{qid}.{name}.md';p.write_text(text);paths[name]=str(p.relative_to(ROOT));hashes[name]=digest(p.read_bytes())
        cases.append({'qid':qid,'source_trial_id':r['trial_id'],'compressor':r['compressor'],
            'category':spec['category'],'selection_reason':spec['reason'],'source_checked_by':'Codex; human review pending',
            'item':q,'original_trial':r['none_trial'],'historical_baseline_trial':r['compressed_trial'],
            'oracle_quotes':quotes,'placebo_quote':placebo,'placebo_source':cfg['placebo_source'],
            'placebo_source_char_start':source_text.index(placebo),'insertion_char_offset':len(base),
            'contexts':paths,'context_sha256':hashes,'token_matching':tokens,
            'baseline_input_est':count_message_tokens(messages(prompt,q,base)),
            'oracle_insert_tokens':count_tokens(oracle),'placebo_insert_tokens':count_tokens(placebo),
            'baseline_context_tokens':count_tokens(base)})
    assert Counter(c['category'] for c in cases)=={'A':5,'B':5}
    assert len({c['qid'] for c in cases})==10
    schedule=[{'qid':c['qid'],'condition':condition,'repeat':rep} for c in cases for condition in CONDITIONS for rep in range(1,4)]
    random.Random(cfg['schedule_seed']).shuffle(schedule)
    answer_input=sum(c['baseline_input_est']+c['token_matching']['oracle_total_input_est']+c['token_matching']['placebo_total_input_est'] for c in cases)*3
    fact_calls=sum(len(c['item']['key_facts']) for c in cases)*9
    # Judge estimate uses reference answer as a transparent candidate-length proxy, not a prediction.
    judge_est=sum(sum(count_message_tokens([{'role':'user','content':FACT_JUDGE_SINGLE_PROMPT.format(question=c['item']['question'],reference_answer=c['item']['answer'],candidate_answer=c['item']['answer'],fact=fact)}]) for fact in c['item']['key_facts']) for c in cases)*9
    ox_calls=sum(not is_short(c['item']['answer']) for c in cases)*9
    ox_est=sum(count_message_tokens([{'role':'user','content':JUDGE_PROMPT.format(q=c['item']['question'],a=c['item']['answer'],r=c['item']['answer'])}]) for c in cases if not is_short(c['item']['answer']))*9
    plan={'created_utc':datetime.now(timezone.utc).isoformat(),'configuration':cfg,'cases':cases,'schedule':schedule,
          'source_summary':summary,'source_analysis_metadata':meta,'input_sha256':inputs,
          'answer_prompt_hash':prompt.sha256,'fact_judge_hash':FACT_JUDGE_PROMPT_HASH,
          'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
          'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'git_status':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
          'packages':{p:importlib.metadata.version(p) for p in ['requests','tiktoken','python-dotenv']},
          'dry_run':{'answer_calls':90,'fact_judge_calls_max':fact_calls,'ox_judge_calls_max':ox_calls,
                     'answer_input_tokens_est':answer_input,'answer_output_token_cap':90*512,
                     'fact_judge_input_proxy_est':judge_est,'fact_judge_output_token_cap':fact_calls*4096,
                     'ox_judge_input_proxy_est':ox_est,'ox_judge_output_token_cap':ox_calls*4096,
                     'note':'NOT FOUND/empty skip fact calls; short answers skip OX. Per-call 4096 judge cap. tiktoken chat estimates, billed usage recorded later. No API calls during prepare.'}}
    dump(OUT/'plan.json',plan)
    lines=['# 사전 고정 dry-run','',json.dumps(plan['dry_run'],ensure_ascii=False,indent=2),'',
           '|qid|분류|baseline 입력|oracle 입력|placebo 입력|차이(P−O)|선정 이유|','|---|---|---:|---:|---:|---:|---|']
    for c in cases:
        t=c['token_matching'];lines.append(f"|{c['qid']}|{c['category']}|{c['baseline_input_est']}|{t['oracle_total_input_est']}|{t['placebo_total_input_est']}|{t['placebo_minus_oracle_est']}|{c['selection_reason']}|")
    for c in cases:
        lines.extend(['',f"## {c['qid']} ({c['category']})",'원문 복원 구절 (문서 경로와 실제 위치는 plan.json 참조):','',*['> '+q['text'] for q in c['oracle_quotes']],'','Placebo:','',c['placebo_quote']])
    (OUT/'dry_run.md').write_text('\n'.join(lines))
    audit=[]
    for r in sorted(failures.values(),key=lambda x:x['trial_id']):
        qid=r['qid'];selected=next((c for c in cases if c['source_trial_id']==r['trial_id']),None)
        audit.append({'trial_id':r['trial_id'],'decision':'selected' if selected else 'excluded',
                      'reason':selected['selection_reason'] if selected else cfg['suspected_D_reason'] if qid in cfg['suspected_D_qids'] else 'Not in fixed purposeful manifest; r50 excluded to avoid duplicate qids and hold r30 constant, other r30 cases not prioritized for clear isolated damage. Not a confirmed damage label.'})
    dump(OUT/'selection_audit.json',audit)
    print(json.dumps(plan['dry_run'],indent=2));print('Frozen plan SHA256:',digest((OUT/'plan.json').read_bytes()))


def validate(plan):
    for name,sha in plan['input_sha256'].items():
        if digest((ROOT/name).read_bytes())!=sha:raise ValueError('Input changed: '+name)
    for c in plan['cases']:
        for condition,path in c['contexts'].items():
            if digest((ROOT/path).read_bytes())!=c['context_sha256'][condition]:raise ValueError('Context changed: '+path)


def make_llms():
    answer=LLM(role='answer',max_tokens=512,max_retries=1,timeout=60)
    answer.unsupported.add('max_tokens')
    fact=LLM(role='judge',max_tokens=4096,max_retries=1,timeout=60)
    ox=LLM(role='judge',max_tokens=4096,max_retries=1,timeout=60)
    for client in [answer,fact,ox]:
        if not client.api_key:raise ValueError('Missing credentials for '+client.role)
    CFG.network_retry_waits=()
    return answer,fact,ox


def execute():
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    plan=load(OUT/'plan.json');validate(plan)
    state=OUT/'execution_state.json'
    if state.exists() and load(state)['plan_sha256']!=digest((OUT/'plan.json').read_bytes()):raise ValueError('Plan changed since execution')
    dump(state,{'plan_sha256':digest((OUT/'plan.json').read_bytes()),'started_utc':datetime.now(timezone.utc).isoformat(),'workers':3})
    prompt=load_answer_prompt('v1');cases={c['qid']:c for c in plan['cases']}
    path=OUT/'trials.jsonl'
    existing=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    done={(r['qid'],r['condition'],r['repeat']) for r in existing if r.get('status')=='complete'}
    # Persist answer before judge: reruns never silently regenerate an already paid answer.
    cache=OUT/'answer_cache';cache.mkdir(exist_ok=True)
    lock=threading.Lock()
    def task(t):
        qid=t['qid'];condition=t['condition'];rep=t['repeat'];c=cases[qid];q=c['item']
        answer,fact,ox=make_llms();context=(ROOT/c['contexts'][condition]).read_text()
        cachefile=cache/f'{qid}.{condition}.{rep}.json'
        if cachefile.exists():
            a=load(cachefile);assert a['context_sha256']==c['context_sha256'][condition]
        else:
            result=answer.chat(messages(prompt,q,context))
            if result.model!='gpt-6.1-terra' and not result.model.startswith('gpt-6.1-terra-'):raise ValueError('Unexpected answer model: '+result.model)
            a={'response':result.text,'result':{k:v for k,v in asdict(result).items() if k!='raw'},
               'sampling':answer.sampling_info(),'context_sha256':c['context_sha256'][condition],
               'api_request_id':result.raw.get('id'),'system_fingerprint':result.raw.get('system_fingerprint')}
            dump(cachefile,a)
        nf=is_not_found_answer(a['response'])
        fg=grade_answer_accuracy(q['question'],q['answer'],q['key_facts'],a['response'],fact,mode='per_fact')
        oxg=grade(q['question'],q['answer'],q.get('key_entities',[]),a['response'],judge_llm=ox)
        score=fg.answer_accuracy
        row={**t,'category':c['category'],'status':'complete','timestamp_utc':datetime.now(timezone.utc).isoformat(),
             'context_sha256':c['context_sha256'][condition],'answer':a,'question':q['question'],
             'reference_answer':q['answer'],'key_facts':q['key_facts'],'not_found':nf,
             'answer_accuracy':score,'fully_correct':score==1 if score is not None else None,
             'fact_grade':asdict(fg),'ox_grade':asdict(oxg),
             'fact_sampling':fact.sampling_info(),'ox_sampling':ox.sampling_info(),
             'insert_tokens':0 if condition=='baseline' else c[condition+'_insert_tokens'],
             'input_est':count_message_tokens(messages(prompt,q,context)),
             'historical_accuracy':c['historical_baseline_trial']['answer_accuracy'],
             'historical_none_accuracy':c['original_trial']['answer_accuracy'],
             'response_changed_from_historical':a['response'].strip()!=c['historical_baseline_trial']['response'].strip()}
        with lock:
            with path.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
        print(qid,condition,rep,'accuracy=',score,'NOT FOUND=',nf,flush=True)
        return row
    tasks=[t for t in plan['schedule'] if (t['qid'],t['condition'],t['repeat']) not in done]
    errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        fs={pool.submit(task,t):t for t in tasks}
        for future in as_completed(fs):
            try:future.result()
            except Exception as e:
                # Never log headers/credentials or full HTTP error bodies.
                err={**fs[future],'error_type':type(e).__name__,'http_status':getattr(getattr(e,'response',None),'status_code',None)}
                errors.append(err);print('TASK ERROR',err,flush=True)
    dump(OUT/'execution_errors.json',errors)
    report()
    if errors:raise SystemExit('Some tasks failed; cached answers preserved, see execution_errors.json')


def report():
    plan=load(OUT/'plan.json')
    rows=[json.loads(s) for s in (OUT/'trials.jsonl').read_text().splitlines()]
    bykey={(r['qid'],r['condition'],r['repeat']):r for r in rows}
    if len(bykey)!=len(rows):raise ValueError('Duplicate completed trials')
    flat=[]
    for r in rows:
        paired=bykey.get((r['qid'],'baseline',r['repeat']))
        b=paired['answer_accuracy'] if paired else None;s=r['answer_accuracy'];none=r['historical_none_accuracy']
        flat.append({'qid':r['qid'],'category':r['category'],'condition':r['condition'],'repeat':r['repeat'],
            'question':r['question'],'gold':r['reference_answer'],'response':r['answer']['response'],
            'accuracy':s,'fully_correct':r['fully_correct'],'not_found':r['not_found'],
            'baseline_accuracy':b,'improved_vs_paired_baseline':s>b if s is not None and b is not None else None,
            'recovered_to_none':s>=none if s is not None else None,
            'normalized_gap_recovery':(s-b)/(none-b) if s is not None and b is not None and none>b else None,
            'insert_tokens':r['insert_tokens'],'input_est':r['input_est'],
            'answer_prompt_tokens':r['answer']['result']['prompt_tokens'],'answer_completion_tokens':r['answer']['result']['completion_tokens'],
            'fact_results':json.dumps(r['fact_grade']['fact_results'],ensure_ascii=False),
            'historical_response_changed':r['response_changed_from_historical'],
            'paired_baseline_response':paired['answer']['response'] if paired else None,
            'response_changed_vs_paired_baseline':r['answer']['response']!=paired['answer']['response'] if paired else None})
    with (OUT/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    dump(OUT/'results.json',rows)
    def mean(values):
        vals=[v for v in values if v is not None];return sum(vals)/len(vals) if vals else None
    summary=[]
    for category in ['all','A','B']:
        for condition in CONDITIONS:
            rs=[r for r in flat if r['condition']==condition and (category=='all' or r['category']==category)]
            valid=[r for r in rs if r['accuracy'] is not None]
            none_by_qid={c['qid']:c['original_trial']['answer_accuracy'] for c in plan['cases']}
            eligible=[r for r in valid if r['baseline_accuracy'] is not None and r['baseline_accuracy']<none_by_qid[r['qid']]]
            summary.append({'category':category,'condition':condition,'n':len(rs),'valid_n':len(valid),
                'accuracy':mean([r['accuracy'] for r in rs]),'fully_correct_rate':mean([r['fully_correct'] for r in valid]),
                'not_found_rate':mean([r['not_found'] for r in rs]),
                'improved_vs_baseline_rate':mean([r['improved_vs_paired_baseline'] for r in valid]) if condition!='baseline' else None,
                'recovery_eligible_n':len(eligible),'recovered_to_none_rate':mean([r['recovered_to_none'] for r in eligible]),
                'normalized_gap_recovery':mean([r['normalized_gap_recovery'] for r in eligible])})
    usage={k:sum(r['answer']['result'][k] for r in rows) for k in ['prompt_tokens','completion_tokens']}
    usage.update({k:sum(r['fact_grade'][k]+r['ox_grade'][k] for r in rows) for k in ['judge_prompt_tokens','judge_completion_tokens']})
    actual_deltas=[]
    for c in plan['cases']:
        for rep in range(1,4):
            p=bykey.get((c['qid'],'placebo',rep));o=bykey.get((c['qid'],'oracle',rep))
            if p and o:actual_deltas.append({'qid':c['qid'],'repeat':rep,'placebo_minus_oracle_billed_prompt_tokens':p['answer']['result']['prompt_tokens']-o['answer']['result']['prompt_tokens']})
    dump(OUT/'summary.json',{'conditions':summary,'usage':usage,'actual_token_matching':actual_deltas,'completed':len(rows),'expected':90})
    lines=['# Oracle 근거 복원 파일럿','',f"완료 {len(rows)}/90 시행. source run: 20261104-165320. Branch: {plan['branch']}. 원본 run과 평가셋 수정 없음.",'',
      '## 방법','',plan['configuration']['selection_protocol'],'',
      'A=값/식별자 손실, B=살아남은 대상 사이의 관계·조건·시간 단위·순서 손실. B에서 일부 entity 삭제가 함께 발생할 수 있다. source 검증은 Codex가 수행했으며 사람 검증 라벨이 아니다. 선정과 문맥은 첫 호출 전 plan.json에 고정했다. 41개 중 목적 표집한 r30 10건(A5/B5)이며 r50 또는 전체 실패에 일반화하지 않는다.',
      '', 'Baseline은 기존 압축 파일과 바이트가 같다. Oracle은 원본 none 문맥과 원본 기술 문서 모두에서 정확히 확인한 구절만 추가했다. Placeholder/gold 재작성은 없다. Placebo는 같은 코퍼스의 worker·메모리 문서에서 정답과 무관한 연속 구절을 추가했다. 두 조건 모두 baseline 끝 동일 위치, 동일 두 줄 구분자로 삽입했다. 토큰 비교는 전체 메시지에 대해 수행했고 근사치 및 실제 usage 차이를 summary.json에 남겼다.',
      '', 'Terra, answer_v1, temperature=0, seed=42, reasoning_effort=none, 답변 512토큰. DeepSeek-flash fact_judge_v2 per_fact 및 기존 OX 규칙(4096토큰)을 재사용했다. 각 조건 3회, 고정 schedule shuffle, 최대 3개의 동시 요청. 반복 seed를 바꾸지 않았으므로 독립 표본이 아니며 90회를 n=90 독립 관측으로 해석하지 않는다.',
      '', '회복 분모는 같은 qid/반복의 재실행 baseline 점수가 historical none보다 낮은 쌍이다. recovered_to_none는 그 none 수준 도달 비율, normalized_gap_recovery는 (조건−baseline)/(none−baseline)이며 음수도 허용한다. improved_vs_baseline는 유효한 전체 paired 시행 중 점수가 증가한 비율이다. 완전 정답은 key_fact accuracy=1이다. Judge 실패(None)는 평균에서 제외하고 valid_n으로 공개한다.',
      '', '## 조건별 비교','', '|분류|조건|n/유효|핵심 사실 정확도|완전 정답률|NOT FOUND|paired 개선률|회복 분모|none 수준 회복률|', '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    fmt=lambda x:'NA' if x is None else f'{x:.3f}'
    for s in summary:lines.append(f"|{s['category']}|{s['condition']}|{s['n']}/{s['valid_n']}|{fmt(s['accuracy'])}|{fmt(s['fully_correct_rate'])}|{fmt(s['not_found_rate'])}|{fmt(s['improved_vs_baseline_rate'])}|{s['recovery_eligible_n']}|{fmt(s['recovered_to_none_rate'])}|")
    lines+=['','## 문항별 결과와 실제 답변 변화 (미개선도 모두 포함)','']
    for c in plan['cases']:
        qid=c['qid'];lines+=[f"### {qid} ({c['category']})",c['selection_reason'],'',f"질문: {c['item']['question']}",'']
        for rep in range(1,4):
            lines.append(f'반복 {rep}:')
            for condition in CONDITIONS:
                r=bykey.get((qid,condition,rep))
                if r:lines.extend([f"- {condition}: accuracy={r['answer_accuracy']}, NOT FOUND={r['not_found']}",'','```text',r['answer']['response'],'```',''])
            b=bykey.get((qid,'baseline',rep));o=bykey.get((qid,'oracle',rep));p=bykey.get((qid,'placebo',rep))
            if b and o:
                good=o['answer_accuracy'] is not None and b['answer_accuracy'] is not None and o['answer_accuracy']>b['answer_accuracy']
                lines.append('Judge 점수 증가.' if good else '**Oracle 미개선 또는 판정 불가** — 위 답변 원문을 대조할 것.')
                if p and o['answer_accuracy'] is not None and p['answer_accuracy'] is not None and o['answer_accuracy']<=p['answer_accuracy']:lines.append('Oracle이 placebo보다 높지 않음.')
        lines.append('')
    lines+=['## 한계','',
      '답변 텍스트와 fact별 YES/NO 원문을 보존했지만 독립 사람 검수는 수행하지 않았다. 점수 상승만으로 인과 회복을 확정하지 않는다. 선택은 원래 실패에 조건부이므로 회귀 효과가 있고 새 baseline이 이를 확인한다. Oracle은 정답 정보를 활용한 진단적 상한 실험이며 배포 가능한 압축기가 아니다. 토큰 수를 맞춰도 관련성·문체·구절 구조·주의 배분이 완전히 통제되지는 않는다. 외부 문서 placebo는 관련성 외 문서 출처 차이를 동반한다. 짧은 prefix가 문장 중간에서 끝날 수 있다. B의 복합 손상, 소표본, 모델 서버 비결정성, 고정 seed 반복의 상관, judge 오판과 금답의 불완전성을 고려해야 한다. p-value 또는 모집단 원인 비율은 추정하지 않는다.',
      '', '## 사용량','',json.dumps(usage,indent=2),'','재현 및 파일 설명: README.md. 실행 오류는 execution_errors.json, 실제 토큰 차이는 summary.json 참조.']
    (OUT/'report.md').write_text('\n'.join(lines))
    print(json.dumps({'completed':len(rows),'summary':summary,'usage':usage},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','run','report']);args=parser.parse_args()
    {'prepare':prepare,'run':execute,'report':report}[args.action]()
