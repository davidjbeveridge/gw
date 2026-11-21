#!/usr/bin/env python3
"""Reproduce fixed-pair grades, overlap and structural blind spots offline."""
from collections import Counter,defaultdict
from decimal import Decimal
import importlib.util
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prior_scope_analysis',P.parent/'system1-scope-20261121/scripts/analyze.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
MEANING=prior.MEANING;GOLD=prior.GOLD


def analyze():
    plan=json.loads((P/'requests.json').read_text());live=json.loads((P/'evidence/live-results.json').read_text())
    assert live['status']=='complete'
    got={r['case_id']:r for r in live['requests'] if r['kind']=='inference' and r['case_id']!='smoke'}
    assert set(got)=={r['id'] for r in plan}
    labels={};trials=[]
    for r in plan:
        response=got[r['id']];assert response['payload']==r['payload']
        key=next(iter(r['payload']['questions']));label=response['response']['answers'][key]['choice']
        labels[(r['case_id'],r['trial'],r['variant'])]=label
        trials.append({k:r[k] for k in ['id','case_id','trial','variant','gold','scope_gold','family']}|{'label':label})
    pairs=[]
    for c in json.loads((P/'heldout-cases.json').read_text()):
        for trial in (1,2,3):
            main=labels[(c['id'],trial,'main')];scope=labels[(c['id'],trial,'scope_minimal')];paired=prior.combine(main,scope)
            outside=c['scope_gold']=='outside_edit_scope';mf=main=='explicitly_prohibited';sf=scope=='outside_edit_scope'
            overlap=('both_flag' if mf and sf else 'main_only' if mf else 'scope_only' if sf else 'neither_flag') if outside else None
            pairs.append({k:c[k] for k in ['id','gold','scope_gold','family']}|{'trial':trial,'main':main,'scope':scope,'paired':paired,
                'outside_overlap':overlap,'outside_joint_non_detection':outside and not mf and not sf,
                'paired_conflict_permission':c['gold']=='conflicting' and MEANING[paired] in ('supported','qualified_permission'),
                'paired_conflict_abstention':c['gold']=='conflicting' and paired=='permission_information_missing',
                'structural_no_signal_conflict':c['gold']=='conflicting' and not outside and paired!='explicitly_prohibited',
                'corrected_semantic_error':MEANING[main]!=GOLD[c['gold']] and MEANING[paired]==GOLD[c['gold']],
                'introduced_semantic_error':MEANING[main]==GOLD[c['gold']] and MEANING[paired]!=GOLD[c['gold']]})
    permission={field:prior.permission_metrics(pairs,field) for field in ['main','paired']}
    scope_rows=[r for r in trials if r['variant']=='scope_minimal']
    scope_metrics={'responses':len(scope_rows),'scope_gold_counts':dict(Counter(r['scope_gold'] for r in scope_rows)),
        'exact_agreements':sum(r['scope_gold']==r['label'] for r in scope_rows),
        'outside_non_detections':sum(r['scope_gold']=='outside_edit_scope' and r['label']!='outside_edit_scope' for r in scope_rows),
        'inside_falsely_outside':sum(r['scope_gold']=='inside_edit_scope' and r['label']=='outside_edit_scope' for r in scope_rows),
        'correct_nonedit_signals':sum(r['scope_gold']=='not_an_edit' and r['label']=='not_an_edit' for r in scope_rows),
        'correct_missing_scope_signals':sum(r['scope_gold']=='scope_information_missing' and r['label']=='scope_information_missing' for r in scope_rows),
        'confusion':{g:dict(Counter(r['label'] for r in scope_rows if r['scope_gold']==g)) for g in ['inside_edit_scope','outside_edit_scope','not_an_edit','scope_information_missing']}}
    grouped=defaultdict(list)
    for r in pairs:grouped[r['id']].append(r)
    cases=[]
    for case_id,rs in sorted(grouped.items()):
        cases.append({k:rs[0][k] for k in ['id','gold','scope_gold','family']}|
            {'main_labels':dict(Counter(r['main'] for r in rs)),'scope_labels':dict(Counter(r['scope'] for r in rs)),
             'paired_labels':dict(Counter(r['paired'] for r in rs)),
             'outside_joint_miss_trials':sum(r['outside_joint_non_detection'] for r in rs),
             'paired_conflict_permission_trials':sum(r['paired_conflict_permission'] for r in rs),
             'structural_no_signal_trials':sum(r['structural_no_signal_conflict'] for r in rs)})
    overlap=dict(Counter(r['outside_overlap'] for r in pairs if r['outside_overlap'] is not None))
    families={}
    for family in sorted({r['family'] for r in pairs}):
        rs=[r for r in pairs if r['family']==family]
        families[family]={'main':prior.permission_metrics(rs,'main'),'paired':prior.permission_metrics(rs,'paired'),
                          'outside_overlap':dict(Counter(r['outside_overlap'] for r in rs if r['outside_overlap'] is not None)),
                          'paired_conflict_permissions':sum(r['paired_conflict_permission'] for r in rs),
                          'structural_no_signals':sum(r['structural_no_signal_conflict'] for r in rs)}
    prior_scope_plan=json.loads((P.parent/'system1-scope-20261121/requests.json').read_text())
    previously_seen={json.dumps(r['payload'],sort_keys=True) for r in prior_scope_plan if r['variant']=='scope_minimal'}
    new_scope={json.dumps(r['payload'],sort_keys=True) for r in plan if r['variant']=='scope_minimal'}
    observed=permission['paired']['false_alarms']<=permission['main']['false_alarms'] and permission['paired']['conflict_non_detections']<=permission['main']['conflict_non_detections'] and permission['paired']['incomplete_information_signals']>=permission['main']['incomplete_information_signals'] and any(permission['paired'][k]!=permission['main'][k] for k in ['false_alarms','conflict_non_detections','incomplete_information_signals'])
    assert sum(Decimal(str(r['response']['usage']['cost'])) for r in live['requests'] if r['kind']=='inference')==Decimal(live['actual_cost_usd'])
    return {'schema':1,'permission_metrics':permission,'scope_metrics':scope_metrics,'outside_overlap':overlap,
        'outside_joint_miss_cases':sum(c['outside_joint_miss_trials']>0 for c in cases),
        'outside_joint_miss_cases_all_three_trials':sum(c['outside_joint_miss_trials']==3 for c in cases),
        'paired_conflict_permission_trials':sum(r['paired_conflict_permission'] for r in pairs),
        'paired_conflict_abstention_trials':sum(r['paired_conflict_abstention'] for r in pairs),
        'structural_no_signal_conflict_trials':sum(r['structural_no_signal_conflict'] for r in pairs),
        'corrected_semantic_errors':sum(r['corrected_semantic_error'] for r in pairs),
        'introduced_semantic_errors':sum(r['introduced_semantic_error'] for r in pairs),
        'observed_descriptive_improvement':observed,
        'unique_scope_payloads':len(new_scope),'previously_seen_scope_payloads':len(new_scope&previously_seen),'novel_scope_payloads':len(new_scope-previously_seen),
        'families':families,'cases':cases,'pairs':pairs,'trials':sorted(trials,key=lambda r:r['id']),
        'usage':{k:live[k] for k in ['http_requests','inference_requests','input_tokens','output_tokens','actual_cost_usd','peak_worst_case_committed_usd','outstanding_reservation_usd','retries']}}


if __name__=='__main__':print(json.dumps(analyze(),indent=2))
