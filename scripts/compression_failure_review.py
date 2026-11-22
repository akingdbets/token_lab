"""Offline paired compression review builder; standard library only."""
import argparse
import csv
import hashlib
import json
import math
import random
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = ('llmlingua2_r50', 'llmlingua2_r30')
HUMAN = ('evidence_deleted', 'relation_damaged', 'evidence_sufficient',
         'judge_or_gold_issue', 'primary_cause', 'confidence', 'memo')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fingerprint(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def load_run(path):
    summary = read_json(path / 'summary.json')
    rows = [json.loads(line) for line in (path / 'trials.jsonl').read_text().splitlines() if line.strip()]
    return summary, rows


def complete(summary, rows):
    counts = Counter(r['compressor'] for r in rows)
    keys = [(r['qid'], r['compressor']) for r in rows]
    return (len(keys) == len(set(keys)) and all(
        counts[c] == v['n'] == summary['config']['n_items']
        for c, v in summary['results'].items()))


def latest_test(runs):
    for path in sorted(runs.iterdir(), reverse=True):
        if not (path / 'summary.json').exists() or not (path / 'trials.jsonl').exists():
            continue
        s, rows = load_run(path)
        if (s['config'].get('split') == 'test' and
                s['config'].get('models', {}).get('answer', {}).get('model') == 'gpt-6.1-terra'
                and complete(s, rows)):
            return path
    raise ValueError('No completed Terra test run')


def locate(quote, context):
    """Exact offsets are evidence; approximate offsets are navigation candidates only."""
    if context is None or not quote:
        return {'status': 'unavailable', 'exact_offsets': []}
    offsets = [m.start() for m in re.finditer(re.escape(quote), context)]
    if offsets:
        return {'status': 'exact', 'exact_offsets': offsets, 'length': len(quote)}
    match = SequenceMatcher(None, quote, context, autojunk=False).find_longest_match()
    start = max(0, match.b - match.a)
    return {'status': 'candidate_unverified', 'exact_offsets': [],
            'candidate_offset': start, 'matched_characters': match.size,
            'candidate_surrounding': context[max(0, start - 180):start + len(quote) + 180]}


def build(run, dataset, sample, seed):
    summary, rows = load_run(run)
    issues, sources = [], []
    index = defaultdict(list)
    for r in rows:
        index[(r['qid'], r['compressor'])].append(r)
    questions = defaultdict(list)
    for q in read_json(dataset):
        questions[q['id']].append(q)
    groups = defaultdict(Counter)
    failures, successes = [], defaultdict(list)
    for (qid, compressor), items in sorted(index.items()):
        if compressor not in CONDITIONS:
            continue
        base = index.get((qid, 'none'), [])
        if len(items) != 1 or len(base) != 1:
            issues.append({'qid': qid, 'compressor': compressor, 'error': 'missing/ambiguous paired trial'})
            continue
        row, none = items[0], base[0]
        scores = [none.get('answer_accuracy'), row.get('answer_accuracy')]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in scores):
            issues.append({'qid': qid, 'compressor': compressor, 'error': 'invalid accuracy'})
            continue
        group = groups[(row['qtype'], compressor)]
        group['paired'] += 1
        cohort = 'decline' if scores[1] < scores[0] else ('success' if scores[1] == 1 else 'other_non_decline')
        group[cohort] += 1
        record = {'trial_id': f'{run.name}/{qid}/{compressor}', 'qid': qid,
                  'type': row['qtype'], 'compressor': compressor, 'cohort': cohort,
                  'none_trial': none, 'compressed_trial': row, 'join_errors': []}
        qs = questions.get(qid, [])
        if len(qs) != 1:
            record['join_errors'].append('missing/ambiguous dataset qid')
            q = {}
        else:
            q = qs[0]
            for field, qfield in [('question', 'question'), ('answer', 'answer'), ('qtype', 'type')]:
                if row.get(field) != q.get(qfield) or none.get(field) != q.get(qfield):
                    record['join_errors'].append(f'dataset/trial mismatch: {field}')
        record['dataset_item'] = q
        for condition, name in [('none', 'original_context'), (compressor, 'compressed_context')]:
            path = run / 'contexts' / f'{qid}.{condition}.md'
            if path.exists():
                record[name] = path.read_text(encoding='utf-8')
                sources.append(fingerprint(path))
            else:
                record[name] = None
                record['join_errors'].append(f'missing context: {path}')
        record['evidence'] = [{**e, 'original_location': locate(e.get('quote', ''), record['original_context']),
                               'compressed_location': locate(e.get('quote', ''), record['compressed_context'])}
                              for e in q.get('evidence', [])]
        if not q.get('key_facts') or not q.get('evidence'):
            record['join_errors'].append('missing key_facts/evidence')
        for e in record['evidence']:
            if e['original_location']['status'] != 'exact':
                record['join_errors'].append(f'original quote not exactly located: {e.get("page")}')
        if record['join_errors']:
            issues.append({'trial_id': record['trial_id'], 'errors': record['join_errors']})
        if cohort == 'decline':
            failures.append(record)
        elif cohort == 'success':
            successes[(row['qtype'], compressor)].append(record)
    rng = random.Random(seed)
    selected = list(failures)
    denominators = []
    for key, counts in sorted(groups.items()):
        pool = successes[key]
        chosen = rng.sample(pool, min(sample, len(pool)))
        selected.extend(chosen)
        denominators.append({'type': key[0], 'compressor': key[1], **counts,
                             'sampled_success': len(chosen), 'success_sampling_fraction': len(chosen)/len(pool) if pool else 0})
    return selected, denominators, issues, sources


def review_rows(records):
    for r in records:
        facts = r['dataset_item'].get('key_facts') or [None]
        for i, fact in enumerate(facts):
            yield {'review_id': f'{r["trial_id"]}/fact/{i}', 'trial_id': r['trial_id'],
                   'qid': r['qid'], 'type': r['type'], 'compressor': r['compressor'],
                   'cohort': r['cohort'], 'fact_index': i, 'key_fact': fact,
                   'none_accuracy': r['none_trial']['answer_accuracy'],
                   'compressed_accuracy': r['compressed_trial']['answer_accuracy'],
                   'automatic_status': 'unverified', **dict.fromkeys(HUMAN, '')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dev-run', type=Path, default=ROOT/'results/runs/20261104-151606')
    parser.add_argument('--test-run', type=Path)
    parser.add_argument('--dataset', type=Path, default=ROOT/'data/evalsets/claude-v1/qa_test.json')
    parser.add_argument('--success-per-stratum', type=int, default=2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.success_per_stratum < 0:
        parser.error('success-per-stratum must be >= 0')
    out = args.output.resolve()
    if not any(out.is_relative_to(ROOT/p) for p in ('scripts', 'docs/analysis')):
        parser.error('output must be under scripts/ or docs/analysis/')
    if out.exists():
        parser.error('output already exists; choose a new directory')
    test = args.test_run or latest_test(ROOT/'results/runs')
    dev_summary, dev_rows = load_run(args.dev_run)
    test_summary, test_rows = load_run(test)
    if not complete(test_summary, test_rows):
        parser.error('test run is incomplete or has duplicate trials')
    records, denominators, issues, sources = build(test, args.dataset, args.success_per_stratum, args.seed)
    meta = {'created_utc': datetime.now(timezone.utc).isoformat(), 'arguments': {k: str(v) if isinstance(v, Path) else v for k,v in vars(args).items()},
            'analysis_git_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
            'git_status': subprocess.check_output(['git','status','--short'], cwd=ROOT, text=True),
            'dev': {'path': str(args.dev_run.resolve()), 'summary': dev_summary, 'args': read_json(args.dev_run/'args.json'), 'complete': complete(dev_summary, dev_rows)},
            'test': {'path': str(test.resolve()), 'summary': test_summary, 'args': read_json(test/'args.json')},
            'definitions': {'decline': 'compressed answer_accuracy < none answer_accuracy', 'success': 'compressed answer_accuracy = 1 and no decline',
                            'warning': 'Selected declines are not population cause prevalence. Facts may share evidence; no inferred fact-to-quote mapping.'},
            'denominators': denominators, 'join_issues': issues,
            'inputs': [fingerprint(p/f) for p in (args.dev_run,test) for f in ('summary.json','args.json','trials.jsonl')] + [fingerprint(args.dataset)] + sources,
            'implementation': [fingerprint(Path(__file__)), fingerprint(Path(__file__).with_name('compression_review_viewer.html'))]}
    payload = {'metadata': meta, 'records': records, 'review_rows': list(review_rows(records))}
    out.mkdir(parents=True)
    (out/'review_data.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    (out/'metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    with (out/'review_template.csv').open('w', encoding='utf-8-sig', newline='') as f:
        rows = payload['review_rows']
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ['review_id', *HUMAN])
        writer.writeheader(); writer.writerows(rows)
    data = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&','\\u0026')
    html = Path(__file__).with_name('compression_review_viewer.html').read_text().replace('__PAYLOAD__', data)
    (out/'review.html').write_text(html, encoding='utf-8')
    print(json.dumps({'output': str(out), 'declines': dict(Counter(r['compressor'] for r in records if r['cohort']=='decline')), 'success_samples': sum(r['cohort']=='success' for r in records), 'join_issue_trials': len(issues)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
