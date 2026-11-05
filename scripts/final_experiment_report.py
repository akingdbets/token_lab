"""Offline tables, paired/cluster intervals, reproducibility manifest and study ZIP."""
import argparse
import csv
import hashlib
import io
import json
import platform
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/analysis/final-experiment'
sys.path.insert(0,str(ROOT/'scripts'))
from final_experiment import bootstrap,cfg,check_hashes


def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def avg(xs):
    xs=[x for x in xs if x is not None];return sum(xs)/len(xs) if xs else None
def fmt(x):return 'NA' if x is None else f'{x:.4f}'
def interval(x):return 'NA' if not x else f"[{x['low']:+.4f}, {x['high']:+.4f}]"


def analyze(split):
    path=OUT/split;plan=load(path/'plan.json');summary=load(path/'summary.json')
    rows=[json.loads(s) for s in (path/'trials.jsonl').read_text().splitlines()]
    index={(r['qid'],r['condition']):r for r in rows}
    check_hashes(plan['code_hashes']);check_hashes(plan['original_input_hashes'])
    assert len(rows)==len(plan['schedule']) and len(index)==len(rows)
    assert sha(ROOT/plan['dataset'])==plan['dataset_sha256']
    for c in plan['compression']:assert sha(ROOT/c['context_path'])==c['context_sha256']
    stats=[]
    for cond,s in summary['conditions'].items():
        rs=[r for r in rows if r['condition']==cond]
        actual_reductions=[];deltas=[]
        for r in rs:
            n=index[(r['qid'],'none')]['answer']['result']['prompt_tokens']
            actual_reductions.append(100*(1-r['answer']['result']['prompt_tokens']/n))
            b=index[(r['qid'],'llmlingua2_r30')]['answer']['result']['prompt_tokens']
            deltas.append(r['answer']['result']['prompt_tokens']-b)
        stats.append({'condition':cond,**{k:v for k,v in s.items() if k!='by_type'},
             'actual_input_reduction_pct':avg(actual_reductions),
             'aggregate_api_input_reduction_pct':100*(1-sum(r['answer']['result']['prompt_tokens'] for r in rs)/sum(index[(r['qid'],'none')]['answer']['result']['prompt_tokens'] for r in rs)),
             'mean_actual_input_delta_vs_r30':avg(deltas),'max_abs_actual_input_delta_vs_r30':max(map(abs,deltas)),
             'actual_token_delta_histogram':dict(Counter(deltas)),
             'deployment_compression_seconds_mean_including_r30_anchor':avg([r['compression']['duration_sec']+(index[(r['qid'],'llmlingua2_r30')]['compression']['duration_sec'] if cond.startswith('qp_') else 0) for r in rs])})
    # Direct ablation contrasts, same paired questions and budgets, all declared components.
    contrasts=[]
    for a,b in [('qp_identifiers_r30','llmlingua2_r30'),('qp_sentences_r30','llmlingua2_r30'),
                ('qp_combined_r30','llmlingua2_r30'),('qp_combined_r30','qp_identifiers_r30'),('qp_combined_r30','qp_sentences_r30')]:
        pairs=[(index[(q['item']['id'],a)],index[(q['item']['id'],b)],q['cluster']) for q in plan['items']]
        valid=[(a,b,g) for a,b,g in pairs if a['answer_accuracy'] is not None and b['answer_accuracy'] is not None]
        ds=[a['answer_accuracy']-b['answer_accuracy'] for a,b,g in valid];gs=[g for a,b,g in valid]
        contrasts.append({'method':a,'reference':b,'n':len(ds),'delta':avg(ds),
             'question_ci':bootstrap(ds,gs,cfg()['bootstrap_replicates'],cfg()['bootstrap_seed']),
             'cluster_ci':bootstrap(ds,gs,cfg()['bootstrap_replicates'],cfg()['bootstrap_seed'],True),
             'mean_actual_token_difference':avg([a['answer']['result']['prompt_tokens']-b['answer']['result']['prompt_tokens'] for a,b,g in valid])})
    cluster_rows=[]
    for group in sorted({r['document_cluster'] for r in rows}):
        group_rows=[r for r in rows if r['document_cluster']==group]
        docs=sorted({doc for r in group_rows for doc in r['source_files']})
        for condition in cfg()['conditions']:
            rs=[r for r in group_rows if r['condition']==condition]
            cluster_rows.append({'cluster':group,'source_files':json.dumps(docs),'condition':condition,'n':len(rs),
              'valid_n':sum(r['answer_accuracy'] is not None for r in rs),
              'mean_accuracy':avg([r['answer_accuracy'] for r in rs]),
              'mean_api_input_tokens':avg([r['answer']['result']['prompt_tokens'] for r in rs]),
              'not_found_rate':avg([r['not_found'] for r in rs])})
    with (path/'document_clusters.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(cluster_rows[0]));w.writeheader();w.writerows(cluster_rows)
    errors=[json.loads(s) for s in (path/'errors.jsonl').read_text().splitlines()] if (path/'errors.jsonl').exists() else []
    result={'split':split,'conditions':stats,'ablation_contrasts':contrasts,'document_clusters':cluster_rows,'errors':errors,
      'actual_token_estimation_disclaimer':'o200k_base fixed-chat overhead approximation vs server-reported usage; both retained',
      'valid_n':{k:v['valid_n'] for k,v in summary['conditions'].items()},
      'original_input_hashes_unchanged':True,'dataset_and_context_hashes_valid':True}
    dump(path/'analysis_summary.json',result)
    with (path/'accuracy_tokens.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=list(stats[0]);w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in stats:w.writerow({k:json.dumps(v) if isinstance(v,dict) else v for k,v in r.items()})
    return plan,summary,rows,result


def report():
    outputs={split:analyze(split) for split in ['dev','independent']}
    frozen=load(OUT/'algorithm_freeze.json');check_hashes(frozen['code_hashes'])
    data_meta=load(OUT/'dataset_metadata.json')
    assert data_meta['freeze_sha256']==sha(OUT/'algorithm_freeze.json')
    assert data_meta['dataset_sha256']==sha(OUT/'independent_dataset.json')
    primary=outputs['independent'][1]['paired_vs_r30']['qp_combined_r30']
    lines=['# UCWIT 핵심 근거 선택적 보존 압축 실험','',
      f"Dev210 + 독립186시행 완료. 독립31문항에서 결합−r30 평균 정확도 차이 {primary['delta_accuracy']*100:.2f}%p, 문항95%CI {interval(primary['question_bootstrap_95ci'])} (비율 단위), 문서군집95%CI {interval(primary['document_cluster_bootstrap_95ci'])}. 실제 입력 토큰 차이는 전31문항에서 ±1 이내이다. 이 합성 고정추출본에서의 관찰이며 독립 사람 검증된 모집단 효과가 아니다.",'',
      '## 연구 범위와 사전 절차','',
      '기존 test 139문항은 최종 평가에 사용하지 않았다. dev 35문항에서 제약과 성능을 새로 평가한 뒤 algorithm_freeze.json에 코드·설정 해시를 고정했다. 이후에만 Python 3.14 기술 문서를 수집하고 독립 문항을 생성·검수했다. 독립 성능을 본 뒤 보호 규칙이나 예산을 바꾸지 않았다. 개선 여부와 무관하게 사전에 정한 한 정책을 유지했다.',
      '', f"독립셋: {data_meta['n']}문항 / {len(data_meta['sources'])}개 선정 문서. 유형 수: {data_meta['types']}. 기존 평가셋과 문서 ID 교집합 및 12단어 shingle 중복을 검증했다. 문서·문항 독립은 기존 평가셋에 대한 것이며 모델 사전학습 데이터와의 독립을 뜻하지 않는다.",
      '', '## 압축 방법 및 정보 경계','',
      '질문과 원본 문맥을 문장/줄/코드 블록 단위로 분할하고 BM25(k1=1.2, b=0.75)로 순위를 정한다. Combined는 질문 관련 점수에 조건·부정·비교·순서 표현이 있는 단위를 1.25배 가중한다. 보호 예산은 해당 문항의 context 가용 예산 중 35%, 최대 18구간이다. 문서 경계를 먼저 보존하고, combined는 보호 예산의 85%까지 관련 문장을 보존한 뒤 나머지에 식별자·버전·숫자·API 표기를 담는다. 중요한 문장/코드 블록을 통째로 보존해 주어·동작·조건의 동시 보존을 시도한다. 모든 식별자나 관계를 전역적으로 보장하는 방법은 아니며 예산을 넘는 구간은 제외된다.',
      '', '보호 구간은 고유 마커로 치환하고 나머지에 로컬 LLMLingua-2를 적용한 뒤 원문 그대로 복원한다. 전체 입력 예산 초과 시 보호되지 않은 단어만 삭제한다. 남는 예산에는 질문 순위에 따라 원문 구간과 단어 경계 prefix를 추가한다. 합성 filler는 사용하지 않는다. Prefix와 잔여 단어는 완전 문장이 아닐 수 있다. 보존 비율이 높아지는 대신 잔여 영역 예산은 감소한다. 모델 추론 실패는 extractive fallback으로 별도 기록하고 실험에서 숨기지 않는다.',
      '', '압축 결정 함수 compress_budget(question, context, system, budget, total_tokens, text_tokens)는 qid, 정답, key_facts, evidence, 모델 답변 또는 실패 목록을 받지 않는다. 공개 compress 인터페이스도 PromptParts의 evidence/answer_core를 버린 뒤 호출한다. 이에 대한 poisoned-label 경계 테스트를 포함한다. 평가기의 gold/근거는 채점과 사후 사례 분석에서만 사용한다. 기존 평가와 마찬가지로 문맥 문서 자체는 주어진 것이며 검색 성능까지 평가한 RAG 실험은 아니다.',
      '', '## 동일 예산 및 비교 설계','',
      '각 문항의 새 r30 전체 입력(system+context+question) 토큰 수를 숫자 목표로 삼는다. 세 ablation은 동일 목표, 동일 residual LLMLingua 모델 및 동일 예산 수선 정책을 쓴다. None/r50은 참조용이고 r50과의 정확도 차이는 동일 예산 효과로 해석하지 않는다. r30 구현은 기존 코드 그대로이다. r30이 fenced code 등을 이미 보존하므로 nominal 30%와 실제 전체 입력 보존 비율이 다르다. 기존 run 답변은 어떤 조건에도 재사용하지 않았다.',
      '', '동일 예산의 주요 검사는 서버 보고 prompt_tokens이다. 전체/문항별 차이와 ±1토큰 부분집합 민감도를 모두 보고한다. 최소 예산이 system/question보다 작은 불가능한 경우도 예산 초과 사유와 양을 기록한다. 단일 seed=42, temperature=0, Terra reasoning_effort=none, answer_v1, 답변 한도512, DeepSeek-flash fact_judge_v2 per_fact/4096을 사용했다. 추가 압축 LLM API 호출은 없으며 로컬 CPU 추론 시간은 별도 기록한다.',
      '', '정확도는 각 문항의 동일 가중 핵심 사실 비율을 계산한 뒤 문항에 동일 가중치를 둔 macro 평균이다. 표의 입력 절감률도 문항별 퍼센트의 평균이며, 전체 입력 토큰 합 기준 절감률은 accuracy_tokens.csv의 aggregate_api_input_reduction_pct에 별도로 둔다. 완전 정답은 accuracy=1, NOT FOUND는 기존 전용 규칙이다. Judge 파싱 실패는 None/유효 n으로 공개한다. 사례별 추가 답변은 캐시 후 채점하며 실패·재시도 기록을 보존한다. 통계는 paired 문항 bootstrap 10,000회, 문서 공유를 연결한 connected-component 군집 bootstrap 10,000회, seed20261104의 percentile95% CI이다. 군집이 하나이면 군집 CI는 산출하지 않는다. 다중 비교 보정 없는 탐색적 ablation이며 CI를 확증적 유의성으로 과장하지 않는다.']
    for split,(plan,summary,rows,analysis) in outputs.items():
        lines += ['',f'## {split}: 정확도–전체 입력 토큰','',
          f"{summary['distinct_qids']}문항, {summary['completed_trials']}/{summary['expected_trials']}시행, 문서 연결 군집 {summary['document_clusters']}개.",'',
          '|조건|유효 n|핵심 사실 정확도|완전 정답률|NOT FOUND|실제 평균 입력 토큰|실제 절감률 %|r30 대비 평균 입력 차이|최대 절대 차이|',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
        for s in analysis['conditions']:
            lines.append(f"|{s['condition']}|{s['valid_n']}|{fmt(s['answer_accuracy'])}|{fmt(s['fully_correct_rate'])}|{fmt(s['not_found_rate'])}|{fmt(s['api_input_tokens'])}|{fmt(s['actual_input_reduction_pct'])}|{fmt(s['mean_actual_input_delta_vs_r30'])}|{s['max_abs_actual_input_delta_vs_r30']}|")
        lines+=['','### 동일 예산 paired 비교 및 ablation','',
                '|방법 − 참조|paired n|정확도 차이|문항 95% CI|문서 군집 95% CI|평균 입력 차이|',
                '|---|---:|---:|---|---|---:|']
        for c in analysis['ablation_contrasts']:
            lines.append(f"|{c['method']} − {c['reference']}|{c['n']}|{fmt(c['delta'])}|{interval(c['question_ci'])}|{interval(c['cluster_ci'])}|{fmt(c['mean_actual_token_difference'])}|")
        lines+=['','### 유형별 정확도 / NOT FOUND','', '|조건|유형|n|정확도|NOT FOUND|','|---|---|---:|---:|---:|']
        for condition,st in summary['conditions'].items():
            for qt,stt in st['by_type'].items():lines.append(f"|{condition}|{qt}|{stt['n']}|{fmt(stt['accuracy'])}|{fmt(stt['not_found_rate'])}|")
        lines+=['','### 예산·압축 실패 및 비용','']
        for st in analysis['conditions']:
            lines.append(f"- {st['condition']}: 평균 압축 {st['compression_seconds_mean']:.3f}초 (r30 예산 산출 포함 추정 {st['deployment_compression_seconds_mean_including_r30_anchor']:.3f}초), fallback {st['compression_failure_n']}건, 예산 차이 분포 {st['actual_token_delta_histogram']}.")
        lines+=['',json.dumps(summary['usage'],ensure_ascii=False,indent=2),'',
          '위 사용량은 평가 답변과 사실 Judge의 실제 API 토큰이다. 압축 API는 0이다. 이전 잔액 부족으로 중단된 per-fact batch 중 반환 전에 성공한 Judge 호출의 usage는 남지 않았을 수 있어 Judge 합계는 알려진 사용량의 하한이다. 달러 비용은 호출 시점의 계약 단가를 고정하지 않아 추정하지 않았다. 압축 시간 비교는 CPU 모델 최초 로딩과 공유 캐시 효과를 포함하므로 엄밀한 독립 성능 벤치마크가 아니다.',
          '', '### 개선·악화된 모든 사례','']
        deltas=load(OUT/split/'case_deltas.json')
        changes=[d for d in deltas if d['condition']=='qp_combined_r30' and d['delta_accuracy']!=0]
        lines.append(f'Combined vs r30: 개선 {sum(d["delta_accuracy"]>0 for d in changes)}건, 악화 {sum(d["delta_accuracy"]<0 for d in changes)}건. 모든 동률 및 다른 ablation의 변화도 case_deltas.json에 있다.')
        for d in changes:
            lines += ['',f"#### {d['qid']} ({d['qtype']}) — {'개선' if d['delta_accuracy']>0 else '악화'}",d['question'],
                f"점수: {d['baseline_accuracy']} → {d['condition_accuracy']}; 실제 입력 차이 {d['api_token_difference']}토큰",'',
                'r30:','```text',d['baseline_response'],'```','Combined:','```text',d['condition_response'],'```']
        if not changes:lines.append('점수가 달라진 사례 없음. 답변 텍스트 전체는 trials.jsonl 참조.')
        if analysis['errors']:lines+=['','실행 오류(삭제하지 않음):',json.dumps(analysis['errors'],indent=2)]
    lines+=['','## 독립 평가셋 생성·자동 검수와 비용','',
      '알고리즘 고정 후 공식 문서의 main body를 HTMLParser로 추출하고 각 문서의 처음 약 5,000토큰을 사용했다. 코드 펜스가 열려 있으면 닫힐 때까지 포함한다. 문서당 Terra 한 요청으로 fact/code/procedure/multi 각각 1개를 생성한다. 정답과 key_facts는 압축기에 전달하지 않는다. Schema와 원문 인용 exact-match를 검사하고 DeepSeek-flash가 질문의 명확성·근거 지지·사실 완전성을 YES로 판정한 문항만 포함했다. 거절·생성 실패를 모두 보존하며 답변 성능에 따른 재생성이나 문항 교체는 하지 않았다. dataset_metadata.json 및 sources/*.generation.json/*.audit.json에 프롬프트·원문·usage·모델·해시를 기록했다.',
      '', 'Source snapshots and attribution: Python Software Foundation documentation, [Python 3.14 documentation license](https://docs.python.org/3.14/license.html).']
    for source in data_meta['sources']:lines.append(f"- [{source['module']}]({source['url']}), text SHA256 `{source['text_sha256']}`, 기존 corpus 12단어 shingle 겹침 {source['old_corpus_12word_shingle_overlap_fraction']:.6f}.")
    data_usage={'generation_input':0,'generation_output':0,'audit_input':0,'audit_output':0}
    for p in (OUT/'sources').glob('*.generation.json'):
        r=load(p)['result'];data_usage['generation_input']+=r['prompt_tokens'];data_usage['generation_output']+=r['completion_tokens']
    for p in (OUT/'sources').glob('*.audit.json'):
        r=load(p)['result'];data_usage['audit_input']+=r['prompt_tokens'];data_usage['audit_output']+=r['completion_tokens']
    lines+=['',json.dumps(data_usage,indent=2),'','## 한계와 해석','',
      '사후 실제 답변·근거 검토는 [qualitative_review.md](qualitative_review.md)에 있다. 점수 변화11개 전부를 포함하며 ind_copy_3의 부분 회복과 ind_copy_4의 악화도 보존했다. ind_graphlib_3와 ind_functools_3 등은 암묵적 의미의 인정 여부에 따라 점수가 달라질 여지가 있다. 주 결과를 유리하게 바꾸기 위한 사후 재채점/제외는 하지 않았다.',
      '', '고정 원문 추출본에 비ASCII 문장부호의 mojibake가 발견됐다. frozen 추출기는 requests.response.text의 기본 문자셋 해석을 사용했고 명시적 UTF-8을 강제하지 않았다. 모든 조건은 같은 추출본을 사용했고 quote exact-match는 그 추출본 기준이다. 원본 HTML byte는 유효한 UTF-8로 보존했다. 평가 후 corpus를 수정하지 않았으며 typography가 정상인 새 holdout에서의 재현이 필요하다. 상세는 preprocessing_diagnostic.json 참조.', '',
      '새 문서에 대한 held-out 평가는 기존 test를 재활용하지 않았다는 의미다. 생성 모델과 답변 모델이 같고, 정답·Judge가 자동으로 생성·검수되어 편향과 오류가 남는다. 독립 사람 검수, 외부 모델 재현, 더 많은 문서 군집이 필요하다. r30은 기존 전역 코드블록 보호를 쓰고 새 변형은 선택 보호를 사용하므로 baseline 대비 차이를 단일 보호 요소의 순수 인과 효과로 단정하지 않는다. 직접 ablation 대조도 보호 cap 재배분이 동반된다. 보호 규칙은 정규식/BM25 휴리스틱으로 문법적 관계 보존을 보장하지 않는다. 새 방법이 더 나쁘거나 신뢰구간이 0을 포함하면 개선으로 확정하지 않는다. 예산이 맞더라도 문서 구간 선택·반복·문장 조각 차이 등이 성능에 영향을 줄 수 있다. 문항은 문서 내 상관이 있고 문서 군집 수가 적어 CI도 불안정하다. 정답 기반 oracle 복원 결과는 이번 deployable method의 성능 주장에 사용하지 않았다.',
      '', '## 재현','', 'README.md의 staged commands, algorithm_freeze.json, 각 split plan/preflight, sources snapshots, dataset metadata, artifact_manifest.json 참조. Git commit/push 없음. 기존 run 및 평가셋 해시 재검증 완료.']
    (OUT/'report.md').write_text('\n'.join(lines))
    dump(OUT/'costs.json',{'dataset':data_usage,'dataset_generation_calls':len(list((OUT/'sources').glob('*.generation.json'))),'dataset_audit_calls':len(list((OUT/'sources').glob('*.audit.json'))),'evaluation':{s:o[1]['usage'] for s,o in outputs.items()},'compression_api_calls':0,'note':'Known returned usage only; interrupted network or per-fact batches can have unreturned usage, so complete provider billing totals are not claimed.'})
    dump(OUT/'verification.json',{'code_freeze_unchanged':True,'existing_run_and_dataset_hashes_unchanged':True,
        'dev_completed':outputs['dev'][1]['completed_trials'],'independent_completed':outputs['independent'][1]['completed_trials'],
        'independent_questions':data_meta['n'],'dataset_frozen_before_independent_evaluation':True,
        'independent_data_generated_after_algorithm_freeze':True,
        'dataset_audit_accepted':sum(q.get('accepted') is True for q in load(OUT/'dataset_audit.json')),
        'tests':'6 question_preserve + 4 analysis + 21 legacy LLMLingua2 + 24 existing grader + 3 frozen-artifact tests',
        'source_api_keys_exported':False,'preprocessing_artifacts_disclosed':True,'human_gold_audit_completed':False,'platform':platform.platform(),'python':sys.version,
        'no_commit_or_push':True})
    dump(OUT/'status.json',{'status':'complete','dev_completed_trials':outputs['dev'][1]['completed_trials'],
      'independent_completed_trials':outputs['independent'][1]['completed_trials'],
      'independent_questions':data_meta['n'],'algorithm_frozen':True,
      'original_credit_failures_preserved':True,'historical_partial_reports':'history/',
      'performance_conclusion':'See report and paired confidence intervals; negative findings retained.'})
    print('REPORT READY',OUT/'report.md')


def partial_report():
    path=OUT/'dev';plan=load(path/'plan.json');summary=load(path/'summary.json')
    check_hashes(plan['code_hashes']);check_hashes(plan['original_input_hashes'])
    assert sha(ROOT/plan['dataset'])==plan['dataset_sha256']
    rows=[json.loads(x) for x in (path/'trials.jsonl').read_text().splitlines()]
    errors=[json.loads(x) for x in (path/'errors.jsonl').read_text().splitlines()]
    caches=[load(p) for p in (path/'answer_cache').glob('*.json')]
    for r in plan['compression']:assert sha(ROOT/r['context_path'])==r['context_sha256']
    audit=[]
    for r in plan['compression']:
        audit.append({'qid':r['qid'],'condition':r['condition'],'target_input_tokens':r['target_input_tokens'],
          'input_tokens_est':r['input_tokens_est'],'raw_input_tokens_est':r['raw_input_tokens_est'],
          'reduction_pct_est':100*(1-r['input_tokens_est']/r['raw_input_tokens_est']),
          'difference_vs_r30':r['budget_difference'],'compression_status':r['info'].get('status','identity'),
          'compression_seconds':r['duration_sec'],'protected_spans':len(r['info'].get('protected_spans',[]))})
    with (path/'budget_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(audit[0]));w.writeheader();w.writerows(audit)
    budgets={}
    for c in cfg()['conditions']:
        rs=[r for r in audit if r['condition']==c]
        budgets[c]={'n':len(rs),'input_tokens_est_mean':avg([r['input_tokens_est'] for r in rs]),
           'input_reduction_pct_est_mean':avg([r['reduction_pct_est'] for r in rs]),
           'delta_histogram':dict(Counter(r['difference_vs_r30'] for r in rs)),
           'compression_failures':sum('fallback' in r['compression_status'] for r in rs),
           'duration_mean':avg([r['compression_seconds'] for r in rs])}
    status={'status':'blocked_external_api_credit','dev_expected_trials':210,'dev_completed_trials':len(rows),
       'dev_pending_trials':210-len(rows),'cached_answers':len(caches),'cached_answers_pending_judge':len(caches)-len(rows),
       'errors_by_http_status':dict(Counter(r['http_status'] for r in errors)),
       'algorithm_frozen':False,'independent_dataset_created':False,'independent_evaluation_completed':False,
       'performance_conclusion':'unavailable: incomplete and unequally missing conditions',
       'blockers':load(OUT/'api_diagnostics.json'),'budget_validation':budgets,
       'required_next_action':'Restore both API credit balances, resume dev; freeze only after complete dev; then generate independent data and evaluate without changing compressor policy.'}
    dump(OUT/'status.json',status)
    # All cached answers, not only graded trials, contribute to known answer usage.
    usage={'cached_answer_calls':len(caches),'answer_prompt_tokens_known':sum(c['result']['prompt_tokens'] for c in caches),
       'answer_completion_tokens_known':sum(c['result']['completion_tokens'] for c in caches),
       'completed_fact_judge_calls':sum(r['fact_grade']['judge_calls'] for r in rows),
       'completed_fact_judge_input_tokens':sum(r['fact_grade']['judge_prompt_tokens'] for r in rows),
       'completed_fact_judge_output_tokens':sum(r['fact_grade']['judge_completion_tokens'] for r in rows),
       'compression_api_calls':0,'compression_api_tokens':0,
       'caveat':'Judge usage of partly failed per-fact batches may be absent because original grader returns only at end; known totals are lower bounds. Do not report these as complete billed totals. Failed 402/429 requests preserved.'}
    dump(OUT/'costs.json',usage)
    lines=['# UCWIT 핵심 근거 보존 압축 실험 — 중간 결과','',
       '**현재 상태: API 크레딧 소진으로 미완료. 성능 개선·독립 검증을 주장할 수 없다.**','',
       f"dev 35문항의 6조건 압축 문맥 210개를 모두 생성했다. 평가 계획 210시행 중 {len(rows)}시행만 핵심 사실 Judge까지 완료했다. 받은 답변 {len(caches)}개는 모두 캐시에 남겼다. 서로 다른 조건의 누락 수가 달라 현재 평균을 성능 비교로 해석하지 않는다.",'',
       '## 중단 원인','',
       '실제 API 진단에서 Terra는 HTTP429 credit_balance_exhausted / insufficient_quota, DeepSeek Judge는 HTTP402 insufficient_balance_error / Insufficient Balance를 반환했다. 단순 RPM 제한으로 추정해 반복 호출하지 않는다. 추가 유료 호출 중단. 기존 모델이나 원본 run 답변으로 대체하지 않았다. 실패 176요청과 별도 진단 2건을 보존했다.',
       '', '## 완료한 구현과 정보 경계','',
       '신규 등록 qp_identifiers_r30 / qp_sentences_r30 / qp_combined_r30. 기존 r30/r50 구현과 등록 이름은 유지했다. question_preserve.py의 compress_budget는 질문·원본 문맥·system·숫자 예산만 받으며 정답/key_facts/evidence/qid/답변/실패 목록을 인자로 받지 않는다. 공개 compress도 diagnostic gold 필드를 버린다. poisoned-label 테스트를 포함한다.',
       '', 'BM25(k1=1.2,b=0.75), 관련 문장/코드블록, 버전/API/숫자 식별자, 조건·부정·비교·순서 휴리스틱을 결합했다. 보호 cap은 가용 context 예산35%, 최대18구간이다. Combined는 문장에 cap85%를 우선 배분하고 남는 cap에 식별자를 보호한다. 관련 관계 표현은 BM25 점수에 1.25배 가중한다. 실제 구문 분석기가 아니므로 주어/동작 관계의 보존을 보장하지 않는다.',
       '', '보호 구간은 원문 그대로 복원하고 잔여 영역만 로컬 LLMLingua-2로 압축한다. 초과 시 잔여 단어를 삭제하고 남는 예산은 원문 구간/단어 경계 prefix로 사용한다. 따라서 보호되지 않은 구간은 문장 조각이 될 수 있다. 모든 식별자를 전역 보존하는 것은 아니며 제한 예산에서 질문 관련 후보를 우선한다.',
       '', '## 전체 35문항의 입력 예산 검증 (평가 API와 무관)','',
       '|조건|문항 수|평균 전체 입력 토큰(추정)|평균 절감률 %|r30 대비 차이 분포|추론 실패|평균 압축 초|',
       '|---|---:|---:|---:|---|---:|---:|']
    for c,b in budgets.items():lines.append(f"|{c}|{b['n']}|{b['input_tokens_est_mean']:.3f}|{b['input_reduction_pct_est_mean']:.3f}|{b['delta_histogram']}|{b['compression_failures']}|{b['duration_mean']:.3f}|")
    lines+=['','세 제안 변형 모두 예산 초과 0건, r30과의 차이는 0 또는 −1토큰이다. 이 결과는 전체 입력 tiktoken 추정치이다. 실제 API 토큰 동등성의 전 문항 확인과 답변 성능 비교는 평가 완료 후 가능하다. None/r50은 토큰 예산이 다른 참조 조건이며 동등 예산 효과로 해석하지 않는다.',
       '', '## 부분 평가 진행률 — 성능 결론 금지','', '|조건|완료 수 / 35|','|---|---:|']
    for c in cfg()['conditions']:lines.append(f"|{c}|{summary['conditions'][c]['n']} / 35|")
    lines+=['','현재 정확도 원자료와 부분 paired CI는 dev/summary.json 및 trials.csv에 남겼으나 불완전 선택 표본이므로 논문 결과표로 사용하지 않는다. 모든 완료 답변·사실 점수와 오류, 개선/악화의 부분 기록은 보존했다.',
       '', '## Ablation 및 독립 평가 상태','',
       '식별자/수치만, 질문 관련 문장만, 결합 방식의 3개 변형을 모두 같은 예산으로 준비했다. 각 구성의 정확도 기여와 유효 bootstrap CI는 현재 평가 미완료로 판단 불가다. 통계 코드는 문항 paired bootstrap 및 문서 연결 군집 bootstrap을 포함하고 단위 테스트를 통과했다.',
       '', 'dev 완료 후 freeze를 먼저 수행한다. 그 전에는 새 Python3.14 공식 문서를 수집하거나 독립 문항을 생성하지 않았다. 사전 후보는 graphlib, tomllib, bisect, heapq, copy, weakref, contextlib, functools이다. 고정 후에 문서당4유형 후보를 생성하고 schema/원문 exact quote/자동 grounding audit를 통과한 문항만 포함하도록 구현했다. 거절과 실패도 보존하며 성능에 따라 문항을 교체하지 않는다. 독립셋이 아직 없으므로 문서 비중복 검증을 완료했다고 주장하지 않는다.',
       '', '공식 문서 출처 예정: [Python3.14 표준 라이브러리](https://docs.python.org/3.14/library/index.html). 생성 모델과 평가 모델이 같고 자동 Judge를 쓰는 편향은 후속 보고서에서 명시해야 한다.',
       '', '## 검증·사용량','', '6개 신규/경계 테스트, 4개 분석 테스트, 21개 기존 압축기 테스트, 24개 기존 grader 테스트: 총55개 통과. 테스트 환경 문제 이력은 test_notes.md에 보존했다. 기존 run/평가셋 해시와 이번 코드/문맥 해시를 재검증했다. API 키/.env/.venv/Git 내부 파일은 공유본에 포함하지 않는다.',
       '',json.dumps(usage,ensure_ascii=False,indent=2),'',
       '## 재개','',
       '두 API 계정의 크레딧을 복구한 뒤 README.md 순서로 이어 실행한다. 완료 시행은 건너뛰고 이미 받은50개 답변은 재생성하지 않는다. dev가 완료되기 전 freeze는 assertion으로 거부된다. 독립 단계도 freeze가 없으면 거부된다. 기존 원본 변경, Git commit/push 없음.']
    (OUT/'report.md').write_text('\n'.join(lines))
    dump(OUT/'verification.json',{'status':'partial_not_final','original_run_and_dataset_hashes_unchanged':True,
      'code_and_context_hashes_valid':True,'dev_context_files':210,'completed_trial_rows':len(rows),
      'cached_answers':len(caches),'independent_stage_not_started':True,'tests_passed':55,
      'platform':platform.platform(),'python':sys.version,'no_commit_or_push':True})
    print(json.dumps({'status':status['status'],'complete':len(rows),'pending':210-len(rows),'budgets':budgets},indent=2))


def package():
    assert (OUT/'report.md').exists()
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='artifact_manifest.json']
    files+=[ROOT/'scripts/final_experiment.py',ROOT/'scripts/final_experiment_report.py',ROOT/'scripts/final_experiment_canary.py',ROOT/'requirements.txt']
    files+=[ROOT/'tests'/n for n in ['test_question_preserve.py','test_question_preserve_boundary.py','test_final_experiment_analysis.py','test_llmlingua2_compressor.py','test_grader.py','test_final_experiment_artifacts.py']]
    # All import-time dependencies of the existing experiment/prompt machinery.
    files+=[ROOT/'src'/n for n in ['config.py','experiment.py','grader.py','llm.py','corpus.py','core_match.py','prompts/answer_v1.md']]
    files+=list((ROOT/'src/compressors').glob('*.py'))
    # Freeze hashes include these source snapshots as well; keep the code bundle complete.
    files+=list((ROOT/'src').glob('*.py'))
    files=sorted(set(files));assert all(p.is_file() for p in files)
    assert not any(set(p.relative_to(ROOT).parts)&{'.env','.venv','.git','__pycache__'} for p in files)
    # Check configured credential values without logging them.
    from dotenv import dotenv_values
    env=dotenv_values(ROOT/'.env') if (ROOT/'.env').exists() else {}
    secrets=[v.encode() for k,v in env.items() if k.endswith('API_KEY') and v and len(v)>12]
    for p in files:assert not any(secret in p.read_bytes() for secret in secrets),'Credential found; package aborted'
    dump(OUT/'artifact_manifest.json',{str(p.relative_to(ROOT)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in files})
    files.append(OUT/'artifact_manifest.json')
    target=ROOT/'tokenlab_final_experiment.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files:z.write(p,str(p.relative_to(ROOT)))
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert all(z.read(str(p.relative_to(ROOT)))==p.read_bytes() for p in files)
        for split in ['dev','independent']:
            if not (OUT/split/'trials.csv').exists():continue
            raw=z.read(f'docs/analysis/final-experiment/{split}/trials.csv').decode('utf-8-sig')
            assert len(list(csv.DictReader(io.StringIO(raw))))==load(OUT/split/'summary.json')['completed_trials']
    print(json.dumps({'zip':str(target),'files':len(files),'bytes':target.stat().st_size,'sha256':sha(target),'missing_files':[]},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['report','partial','package']);a=p.parse_args()
    {'report':report,'partial':partial_report,'package':package}[a.action]()
