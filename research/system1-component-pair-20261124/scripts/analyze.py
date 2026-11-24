#!/usr/bin/env python3
"""Replay dot-root shared misses and absent-operation projection regressions."""
from collections import Counter,defaultdict
from decimal import Decimal
import importlib.util
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prior_scope_analysis',P.parent/'system1-scope-20261121/scripts/analyze.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)


def permission(rows,field):
    base=prior.permission_metrics(rows,field)
    base['incomplete_permission_answers']=sum(r['gold']=='uncertain' and prior.MEANING[r[field]] in ('supported','qualified_permission') for r in rows)
    base['incomplete_prohibition_answers']=sum(r['gold']=='uncertain' and r[field]=='explicitly_prohibited' for r in rows)
    return base


def analyze():
    d=json.loads((P/'design.json').read_text());plan=json.loads((P/'requests.json').read_text());live=json.loads((P/'evidence/live-results.json').read_text())
    assert live['status']=='complete'
    got={r['case_id']:r for r in live['requests'] if r['kind']=='inference' and r['case_id']!='smoke'}
    assert set(got)=={r['id'] for r in plan}
    rows=[];labels={}
    for r in plan:
        x=got[r['id']];assert x['payload']==r['payload'];key=next(iter(r['payload']['questions']));label=x['response']['answers'][key]['choice']
        scope=d['scope_label_map'][label] if r['variant']=='scope_components' else None
        rows.append({k:r[k] for k in ['id','case_id','trial','variant','gold','scope_gold','family','operation_form']}|{'label':label,'scope_meaning':scope})
        labels[(r['case_id'],r['trial'],r['variant'])]=(label,scope)
    pairs=[]
    for r in rows:
        if r['variant']!='main':continue
        raw_scope,scope=labels[(r['case_id'],r['trial'],'scope_components')];main=r['label'];paired=prior.combine(main,scope)
        outside=r['scope_gold']=='outside_edit_scope';mf=main=='explicitly_prohibited';sf=scope=='outside_edit_scope'
        pairs.append({k:r[k] for k in ['case_id','trial','gold','scope_gold','family','operation_form']}|
            {'main':main,'scope_label':raw_scope,'scope':scope,'paired':paired,
             'outside_overlap':('both_flag' if mf and sf else 'main_only' if mf else 'scope_only' if sf else 'neither_flag') if outside else None,
             'corrected_semantic_error':prior.MEANING[main]!=prior.GOLD[r['gold']] and prior.MEANING[paired]==prior.GOLD[r['gold']],
             'introduced_semantic_error':prior.MEANING[main]==prior.GOLD[r['gold']] and prior.MEANING[paired]!=prior.GOLD[r['gold']],
             'overrode_correct_missing_signal':r['gold']=='uncertain' and main=='permission_information_missing' and paired!='permission_information_missing'})
    metrics={field:permission(pairs,field) for field in ['main','paired']}
    sr=[r for r in rows if r['variant']=='scope_components']
    scope_metrics={'responses':len(sr),'scope_gold_counts':dict(Counter(r['scope_gold'] for r in sr)),
        'exact_agreements':sum(r['scope_meaning']==r['scope_gold'] for r in sr),
        'outside_non_detections':sum(r['scope_gold']=='outside_edit_scope' and r['scope_meaning']!='outside_edit_scope' for r in sr),
        'inside_falsely_outside':sum(r['scope_gold']=='inside_edit_scope' and r['scope_meaning']=='outside_edit_scope' for r in sr),
        'correct_nonedit_signals':sum(r['scope_gold']=='not_an_edit' and r['scope_meaning']=='not_an_edit' for r in sr),
        'correct_missing_operation_signals':sum(r['scope_gold']=='scope_information_missing' and r['scope_meaning']=='scope_information_missing' for r in sr),
        'confusion':{g:dict(Counter(r['scope_meaning'] for r in sr if r['scope_gold']==g)) for g in ['inside_edit_scope','outside_edit_scope','not_an_edit','scope_information_missing']}}
    groups=defaultdict(list)
    for r in pairs:groups[r['case_id']].append(r)
    cases=[]
    for case_id,rs in sorted(groups.items()):
        assert len(rs)==3
        cases.append({k:rs[0][k] for k in ['case_id','gold','scope_gold','family','operation_form']}|
            {'main_labels':dict(Counter(r['main'] for r in rs)),'scope_labels':dict(Counter(r['scope_label'] for r in rs)),
             'paired_labels':dict(Counter(r['paired'] for r in rs)),
             'paired_correct_trials':sum(prior.MEANING[r['paired']]==prior.GOLD[r['gold']] for r in rs),
             'outside_joint_miss_trials':sum(r['outside_overlap']=='neither_flag' for r in rs)})
    families={family:{f:permission([r for r in pairs if r['family']==family],f) for f in ['main','paired']} for family in sorted({r['family'] for r in pairs})}
    operation_forms={}
    for form in ['absent','null','empty']:
        rs=[r for r in pairs if r['operation_form']==form];scope_subset=[r for r in sr if r['operation_form']==form]
        operation_forms[form]={'main':permission(rs,'main'),'paired':permission(rs,'paired'),
            'scope_confusion':dict(Counter(r['scope_meaning'] for r in scope_subset)),
            'scope_correct_missing':sum(r['scope_meaning']=='scope_information_missing' for r in scope_subset),
            'overrode_correct_missing_signal':sum(r['overrode_correct_missing_signal'] for r in rs)}
    a=metrics['main'];b=metrics['paired']
    comparison={'corrected_semantic_errors':sum(r['corrected_semantic_error'] for r in pairs),'introduced_semantic_errors':sum(r['introduced_semantic_error'] for r in pairs),
        'overrode_correct_missing_signal':sum(r['overrode_correct_missing_signal'] for r in pairs),
        'changes':{k:b[k]-a[k] for k in ['false_alarms','conflict_non_detections','incomplete_information_signals','incomplete_permission_answers','incomplete_prohibition_answers']},
        'observed_descriptive_improvement':b['false_alarms']<=a['false_alarms'] and b['conflict_non_detections']<=a['conflict_non_detections'] and b['incomplete_information_signals']>=a['incomplete_information_signals'] and any(b[k]!=a[k] for k in ['false_alarms','conflict_non_detections','incomplete_information_signals'])}
    assert sum(Decimal(str(r['response']['usage']['cost'])) for r in live['requests'] if r['kind']=='inference')==Decimal(live['actual_cost_usd'])
    return {'schema':1,'permission_metrics':metrics,'scope_metrics':scope_metrics,'outside_overlap':dict(Counter(r['outside_overlap'] for r in pairs if r['outside_overlap'] is not None)),
        'outside_joint_miss_cases':sum(c['outside_joint_miss_trials']>0 for c in cases),
        'outside_joint_miss_cases_all_three_trials':sum(c['outside_joint_miss_trials']==3 for c in cases),
        'comparison':comparison,'operation_forms':operation_forms,'families':families,'cases':cases,
        'pairs':sorted(pairs,key=lambda r:(r['case_id'],r['trial'])),'trials':sorted(rows,key=lambda r:r['id']),
        'usage':{k:live[k] for k in ['http_requests','inference_requests','input_tokens','output_tokens','actual_cost_usd','peak_worst_case_committed_usd','outstanding_reservation_usd','retries']}}


if __name__=='__main__':print(json.dumps(analyze(),indent=2))
