#!/usr/bin/env python3
"""Replay old/new scope grades and unchanged conservative pair projections."""
from collections import Counter,defaultdict
from decimal import Decimal
import importlib.util
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('previous_scope_analysis',P.parent/'system1-scope-20261121/scripts/analyze.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)


def analyze():
    d=json.loads((P/'design.json').read_text());plan=json.loads((P/'requests.json').read_text());live=json.loads((P/'evidence/live-results.json').read_text())
    assert live['status']=='complete'
    got={r['case_id']:r for r in live['requests'] if r['kind']=='inference' and r['case_id']!='smoke'}
    assert set(got)=={r['id'] for r in plan}
    rows=[]
    for r in plan:
        x=got[r['id']];assert x['payload']==r['payload'];key=next(iter(r['payload']['questions']));label=x['response']['answers'][key]['choice']
        normalized=None if r['variant']=='main' else label if r['variant']=='scope_old' else d['scope_label_map'][label]
        rows.append({k:r[k] for k in ['id','stage','case_id','trial','variant','gold','scope_gold','family']}|
                    {'label':label,'normalized_scope':normalized})
    groups=defaultdict(list)
    for r in rows:groups[(r['stage'],r['case_id'],r['variant'])].append(r)
    cases=[]
    for (stage,case_id,variant),rs in sorted(groups.items()):
        assert len(rs)==(2 if stage=='diagnostic' else 3)
        cases.append({'stage':stage,'case_id':case_id,'variant':variant,'gold':rs[0]['gold'],'scope_gold':rs[0]['scope_gold'],'family':rs[0]['family'],
                      'trials':len(rs),'label_counts':dict(Counter(r['label'] for r in rs)),
                      'scope_correct_trials':sum(r['normalized_scope']==r['scope_gold'] for r in rs) if variant!='main' else None})
    scope_metrics={}
    for stage,variants in [('diagnostic',['scope_old','component_no_examples','scope_revised']),('heldout',['scope_old','scope_revised'])]:
        scope_metrics[stage]={}
        for variant in variants:
            rs=[r for r in rows if r['stage']==stage and r['variant']==variant]
            cs=[c for c in cases if c['stage']==stage and c['variant']==variant]
            scope_metrics[stage][variant]={
                'responses':len(rs),'unique_cases':len(cs),'scope_gold_counts':dict(Counter(r['scope_gold'] for r in rs)),
                'exact_agreements':sum(r['normalized_scope']==r['scope_gold'] for r in rs),
                'outside_non_detections':sum(r['scope_gold']=='outside_edit_scope' and r['normalized_scope']!='outside_edit_scope' for r in rs),
                'inside_falsely_outside':sum(r['scope_gold']=='inside_edit_scope' and r['normalized_scope']=='outside_edit_scope' for r in rs),
                'correct_nonedit_signals':sum(r['scope_gold']=='not_an_edit' and r['normalized_scope']=='not_an_edit' for r in rs),
                'correct_missing_scope_signals':sum(r['scope_gold']=='scope_information_missing' and r['normalized_scope']=='scope_information_missing' for r in rs),
                'variable_cases':sum(len(c['label_counts'])>1 for c in cs),
                'confusion':{g:dict(Counter(r['normalized_scope'] for r in rs if r['scope_gold']==g)) for g in ['inside_edit_scope','outside_edit_scope','not_an_edit','scope_information_missing']}}
    index={(r['stage'],r['case_id'],r['trial'],r['variant']):r for r in rows};pairs=[]
    for r in rows:
        if r['stage']!='heldout' or r['variant']!='main':continue
        old=index[('heldout',r['case_id'],r['trial'],'scope_old')]['normalized_scope'];new=index[('heldout',r['case_id'],r['trial'],'scope_revised')]['normalized_scope']
        mf=r['label']=='explicitly_prohibited'
        pairs.append({k:r[k] for k in ['case_id','trial','gold','scope_gold','family']}|
            {'main':r['label'],'scope_old':old,'scope_revised':new,'pair_old':prior.combine(r['label'],old),'pair_revised':prior.combine(r['label'],new),
             'overlap_old':('both_flag' if mf and old=='outside_edit_scope' else 'main_only' if mf else 'scope_only' if old=='outside_edit_scope' else 'neither_flag') if r['scope_gold']=='outside_edit_scope' else None,
             'overlap_revised':('both_flag' if mf and new=='outside_edit_scope' else 'main_only' if mf else 'scope_only' if new=='outside_edit_scope' else 'neither_flag') if r['scope_gold']=='outside_edit_scope' else None})
    permission={f:prior.permission_metrics(pairs,f) for f in ['main','pair_old','pair_revised']}
    comparisons={}
    for before,after,name in [('pair_old','pair_revised','revised_pair_vs_old_pair')]:
        a=permission[before];b=permission[after]
        comparisons[name]={
            'corrected_semantic_errors':sum(prior.MEANING[r[before]]!=prior.GOLD[r['gold']] and prior.MEANING[r[after]]==prior.GOLD[r['gold']] for r in pairs),
            'introduced_semantic_errors':sum(prior.MEANING[r[before]]==prior.GOLD[r['gold']] and prior.MEANING[r[after]]!=prior.GOLD[r['gold']] for r in pairs),
            'changes':{k:b[k]-a[k] for k in ['false_alarms','conflict_non_detections','incomplete_information_signals']},
            'observed_descriptive_improvement':b['false_alarms']<=a['false_alarms'] and b['conflict_non_detections']<=a['conflict_non_detections'] and b['incomplete_information_signals']>=a['incomplete_information_signals'] and any(b[k]!=a[k] for k in ['false_alarms','conflict_non_detections','incomplete_information_signals'])}
    old=scope_metrics['heldout']['scope_old'];new=scope_metrics['heldout']['scope_revised']
    comparisons['revised_scope_vs_old_scope']={'observed_descriptive_improvement':new['outside_non_detections']<=old['outside_non_detections'] and new['inside_falsely_outside']<=old['inside_falsely_outside'] and new['correct_missing_scope_signals']>=old['correct_missing_scope_signals'] and any(new[k]!=old[k] for k in ['outside_non_detections','inside_falsely_outside','correct_missing_scope_signals'])}
    assert sum(Decimal(str(r['response']['usage']['cost'])) for r in live['requests'] if r['kind']=='inference')==Decimal(live['actual_cost_usd'])
    families={}
    for family in sorted({r['family'] for r in pairs}):
        rs=[r for r in pairs if r['family']==family];families[family]={f:prior.permission_metrics(rs,f) for f in ['main','pair_old','pair_revised']}
    return {'schema':1,'scope_metrics':scope_metrics,'permission_metrics':permission,
        'outside_overlap':{variant:dict(Counter(r['overlap_'+variant] for r in pairs if r['overlap_'+variant] is not None)) for variant in ['old','revised']},
        'comparisons':comparisons,'families':families,'cases':cases,'pairs':sorted(pairs,key=lambda r:(r['case_id'],r['trial'])),
        'trials':sorted(rows,key=lambda r:r['id']),
        'usage':{k:live[k] for k in ['http_requests','inference_requests','input_tokens','output_tokens','actual_cost_usd','peak_worst_case_committed_usd','outstanding_reservation_usd','retries']}}


if __name__=='__main__':print(json.dumps(analyze(),indent=2))
