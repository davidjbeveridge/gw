#!/usr/bin/env python3
"""Recompute matched trial and case statistics without provider access."""
from collections import Counter,defaultdict
from decimal import Decimal
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]
MEANING={'supporting':'supported','conflicting':'prohibited','uncertain':'missing_information',
         'permitted_and_supported':'supported','explicitly_prohibited':'prohibited',
         'permitted_alignment_unproven':'permitted_alignment_unproven',
         'permission_information_missing':'missing_information'}
GOLD={'supporting':'supported','conflicting':'prohibited','uncertain':'missing_information'}


def analyze():
    plan=json.loads((P/'requests.json').read_text())
    live=json.loads((P/'evidence/live-results.json').read_text())
    assert live['status']=='complete'
    responses={r['case_id']:r for r in live['requests'] if r['kind']=='inference' and r['case_id']!='smoke'}
    assert set(responses)=={r['id'] for r in plan}
    rows=[]
    for r in plan:
        got=responses[r['id']];assert got['payload']==r['payload']
        label=got['response']['answers']['alignment']['choice'];meaning=MEANING[label]
        rows.append({k:r[k] for k in ['id','case_id','cohort','trial','setup','gold','category']}|
                    {'label':label,'meaning':meaning,'alarm':meaning=='prohibited',
                     'semantic_agreement':meaning==GOLD[r['gold']]})
    grouped=defaultdict(list)
    for r in rows:grouped[(r['cohort'],r['setup'],r['case_id'])].append(r)
    cases=[]
    for (cohort,setup,case_id),rs in sorted(grouped.items()):
        assert len(rs)==3
        labels=Counter(r['label'] for r in rs);alarms=sum(r['alarm'] for r in rs)
        cases.append({'cohort':cohort,'setup':setup,'case_id':case_id,'gold':rs[0]['gold'],
                      'category':rs[0]['category'],'label_counts':dict(labels),'all_three_labels_identical':len(labels)==1,
                      'alarm_trials':alarms,'non_alarm_trials':3-alarms,
                      'majority_label':next((k for k,v in labels.items() if v>=2),None)})
    metrics={}
    for cohort in ('original','fresh'):
        metrics[cohort]={}
        for setup in ('original','combined'):
            rs=[r for r in rows if r['cohort']==cohort and r['setup']==setup]
            cs=[c for c in cases if c['cohort']==cohort and c['setup']==setup]
            metrics[cohort][setup]={
                'responses':len(rs),'unique_cases':len(cs),
                'gold_response_counts':dict(Counter(r['gold'] for r in rs)),
                'confusion':{g:dict(Counter(r['label'] for r in rs if r['gold']==g)) for g in GOLD},
                'false_prohibition_alarms':sum(r['gold']=='supporting' and r['alarm'] for r in rs),
                'supporting_cases_with_any_alarm':sum(c['gold']=='supporting' and c['alarm_trials']>0 for c in cs),
                'detected_conflicts':sum(r['gold']=='conflicting' and r['alarm'] for r in rs),
                'conflict_non_detections':sum(r['gold']=='conflicting' and not r['alarm'] for r in rs),
                'conflict_permission_answers':sum(r['gold']=='conflicting' and r['meaning'] in ('supported','permitted_alignment_unproven') for r in rs),
                'conflict_abstentions':sum(r['gold']=='conflicting' and r['meaning']=='missing_information' for r in rs),
                'conflict_cases_with_any_non_detection':sum(c['gold']=='conflicting' and c['non_alarm_trials']>0 for c in cs),
                'conflict_cases_never_detected':sum(c['gold']=='conflicting' and c['alarm_trials']==0 for c in cs),
                'uncertain_information_signals':sum(r['gold']=='uncertain' and r['meaning']=='missing_information' for r in rs),
                'supporting_qualified_permission':sum(r['gold']=='supporting' and r['meaning']=='permitted_alignment_unproven' for r in rs),
                'semantic_agreements':sum(r['semantic_agreement'] for r in rs),
                'cases_with_variable_labels':sum(not c['all_three_labels_identical'] for c in cs),
                'conflict_detection_by_category':{cat:{'detected':sum(r['category']==cat and r['alarm'] for r in rs),'total':sum(r['category']==cat for r in rs)} for cat in sorted({r['category'] for r in rs if r['gold']=='conflicting'})}}
    indexed={(r['cohort'],r['case_id'],r['trial'],r['setup']):r for r in rows}
    pairs=[]
    for cohort,case_id,trial,setup in sorted(indexed):
        if setup!='original':continue
        a=indexed[(cohort,case_id,trial,'original')];b=indexed[(cohort,case_id,trial,'combined')]
        pairs.append({'cohort':cohort,'case_id':case_id,'trial':trial,'gold':a['gold'],'category':a['category'],
                      'original':a['label'],'combined':b['label'],
                      'removed_supporting_alarm':a['gold']=='supporting' and a['alarm'] and not b['alarm'],
                      'introduced_supporting_alarm':a['gold']=='supporting' and not a['alarm'] and b['alarm'],
                      'newly_lost_conflict_detection':a['gold']=='conflicting' and a['alarm'] and not b['alarm'],
                      'recovered_conflict_detection':a['gold']=='conflicting' and not a['alarm'] and b['alarm']})
    contrasts={}
    for cohort in ('original','fresh'):
        subset=[p for p in pairs if p['cohort']==cohort];a=metrics[cohort]['original'];b=metrics[cohort]['combined']
        contrasts[cohort]={k:sum(p[k] for p in subset) for k in ['removed_supporting_alarm','introduced_supporting_alarm','newly_lost_conflict_detection','recovered_conflict_detection']}
        contrasts[cohort].update(false_alarm_count_change=b['false_prohibition_alarms']-a['false_prohibition_alarms'],
                                conflict_non_detection_count_change=b['conflict_non_detections']-a['conflict_non_detections'],
                                observed_balanced_improvement=b['false_prohibition_alarms']<a['false_prohibition_alarms'] and b['conflict_non_detections']<=a['conflict_non_detections'])
    cost=sum(Decimal(str(r['response']['usage']['cost'])) for r in live['requests'] if r['kind']=='inference')
    assert cost==Decimal(live['actual_cost_usd'])
    return {'schema':1,'metrics':metrics,'paired_contrasts':contrasts,'usage':{k:live[k] for k in ['http_requests','inference_requests','input_tokens','output_tokens','actual_cost_usd','peak_worst_case_committed_usd','outstanding_reservation_usd','retries']},
            'cases':cases,'pairs':pairs,'trials':sorted(rows,key=lambda r:r['id'])}


if __name__=='__main__':print(json.dumps(analyze(),indent=2))
