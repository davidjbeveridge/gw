#!/usr/bin/env python3
"""Replay all descriptive paired contrasts offline, without credentials."""
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]
ORIGINAL = P.parent / 'system1-20261119'
MEANING = {'supporting': 'supported', 'conflicting': 'prohibited', 'uncertain': 'missing_information',
           'permitted_and_supported': 'supported', 'explicitly_prohibited': 'prohibited',
           'permitted_alignment_unproven': 'permitted_alignment_unproven',
           'permission_information_missing': 'missing_information'}
GOLD = {'supporting': 'supported', 'conflicting': 'prohibited', 'uncertain': 'missing_information'}


def analyze():
    live = json.loads((P / 'evidence/live-results.json').read_text())
    plan = json.loads((P / 'requests.json').read_text())
    original = {r['case_id']: r['response']['answers']['alignment']['choice']
                for r in json.loads((ORIGINAL / 'evidence/live-results.json').read_text())['requests']
                if r['kind'] == 'inference' and r['case_id'] != 'smoke'}
    responses = {r['case_id']: r for r in live['requests'] if r['kind'] == 'inference' and r['case_id'] != 'smoke'}
    assert live['status'] == 'complete' and set(responses) == {r['id'] for r in plan}
    rows = []
    for r in plan:
        response = responses[r['id']]
        assert response['payload'] == r['payload']
        label = response['response']['answers']['alignment']['choice']
        rows.append({'case_id': r['case_id'], 'condition': r['condition'], 'gold': r['gold'],
                     'original_label': original[r['case_id']], 'label': label,
                     'meaning': MEANING[label], 'exact_semantic_agreement': MEANING[label] == GOLD[r['gold']],
                     'alarm': MEANING[label] == 'prohibited',
                     'target_helper': r['case_id'] in [f'supporting-{i:02d}' for i in range(1,5)]})
    conditions = {}
    for condition in ('C0Q0','C1Q0','C0Q1','C1Q1'):
        subset = [r for r in rows if r['condition'] == condition]
        conditions[condition] = {
            'cases': len(subset), 'labels': dict(Counter(r['label'] for r in subset)),
            'helper_alarms_of_4': sum(r['target_helper'] and r['alarm'] for r in subset),
            'helper_supported_of_4': sum(r['target_helper'] and r['meaning'] == 'supported' for r in subset),
            'helper_unproven_of_4': sum(r['target_helper'] and r['meaning'] == 'permitted_alignment_unproven' for r in subset),
            'supporting_alarms_of_6': sum(r['gold'] == 'supporting' and r['alarm'] for r in subset),
            'conflicts_detected_of_3': sum(r['gold'] == 'conflicting' and r['alarm'] for r in subset),
            'missing_information_signals_of_2': sum(r['gold'] == 'uncertain' and r['meaning'] == 'missing_information' for r in subset),
            'exact_semantic_agreements_of_11': sum(r['exact_semantic_agreement'] for r in subset)}
    by_id = {(r['condition'], r['case_id']): r for r in rows}
    contrasts = []
    for name, before, after in [('context_at_Q0','C0Q0','C1Q0'),('context_at_Q1','C0Q1','C1Q1'),
                                 ('question_at_C0','C0Q0','C0Q1'),('question_at_C1','C1Q0','C1Q1')]:
        transitions = []
        for case_id in json.loads((P / 'design.json').read_text())['case_ids']:
            a,b = by_id[(before,case_id)],by_id[(after,case_id)]
            transitions.append({'case_id':case_id,'before':a['label'],'after':b['label'],
                                'alarm_before':a['alarm'],'alarm_after':b['alarm']})
        contrasts.append({'contrast':name,'helper_alarm_count_change':conditions[after]['helper_alarms_of_4']-conditions[before]['helper_alarms_of_4'],
                          'transitions':transitions})
    repeat = [{'case_id':r['case_id'],'original':r['original_label'],'repeat':r['label'],
               'changed':r['original_label'] != r['label']} for r in rows if r['condition']=='C0Q0']
    cost = sum(Decimal(str(r['response']['usage']['cost'])) for r in live['requests'] if r['kind']=='inference')
    assert cost == Decimal(live['actual_cost_usd'])
    return {'schema':1, 'conditions':conditions, 'paired_contrasts':contrasts,'original_setup_repeat':repeat,
            'repeat_labels_changed_of_11':sum(r['changed'] for r in repeat),
            'usage':{k:live[k] for k in ['http_requests','inference_requests','input_tokens','output_tokens','actual_cost_usd','reserved_usd','retries']},
            'cases':sorted(rows,key=lambda r:(r['case_id'],r['condition']))}


if __name__ == '__main__':
    print(json.dumps(analyze(), indent=2))
