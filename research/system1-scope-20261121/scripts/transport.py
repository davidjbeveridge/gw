#!/usr/bin/env python3
"""Explicit serial validation with settled-cost plus in-flight reservations."""
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

P=Path(__file__).resolve().parents[1]
ORIGINAL=P.parent/'system1-20261119'
spec=importlib.util.spec_from_file_location('original_dispatch',ORIGINAL/'scripts/live.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
CAP=Decimal('0.50')
PER_REQUEST=Decimal('0.0111')


class Runner:
    def __init__(self,path,request_cap):
        self.path=path
        self.key=os.environ['OPENROUTER_API_KEY']
        self.data={'schema':1,'status':'preflight','request_cap':request_cap,'spend_cap_usd':str(CAP),
                   'input_token_cap':None,'http_requests':0,'inference_requests':0,
                   'actual_cost_usd':'0','outstanding_reservation_usd':'0',
                   'worst_case_committed_usd':'0','peak_worst_case_committed_usd':'0',
                   'input_tokens':0,'output_tokens':0,'retries':0,'requests':[]}
        with path.open('x') as f:json.dump(self.data,f,indent=2)

    def save(self):
        # Only one serial request may be in flight; an interrupted request is never retried.
        self.data['worst_case_committed_usd']=str(Decimal(self.data['actual_cost_usd'])+Decimal(self.data['outstanding_reservation_usd']))
        self.path.write_text(json.dumps(self.data,indent=2)+'\n')

    def reserve(self,paid):
        if self.data['http_requests']>=self.data['request_cap']:raise RuntimeError('request_cap')
        if Decimal(self.data['outstanding_reservation_usd'])!=0:raise RuntimeError('unsettled_request')
        worst=Decimal(self.data['actual_cost_usd'])+(PER_REQUEST if paid else Decimal('0'))
        if worst>CAP:raise RuntimeError('spend_cap')
        self.data['http_requests']+=1
        if paid:
            self.data['inference_requests']+=1
            self.data['outstanding_reservation_usd']=str(PER_REQUEST)
        self.data['peak_worst_case_committed_usd']=str(max(Decimal(self.data['peak_worst_case_committed_usd']),worst))

    def request(self,route,body=None,case_id=None,auth=True):
        paid=body is not None
        self.reserve(paid)
        row={'sequence':self.data['http_requests'],'kind':'inference' if paid else 'metadata',
             'case_id':case_id,'status':'dispatched_outcome_unknown',
             'actual_cost_before_usd':self.data['actual_cost_usd'],
             'pre_dispatch_reservation_usd':str(PER_REQUEST if paid else 0)}
        if paid:
            row['payload']=body
            row['payload_sha256']=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
        self.data['requests'].append(row);self.save()
        headers={'Content-Type':'application/json','User-Agent':'gw-synthetic-validation/1'}
        if auth:headers['Authorization']='Bearer '+self.key
        req=urllib.request.Request('https://openrouter.ai'+route,data=json.dumps(body).encode() if paid else None,headers=headers)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        began=time.perf_counter_ns()
        try:
            with urllib.request.build_opener(NoRedirect).open(req,timeout=60) as response:
                result=json.loads(response.read())
        except urllib.error.HTTPError as e:
            row.update(status='http_error',http_status=e.code);self.save()
            raise RuntimeError('http_error_'+str(e.code)) from None
        except Exception:
            self.save();raise RuntimeError('unknown_outcome') from None
        row.update(status='received',elapsed_ns=time.perf_counter_ns()-began)
        if paid:
            # Store only the same synthetic typed-response fields as earlier studies.
            usage=result['usage']
            row['response']={'model':result.get('model'),'provider':result.get('provider'),
                             'answers':result.get('answers'),
                             'usage':{k:usage.get(k) for k in ('input_tokens','output_tokens','cost')}}
            self.save()
            cost=Decimal(str(usage['cost']))
            assert cost.is_finite() and Decimal('0')<=cost<=PER_REQUEST
            assert usage.get('is_byok',False) is False
            assert type(usage['input_tokens']) is int and 0<=usage['input_tokens']<=262144
            assert type(usage['output_tokens']) is int and 0<=usage['output_tokens']<=235929
            assert cost==Decimal(usage['input_tokens'])*Decimal('0.000000042')
            self.data['actual_cost_usd']=str(Decimal(self.data['actual_cost_usd'])+cost)
            self.data['outstanding_reservation_usd']='0'
            self.data['input_tokens']+=usage['input_tokens'];self.data['output_tokens']+=usage['output_tokens']
            self.save()
            assert result['model']==original.SERVED and result['provider']=='TypeSafe'
            assert set(result['answers'])==set(body['questions'])
            for name,question in body['questions'].items():
                answer=result['answers'][name]
                assert answer['type']=='choice' and answer['choice'] in question['criteria']
        self.save();return result
