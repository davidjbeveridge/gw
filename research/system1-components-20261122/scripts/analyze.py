#!/usr/bin/env python3
"""Replay representation-only scope grades and matched path contrasts offline."""
from collections import Counter,defaultdict
from decimal import Decimal
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]


def analyze():
    d=json.loads((P/'design.json').read_text());plan=json.loads((P/'requests.json').read_text());live=json.loads((P/'evidence/live-results.json').read_text())
    assert live['status']=='complete'
    got={r['case_id']:r for r in live['requests'] if r['kind']=='inference' and r['case_id']!='smoke'}
    assert set(got)=={r['id'] for r in plan}
    rows=[]
    for r in plan:
        x=got[r['id']];assert x['payload']==r['payload'];label=x['response']['answers']['scope']['choice'];meaning=d['scope_label_map'][label]
        rows.append({k:r[k] for k in ['id','case_id','trial','variant','scope_gold','family','matched_pair']}|
                    {'label':label,'meaning':meaning,'correct':meaning==r['scope_gold']})
    groups=defaultdict(list)
    for r in rows:groups[(r['case_id'],r['variant'])].append(r)
    cases=[]
    for (case_id,variant),rs in sorted(groups.items()):
        assert len(rs)==3
        cases.append({'case_id':case_id,'variant':variant,'scope_gold':rs[0]['scope_gold'],'family':rs[0]['family'],'matched_pair':rs[0]['matched_pair'],
                      'labels':dict(Counter(r['label'] for r in rs)),'correct_trials':sum(r['correct'] for r in rs)})
    metrics={}
    for variant in ['raw','components']:
        rs=[r for r in rows if r['variant']==variant];cs=[c for c in cases if c['variant']==variant]
        metrics[variant]={'responses':len(rs),'unique_cases':len(cs),'scope_gold_counts':dict(Counter(r['scope_gold'] for r in rs)),
            'exact_agreements':sum(r['correct'] for r in rs),
            'outside_non_detections':sum(r['scope_gold']=='outside_edit_scope' and r['meaning']!='outside_edit_scope' for r in rs),
            'outside_labeled_inside':sum(r['scope_gold']=='outside_edit_scope' and r['meaning']=='inside_edit_scope' for r in rs),
            'inside_falsely_outside':sum(r['scope_gold']=='inside_edit_scope' and r['meaning']=='outside_edit_scope' for r in rs),
            'inside_abstentions':sum(r['scope_gold']=='inside_edit_scope' and r['meaning']=='scope_information_missing' for r in rs),
            'correct_nonedit_signals':sum(r['scope_gold']=='not_an_edit' and r['meaning']=='not_an_edit' for r in rs),
            'correct_missing_operation_signals':sum(r['scope_gold']=='scope_information_missing' and r['meaning']=='scope_information_missing' for r in rs),
            'cases_with_any_error':sum(c['correct_trials']<3 for c in cs),'persistent_error_cases':sum(c['correct_trials']==0 for c in cs),
            'variable_cases':sum(len(c['labels'])>1 for c in cs),
            'confusion':{g:dict(Counter(r['meaning'] for r in rs if r['scope_gold']==g)) for g in ['inside_edit_scope','outside_edit_scope','not_an_edit','scope_information_missing']}}
    indexed={(r['case_id'],r['trial'],r['variant']):r for r in rows};transitions=[]
    for r in rows:
        if r['variant']!='raw':continue
        b=indexed[(r['case_id'],r['trial'],'components')]
        transitions.append({k:r[k] for k in ['case_id','trial','scope_gold','family','matched_pair']}|
            {'raw':r['label'],'components':b['label'],'corrected_error':not r['correct'] and b['correct'],'introduced_error':r['correct'] and not b['correct']})
    contrast_rows=[]
    for variant in ['raw','components']:
        for contrast in sorted({r['matched_pair'] for r in rows if r['matched_pair']}):
            for trial in (1,2,3):
                rs=[r for r in rows if r['variant']==variant and r['matched_pair']==contrast and r['trial']==trial];assert len(rs)==2
                outside=next(r for r in rs if r['scope_gold']=='outside_edit_scope');inside=next(r for r in rs if r['scope_gold']=='inside_edit_scope')
                status='both_correct' if outside['correct'] and inside['correct'] else 'outside_only_correct' if outside['correct'] else 'inside_only_correct' if inside['correct'] else 'neither_correct'
                contrast_rows.append({'variant':variant,'contrast':contrast,'trial':trial,'status':status,'outside':outside['label'],'inside':inside['label']})
    families={family:{v:{'responses':sum(r['family']==family and r['variant']==v for r in rows),'correct':sum(r['family']==family and r['variant']==v and r['correct'] for r in rows)} for v in ['raw','components']} for family in sorted({r['family'] for r in rows})}
    a=metrics['raw'];b=metrics['components']
    comparison={'corrected_errors':sum(r['corrected_error'] for r in transitions),'introduced_errors':sum(r['introduced_error'] for r in transitions),
        'changes':{k:b[k]-a[k] for k in ['outside_non_detections','inside_falsely_outside','correct_nonedit_signals','correct_missing_operation_signals']},
        'observed_descriptive_improvement':b['outside_non_detections']<=a['outside_non_detections'] and b['inside_falsely_outside']<=a['inside_falsely_outside'] and b['correct_missing_operation_signals']>=a['correct_missing_operation_signals'] and any(b[k]!=a[k] for k in ['outside_non_detections','inside_falsely_outside','correct_missing_operation_signals'])}
    assert sum(Decimal(str(r['response']['usage']['cost'])) for r in live['requests'] if r['kind']=='inference')==Decimal(live['actual_cost_usd'])
    return {'schema':1,'metrics':metrics,'comparison':comparison,
        'contrast_counts':{v:dict(Counter(r['status'] for r in contrast_rows if r['variant']==v)) for v in ['raw','components']},
        'families':families,'cases':cases,'transitions':sorted(transitions,key=lambda r:(r['case_id'],r['trial'])),
        'contrasts':contrast_rows,'trials':sorted(rows,key=lambda r:r['id']),
        'usage':{k:live[k] for k in ['http_requests','inference_requests','input_tokens','output_tokens','actual_cost_usd','peak_worst_case_committed_usd','outstanding_reservation_usd','retries']}}


if __name__=='__main__':print(json.dumps(analyze(),indent=2))
