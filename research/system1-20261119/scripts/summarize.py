#!/usr/bin/env python3
"""Recompute selected historical aggregates; never calls a provider."""
import json
from pathlib import Path
S=Path(__file__).resolve().parents[1]
d=json.loads((S/'evidence/historical-screenings.json').read_text())
for cohort in ('screening','extension'):
    arms={}
    for r in d[cohort]:
        a=arms.setdefault(r['arm'],{'n':0,'verified':0,'seconds':0})
        a['n']+=r['n'];a['verified']+=r['success'];a['seconds']+=r['total_seconds']
    print(json.dumps({'cohort':cohort,'arms':arms},sort_keys=True))
p=json.loads((S/'evidence/public-cohorts.json').read_text())
print(json.dumps({'public_cohort_keys':list(p),'boundary':'Related aggregate cohort replay only; no classifier or worker dispatch'}))
print(json.dumps(d['blocked_patch_audit'],sort_keys=True))
