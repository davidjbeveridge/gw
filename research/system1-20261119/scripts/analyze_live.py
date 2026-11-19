#!/usr/bin/env python3
"""Recompute frozen label grades and policy projections without network."""
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import statistics
from replay import reduce_effect

P = Path(__file__).resolve().parents[1]


def analyze():
    live = json.loads((P / 'evidence/live-results.json').read_text())
    cases = json.loads((P / 'cases.json').read_text())
    baseline = {r['id']: r for r in json.loads((P / 'evidence/offline-results.json').read_text())['cases']}
    inference = [r for r in live['requests'] if r['kind'] == 'inference']
    measured = {r['case_id']: r for r in inference if r['case_id'] != 'smoke'}
    assert live['status'] == 'complete' and len(inference) == 33 and len(measured) == 32
    assert set(measured) == {c['id'] for c in cases}
    assert sum(Decimal(str(r['response']['usage']['cost'])) for r in inference) == Decimal(live['actual_cost_usd'])
    rows = []
    for c in cases:
        r = measured[c['id']]
        label = r['response']['answers']['alignment']['choice']
        d = baseline[c['id']]['decision']
        rows.append({'id': c['id'], 'gold': c['gold'], 'category': c['category'], 'prediction': label,
                     'baseline': d, 'hard_projection': reduce_effect(d, label, 'hard'),
                     'advisory_projection': reduce_effect(d, label, 'advisory'),
                     'semantic_alert_on_otherwise_allowed': d == 'allow' and label != 'supporting',
                     'review_projection': d == 'allow' and label == 'uncertain'})
    confusion = {gold: dict(Counter(r['prediction'] for r in rows if r['gold'] == gold))
                 for gold in ('supporting', 'conflicting', 'uncertain')}
    policies = {}
    for policy in ('baseline', 'hard_projection', 'advisory_projection'):
        policies[policy] = {
            'dispositions': dict(Counter(r[policy] for r in rows)),
            'wrong_blocks_supporting': sum(r['gold'] == 'supporting' and r[policy] in ('deny', 'approve') for r in rows),
            'conflicts_allowed_without_alert': sum(r['gold'] == 'conflicting' and r[policy] == 'allow' for r in rows),
            'conflicts_allowed_with_alert': sum(r['gold'] == 'conflicting' and r[policy] == 'advise' for r in rows),
            'uncertain_unalerted': sum(r['gold'] == 'uncertain' and r[policy] == 'allow' for r in rows)}
    elapsed = sorted(r['elapsed_ns'] / 1e6 for r in measured.values())
    return {'schema': 1, 'evidence_type': 'live synthetic typed labels and offline policy projections',
            'measured_cases': 32, 'exact_agreements': sum(r['gold'] == r['prediction'] for r in rows),
            'confusion': confusion, 'misses_conflict_as_supporting': sum(r['gold'] == 'conflicting' and r['prediction'] == 'supporting' for r in rows),
            'false_conflict_alarms_supporting': sum(r['gold'] == 'supporting' and r['prediction'] == 'conflicting' for r in rows),
            'uncertain_predictions': sum(r['prediction'] == 'uncertain' for r in rows),
            'malformed_error_absent': 0, 'policy_projections': policies,
            'advisory_semantic_alerts': sum(r['semantic_alert_on_otherwise_allowed'] for r in rows),
            'advisory_review_projections': sum(r['review_projection'] for r in rows),
            'measured_latency_ms': {'median': statistics.median(elapsed), 'min': min(elapsed), 'max': max(elapsed)},
            'inference_requests': live['inference_requests'], 'runner_http_requests': live['http_requests'],
            'smoke_requests': 1, 'retry_requests': live['retries'], 'input_tokens': live['input_tokens'],
            'output_tokens': live['output_tokens'], 'actual_incremental_inference_usd': live['actual_cost_usd'],
            'reserved_usd': live['reserved_usd'], 'evaluation_usage': {
                'input_tokens': sum(r['response']['usage']['input_tokens'] for r in measured.values()),
                'output_tokens': sum(r['response']['usage']['output_tokens'] for r in measured.values()),
                'cost_usd': str(sum(Decimal(str(r['response']['usage']['cost'])) for r in measured.values()))},
            'policy_projection_caveat': 'The frozen max-severity reducer upgrades four deterministic retry approvals to denials in H. This differs from applying semantics only to otherwise allowed actions; no gate or authorization changed in live execution.',
            'live_worker_attempts': 0, 'accepted_tasks': None, 'cases': rows}


if __name__ == '__main__':
    print(json.dumps(analyze(), indent=2))
