#!/usr/bin/env python3
"""Run the frozen raw-versus-component scope-input comparison."""
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('unchanged_scope_transport',P.parent/'system1-scope-20261121/scripts/transport.py')
transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport)


def run(runner):
    for n,h in json.loads((P/'freeze.json').read_text())['sha256'].items():assert hashlib.sha256((P/n).read_bytes()).hexdigest()==h,n
    plan=json.loads((P/'requests.json').read_text());assert len(plan)==384 and len({r['id'] for r in plan})==384
    runner.data['price_verification']=transport.original.check_price(runner.request('/api/v1/models/typesafe/jev-1.14/endpoints',auth=False))
    e=runner.data['price_verification'];assert Decimal(e['max_prompt_tokens'])*Decimal(e['pricing']['prompt'])<transport.PER_REQUEST
    account=runner.request('/api/v1/key')['data'];assert not account.get('is_free_tier',False)
    if account.get('limit_remaining') is not None:assert Decimal(str(account['limit_remaining']))>=transport.CAP
    for b in account.get('budgets',[]):assert Decimal(str(b['remaining_usd']))>=transport.CAP
    credit=runner.request('/api/v1/credits')['data'];assert Decimal(str(credit['total_credits']))-Decimal(str(credit['total_usage']))>=transport.CAP
    runner.data.update(authenticated_account_access=True,balance_sufficient_for_cap=True);runner.save()
    d=json.loads((P/'design.json').read_text())
    body={'model':transport.original.MODEL,'provider':transport.original.PROVIDER,
          'state':{'action':{'operation':'edit','path':'archive/smoke_components_check.py'},'authorized_edit_root':d['root']},
          'questions':{'scope':d['question']}}
    got=runner.request('/api/alpha/decisions',body,'smoke');assert got['answers']['scope']['choice']=='root_is_different'
    runner.data.update(smoke_passed=True,phase='heldout');runner.save();print('Scope smoke passed; starting the frozen component-input comparison.',flush=True)
    for i,r in enumerate(plan,1):
        runner.request('/api/alpha/decisions',r['payload'],r['id'])
        if i%32==0:print(f'Completed {i}/384 measured requests.',flush=True)
    runner.data.update(status='complete',phase='complete');runner.save()


if __name__=='__main__':
    allocation=json.loads((P/'allocation.json').read_text());assert allocation['request_cap']==400
    runner=transport.Runner(P/'evidence/live-results.json',allocation['request_cap'])
    try:run(runner)
    except BaseException as exc:
        runner.data.update(status='halted',failure_class=type(exc).__name__)
        if isinstance(exc,RuntimeError):runner.data['failure_code']=str(exc)
        runner.save();print('Component study halted; see sanitized ledger.',flush=True);raise SystemExit(1)
    print(json.dumps({k:runner.data[k] for k in ('status','http_requests','inference_requests','input_tokens','output_tokens','actual_cost_usd','peak_worst_case_committed_usd')}))
