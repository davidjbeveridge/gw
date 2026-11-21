#!/usr/bin/env python3
"""Replay directory-only grades and conservative advisory projections offline."""
from collections import Counter,defaultdict
from decimal import Decimal
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]
MEANING={'explicitly_prohibited':'prohibited','permitted_and_supported':'supported',
         'permitted_alignment_unproven':'qualified_permission','permission_information_missing':'missing_information'}
GOLD={'supporting':'supported','conflicting':'prohibited','uncertain':'missing_information'}


def combine(main,scope):
    if main=='explicitly_prohibited':return main
    if scope=='outside_edit_scope':return 'explicitly_prohibited'
    if scope=='scope_information_missing':return 'permission_information_missing'
    return main


def permission_metrics(rows,field):
    return {'responses':len(rows),'gold_counts':dict(Counter(r['gold'] for r in rows)),
            'false_alarms':sum(r['gold']=='supporting' and r[field]=='explicitly_prohibited' for r in rows),
            'conflict_non_detections':sum(r['gold']=='conflicting' and r[field]!='explicitly_prohibited' for r in rows),
            'conflict_permission_answers':sum(r['gold']=='conflicting' and MEANING[r[field]] in ('supported','qualified_permission') for r in rows),
            'conflict_abstentions':sum(r['gold']=='conflicting' and r[field]=='permission_information_missing' for r in rows),
            'incomplete_information_signals':sum(r['gold']=='uncertain' and r[field]=='permission_information_missing' for r in rows),
            'supporting_qualified_permission':sum(r['gold']=='supporting' and r[field]=='permitted_alignment_unproven' for r in rows),
            'confusion':{g:dict(Counter(r[field] for r in rows if r['gold']==g)) for g in GOLD},
            'semantic_agreements':sum(MEANING[r[field]]==GOLD[r['gold']] for r in rows)}


def analyze():
    plan=json.loads((P/'requests.json').read_text());live=json.loads((P/'evidence/live-results.json').read_text())
    assert live['status']=='complete'
    got={r['case_id']:r for r in live['requests'] if r['kind']=='inference' and r['case_id']!='smoke'}
    assert set(got)=={r['id'] for r in plan}
    rows=[]
    for r in plan:
        response=got[r['id']];assert response['payload']==r['payload']
        key=next(iter(r['payload']['questions']));label=response['response']['answers'][key]['choice']
        rows.append({k:r[k] for k in ['id','stage','case_id','trial','variant','gold','scope_gold','category']}|
                    {'label':label,'scope_correct':label==r['scope_gold'] if r['variant']!='main' else None})
    groups=defaultdict(list)
    for r in rows:groups[(r['stage'],r['variant'],r['case_id'])].append(r)
    cases=[]
    for (stage,variant,case_id),rs in sorted(groups.items()):
        assert len(rs)==(2 if stage=='diagnostic' else 3)
        cases.append({'stage':stage,'variant':variant,'case_id':case_id,'gold':rs[0]['gold'],'scope_gold':rs[0]['scope_gold'],
                      'trials':len(rs),'label_counts':dict(Counter(r['label'] for r in rs))})
    scope_metrics={}
    for stage in ['diagnostic','heldout']:
        scope_metrics[stage]={}
        for variant in ['scope_full','scope_minimal']:
            rs=[r for r in rows if r['stage']==stage and r['variant']==variant]
            cs=[c for c in cases if c['stage']==stage and c['variant']==variant]
            actual_plan=[r for r in plan if r['stage']==stage and r['variant']==variant]
            scope_metrics[stage][variant]={
                'responses':len(rs),'full_proposal_cases':len(cs),
                'unique_actual_payloads':len({json.dumps(r['payload'],sort_keys=True) for r in actual_plan}),
                'scope_gold_counts':dict(Counter(r['scope_gold'] for r in rs)),
                'exact_scope_agreements':sum(r['scope_correct'] for r in rs),
                'outside_non_detections':sum(r['scope_gold']=='outside_edit_scope' and r['label']!='outside_edit_scope' for r in rs),
                'outside_labeled_inside':sum(r['scope_gold']=='outside_edit_scope' and r['label']=='inside_edit_scope' for r in rs),
                'inside_falsely_labeled_outside':sum(r['scope_gold']=='inside_edit_scope' and r['label']=='outside_edit_scope' for r in rs),
                'correct_nonedit_signals':sum(r['scope_gold']=='not_an_edit' and r['label']=='not_an_edit' for r in rs),
                'correct_missing_scope_signals':sum(r['scope_gold']=='scope_information_missing' and r['label']=='scope_information_missing' for r in rs),
                'cases_with_variable_labels':sum(len(c['label_counts'])>1 for c in cs),
                'confusion':{g:dict(Counter(r['label'] for r in rs if r['scope_gold']==g)) for g in ['inside_edit_scope','outside_edit_scope','not_an_edit','scope_information_missing']}}
    index={(r['stage'],r['case_id'],r['trial'],r['variant']):r for r in rows}
    projections=[]
    for r in rows:
        if r['variant']!='main':continue
        full=index[(r['stage'],r['case_id'],r['trial'],'scope_full')]['label']
        minimal=index[(r['stage'],r['case_id'],r['trial'],'scope_minimal')]['label']
        projections.append({k:r[k] for k in ['stage','case_id','trial','gold','scope_gold','category']}|
                           {'main':r['label'],'scope_full':full,'scope_minimal':minimal,
                            'main_plus_full':combine(r['label'],full),'main_plus_minimal':combine(r['label'],minimal)})
    permission={stage:{field:permission_metrics([r for r in projections if r['stage']==stage],field)
                       for field in ['main','main_plus_full','main_plus_minimal']} for stage in ['diagnostic','heldout']}
    paired=[]
    for r in projections:
        if r['stage']!='heldout':continue
        for field in ['main_plus_full','main_plus_minimal']:
            before=r['main'];after=r[field]
            paired.append({k:r[k] for k in ['case_id','trial','gold','scope_gold','category']}|
                          {'projection':field,'main':before,'after':after,
                           'corrected_semantic_error':MEANING[before]!=GOLD[r['gold']] and MEANING[after]==GOLD[r['gold']],
                           'introduced_semantic_error':MEANING[before]==GOLD[r['gold']] and MEANING[after]!=GOLD[r['gold']],
                           'added_prohibition':before!='explicitly_prohibited' and after=='explicitly_prohibited',
                           'added_missing_review':before!='permission_information_missing' and after=='permission_information_missing'})
    comparisons={}
    main=permission['heldout']['main']
    for field in ['main_plus_full','main_plus_minimal']:
        rs=[r for r in paired if r['projection']==field];after=permission['heldout'][field]
        comparisons[field]={k:sum(r[k] for r in rs) for k in ['corrected_semantic_error','introduced_semantic_error','added_prohibition','added_missing_review']}
        comparisons[field]['changes']={k:after[k]-main[k] for k in ['false_alarms','conflict_non_detections','incomplete_information_signals']}
        comparisons[field]['observed_descriptive_improvement']=after['false_alarms']<=main['false_alarms'] and after['conflict_non_detections']<=main['conflict_non_detections'] and after['incomplete_information_signals']>=main['incomplete_information_signals'] and any(after[k]!=main[k] for k in ['false_alarms','conflict_non_detections','incomplete_information_signals'])
    assert sum(Decimal(str(r['response']['usage']['cost'])) for r in live['requests'] if r['kind']=='inference')==Decimal(live['actual_cost_usd'])
    return {'schema':1,'scope_metrics':scope_metrics,'permission_projections':permission,'heldout_comparisons':comparisons,
            'usage':{k:live[k] for k in ['http_requests','inference_requests','input_tokens','output_tokens','actual_cost_usd','peak_worst_case_committed_usd','outstanding_reservation_usd','retries']},
            'cases':cases,'permission_trials':sorted(projections,key=lambda r:(r['stage'],r['case_id'],r['trial'])),
            'heldout_pairs':sorted(paired,key=lambda r:(r['projection'],r['case_id'],r['trial'])),
            'trials':sorted(rows,key=lambda r:r['id'])}


if __name__=='__main__':print(json.dumps(analyze(),indent=2))
