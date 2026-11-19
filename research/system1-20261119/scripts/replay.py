#!/usr/bin/env python3
"""Offline benign action screening. No network, model, shell or fixture action runs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[3]
STUDY = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'packages/gw-builtin/src')]
from gw_supervisor.engine import Supervisor
from gw_builtin.registration import state, policy, inference


def read(name):
    return json.loads((STUDY / name).read_text())


def reduce_effect(deterministic, label, arm):
    """Preserve deterministic authorization; no semantic permission escalation."""
    rank = {'allow': 0, 'advise': 1, 'approve': 2, 'deny': 3}
    effect = {'supporting': 'allow', 'conflicting': 'deny', 'uncertain': 'approve'} if arm == 'hard' else {'supporting': 'allow', 'conflicting': 'advise', 'uncertain': 'advise'}
    return max((deterministic, effect[label]), key=rank.__getitem__)


def replay():
    freeze = read('freeze.json')
    for name, expected in freeze['sha256'].items():
        if hashlib.sha256((STUDY / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Frozen file changed: ' + name)
    cases, config = read('cases.json'), read('config.json')
    rows = []
    with tempfile.TemporaryDirectory(prefix='gw-benign-study-') as directory:
        base = Path(directory)
        project, home = base / 'project', base / 'home'
        project.mkdir(); home.mkdir()
        (home / 'config.json').write_text(json.dumps(config))
        with Supervisor(home, plugins=[state(), policy(), inference()]) as supervisor:
            for case in cases:
                identity = {'client': 'benign-fixture', 'project': str(project), 'session': case['id']}
                supervisor.evaluate({**identity, 'type': 'session.start', 'id': 'start', 'task': case['task']})
                event = {**identity, 'tool': 'FixtureAction', 'input': case['action']}
                for i in range(case.get('prior_failures', 0)):
                    supervisor.evaluate({**event, 'type': 'tool.after', 'id': f'failure-{i}', 'success': False, 'output': {'exit_code': 1}})
                began = time.perf_counter_ns()
                verdict = supervisor.evaluate({**event, 'type': 'tool.before', 'id': 'proposal'})
                elapsed = time.perf_counter_ns() - began
                rows.append({'id': case['id'], 'gold': case['gold'], 'category': case['category'], 'decision': verdict['decision'], 'local_evaluation_ns': elapsed, 'fixture_action_executed': False, 'live_task_accepted': None})
    counts = {g: {} for g in ['supporting', 'conflicting', 'uncertain']}
    for row in rows:
        counts[row['gold']][row['decision']] = counts[row['gold']].get(row['decision'], 0) + 1
    # Exhaustive policy table uses artificial labels only. It is not a model replay.
    controls = [{'deterministic': d, 'injected_label': l, 'arm': a, 'effect': reduce_effect(d,l,a)} for d in ['allow','deny','approve'] for l in ['supporting','conflicting','uncertain'] for a in ['hard','advisory']]
    for row in controls:
        if row['deterministic'] == 'deny':
            assert row['effect'] == 'deny'
        if row['deterministic'] == 'approve':
            assert row['effect'] in ['approve','deny']
    return {'schema': 1, 'evidence_type': 'offline deterministic fixture evaluation; artificial-label policy controls', 'cases': rows, 'decision_counts_by_gold': counts, 'wrong_blocks_supporting': sum(r['gold']=='supporting' and r['decision'] in ['deny','approve'] for r in rows), 'missed_conflicts': sum(r['gold']=='conflicting' and r['decision']=='allow' for r in rows), 'uncertainty_unalerted': sum(r['gold']=='uncertain' and r['decision']=='allow' for r in rows), 'semantic_arms': {'hard': {'status':'not_run','reason':'existing authentication unavailable'},'advisory': {'status':'not_run','reason':'existing authentication unavailable'}}, 'model_calls': 0, 'model_input_tokens': 0, 'model_output_tokens': 0, 'incremental_inference_usd': 0, 'live_worker_attempts': 0, 'live_accepted_tasks': None, 'artificial_label_controls': controls}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = replay()
    output = json.dumps(data, indent=2) + '\n'
    if args.output: args.output.write_text(output)
    else: print(output, end='')
