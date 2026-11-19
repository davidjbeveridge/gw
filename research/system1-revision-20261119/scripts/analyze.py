#!/usr/bin/env python3
"""Reproduce staged ablation and held-out matched grades offline."""
from collections import Counter,defaultdict
from decimal import Decimal
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]
MEANING={'supporting':'supported','conflicting':'prohibited','uncertain':'missing_information',
         'permitted_and_supported':'supported','explicitly_prohibited':'prohibited',
         'permitted_alignment_unproven':'permitted_alignment_unproven','permission_information_missing':'missing_information'}
GOLD={'supporting':'supported','conflicting':'prohibited','uncertain':'missing_information'}


def metrics(rs,cs):
    return {'responses':len(rs),'unique_cases':len(cs),'gold_counts':dict(Counter(r['gold'] for r in rs)),
            'confusion':{g:dict(Counter(r['label'] for r in rs if r['gold']==g)) for g in GOLD},
            'false_alarms':sum(r['gold']=='supporting' and r['meaning']=='prohibited' for r in rs),
            'conflict_detections':sum(r['gold']=='conflicting' and r['meaning']=='prohibited' for r in rs),
            'conflict_non_detections':sum(r['gold']=='conflicting' and r['meaning']!='prohibited' for r in rs),
            'conflict_permission_answers':sum(r['gold']=='conflicting' and r['meaning'] in ('supported','permitted_alignment_unproven') for r in rs),
            'conflict_abstentions':sum(r['gold']=='conflicting' and r['meaning']=='missing_information' for r in rs),
            'incomplete_information_signals':sum(r['gold']=='uncertain' and r['meaning']=='missing_information' for r in rs),
            'incomplete_permission_answers':sum(r['gold']=='uncertain' and r['meaning'] in ('supported','permitted_alignment_unproven') for r in rs),
            'incomplete_prohibition_answers':sum(r['gold']=='uncertain' and r['meaning']=='prohibited' for r in rs),
            'supporting_qualified_permission':sum(r['gold']=='supporting' and r['meaning']=='permitted_alignment_unproven' for r in rs),
            'semantic_agreements':sum(r['correct'] for r in rs),
            'cases_with_variable_labels':sum(len(c['label_counts'])>1 for c in cs),
            'cases_with_any_semantic_error':sum(c['correct_trials']<c['trials'] for c in cs),
            'categories':{category:{'responses':sum(r['category']==category for r in rs),'semantic_agreements':sum(r['category']==category and r['correct'] for r in rs)} for category in sorted({r['category'] for r in rs})}}


def analyze():
    plan=json.loads((P/'requests.json').read_text());live=json.loads((P/'evidence/live-results.json').read_text())
    assert live['status']=='complete'
    responses={r['case_id']:r for r in live['requests'] if r['kind']=='inference' and r['case_id']!='smoke'}
    assert set(responses)=={r['id'] for r in plan}
    rows=[]
    for r in plan:
        got=responses[r['id']];assert got['payload']==r['payload']
        label=got['response']['answers']['alignment']['choice'];meaning=MEANING[label]
        rows.append({k:r[k] for k in ['id','stage','case_id','trial','variant','gold','category']}|
                    {'label':label,'meaning':meaning,'correct':meaning==GOLD[r['gold']]})
    groups=defaultdict(list)
    for r in rows:groups[(r['stage'],r['variant'],r['case_id'])].append(r)
    cases=[]
    for (stage,variant,case_id),rs in sorted(groups.items()):
        assert len(rs)==(2 if stage=='diagnostic' else 3)
        cases.append({'stage':stage,'variant':variant,'case_id':case_id,'gold':rs[0]['gold'],'category':rs[0]['category'],
                      'trials':len(rs),'label_counts':dict(Counter(r['label'] for r in rs)),
                      'correct_trials':sum(r['correct'] for r in rs)})
    tables={}
    for stage in ('diagnostic','heldout'):
        variants=('combined','scope_context_only','prerequisite_question_only','revised') if stage=='diagnostic' else ('original','combined','revised')
        tables[stage]={variant:metrics([r for r in rows if r['stage']==stage and r['variant']==variant],
                                      [c for c in cases if c['stage']==stage and c['variant']==variant]) for variant in variants}
    index={(r['stage'],r['case_id'],r['trial'],r['variant']):r for r in rows}
    pairs=[]
    for r in rows:
        if r['stage']!='heldout' or r['variant']!='revised':continue
        for comparator in ('combined','original'):
            a=index[('heldout',r['case_id'],r['trial'],comparator)]
            pairs.append({'case_id':r['case_id'],'trial':r['trial'],'gold':r['gold'],'category':r['category'],'comparator':comparator,
                          'before':a['label'],'revised':r['label'],
                          'corrected_semantic_error':not a['correct'] and r['correct'],
                          'introduced_semantic_error':a['correct'] and not r['correct'],
                          'removed_false_alarm':r['gold']=='supporting' and a['meaning']=='prohibited' and r['meaning']!='prohibited',
                          'introduced_false_alarm':r['gold']=='supporting' and a['meaning']!='prohibited' and r['meaning']=='prohibited',
                          'recovered_conflict_detection':r['gold']=='conflicting' and a['meaning']!='prohibited' and r['meaning']=='prohibited',
                          'lost_conflict_detection':r['gold']=='conflicting' and a['meaning']=='prohibited' and r['meaning']!='prohibited'})
    comparisons={}
    for comparator in ('combined','original'):
        selected=[p for p in pairs if p['comparator']==comparator]
        a=tables['heldout'][comparator];b=tables['heldout']['revised']
        primary=['false_alarms','conflict_non_detections','incomplete_information_signals']
        comparisons[comparator]={k:sum(p[k] for p in selected) for k in ['corrected_semantic_error','introduced_semantic_error','removed_false_alarm','introduced_false_alarm','recovered_conflict_detection','lost_conflict_detection']}
        comparisons[comparator]['changes']={k:b[k]-a[k] for k in primary}
        comparisons[comparator]['observed_descriptive_improvement']=b['false_alarms']<=a['false_alarms'] and b['conflict_non_detections']<=a['conflict_non_detections'] and b['incomplete_information_signals']>=a['incomplete_information_signals'] and any(b[k]!=a[k] for k in primary)
    cost=sum(Decimal(str(r['response']['usage']['cost'])) for r in live['requests'] if r['kind']=='inference')
    assert cost==Decimal(live['actual_cost_usd'])
    usage={k:live[k] for k in ['http_requests','inference_requests','input_tokens','output_tokens','actual_cost_usd','peak_worst_case_committed_usd','outstanding_reservation_usd','retries']}
    stage_usage={}
    for stage in ('diagnostic','heldout'):
        ids={r['id'] for r in plan if r['stage']==stage};rs=[responses[i] for i in ids]
        stage_usage[stage]={'requests':len(rs),'input_tokens':sum(r['response']['usage']['input_tokens'] for r in rs),
                            'output_tokens':sum(r['response']['usage']['output_tokens'] for r in rs),
                            'cost_usd':str(sum(Decimal(str(r['response']['usage']['cost'])) for r in rs))}
    return {'schema':1,'metrics':tables,'heldout_comparisons':comparisons,'usage':usage,'stage_usage':stage_usage,
            'cases':cases,'heldout_pairs':sorted(pairs,key=lambda r:(r['comparator'],r['case_id'],r['trial'])),
            'trials':sorted(rows,key=lambda r:r['id'])}


if __name__=='__main__':print(json.dumps(analyze(),indent=2))
