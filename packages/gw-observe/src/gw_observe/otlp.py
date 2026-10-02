"""OTLP/HTTP JSON export with OTel GenAI conventions. Explicit, no auto-upload.

Export is metadata-only. Providers such as MLflow/Phoenix can consume traces;
GW-specific decision details use the gw.* namespace. No content/KV duplication.
"""
import json
import os
import urllib.parse
import urllib.request
from .contract import canonical,digest


def value(v):
    if isinstance(v,bool):return {'boolValue':v}
    if isinstance(v,int):return {'intValue':str(v)}
    if isinstance(v,float):return {'doubleValue':v}
    if isinstance(v,(dict,list)):return {'stringValue':canonical(v)}
    return {'stringValue':str(v)}


def export(repo,run_ids):
    spans=[]
    usage_keys={'input_tokens':'input_tokens','output_tokens':'output_tokens','cache_read_input_tokens':'cache_read.input_tokens',
                'cache_write_input_tokens':'cache_creation.input_tokens','reasoning_output_tokens':'reasoning.output_tokens'}
    for rid in run_ids:
        run=repo.run(rid);trace=digest(['gw',rid])[:32];root=digest(['run',rid])[:16]
        def records():
            offset=0
            while offset is not None:
                page=repo.timeline(rid,offset=offset,limit=500)
                yield from page['events'];offset=page['next_offset']
        rows=records()
        end=run['finished_ns'] or run['started_ns'];start=run['started_ns']
        for e in rows:
            a=e['attributes'];end=max(end,e['end_ns']);start=min(start,e['start_ns'])
            attrs={'gw.run.id':rid,'gw.observation.id':e['id'],'gw.kind':e['kind']}
            for key in ('decision','tool_class','tool_class_basis','usage_source','status','cache_hit','cache_stored','enforcement','goal_index','alignment_observation','policy_hash','mode','task_type','skill_id','agent_id'):
                if key in a and a[key] is not None:attrs['gw.'+key]=a[key]
            if a.get('model'):attrs['gen_ai.response.model']=a['model']
            if a.get('tool'):attrs['gen_ai.tool.name']=a['tool']
            if a.get('request_id'):attrs['gen_ai.response.id']=a['request_id']
            for key,suffix in usage_keys.items():
                if key in a.get('usage',{}):attrs['gen_ai.usage.'+suffix]=a['usage'][key]
            if 'cost_usd' in a.get('usage',{}):attrs['gw.cost.usd']=a['usage']['cost_usd']
            attrs['gen_ai.operation.name']='execute_tool' if a.get('tool') else 'chat' if e['kind'].startswith('model.') else e['kind']
            if e['source']:attrs['gw.source.reference']=digest(e['source'])
            spans.append({'traceId':trace,'spanId':digest(e['id'])[:16],
                'parentSpanId':digest(e['parent_id'])[:16] if e['parent_id'] else root,
                'name':e['kind'],'kind':1,'startTimeUnixNano':str(e['start_ns']),'endTimeUnixNano':str(e['end_ns']),
                'attributes':[{'key':k,'value':value(v)} for k,v in attrs.items()],
                'status':{'code':2 if a.get('status') in {'error','failed'} else 0}})
        attrs={'gw.run.id':rid,'gw.outcome':run['outcome'],'gw.harness':run['manifest']['harness'],'gw.mode':run['manifest']['mode']}
        spans.append({'traceId':trace,'spanId':root,'name':run['name'],'kind':1,'startTimeUnixNano':str(start),
                      'endTimeUnixNano':str(end),'attributes':[{'key':k,'value':value(v)} for k,v in attrs.items()],'status':{'code':0}})
    return {'resourceSpans':[{'resource':{'attributes':[{'key':'service.name','value':{'stringValue':'gw'}},
                {'key':'telemetry.sdk.language','value':{'stringValue':'python'}}]},
                'scopeSpans':[{'scope':{'name':'gw-observe','version':'0.1.0'},'spans':spans}]}]}


def send(payload,endpoint,*,key_env=None,headers_env=None,timeout=5):
    u=urllib.parse.urlsplit(endpoint)
    if not u.hostname or u.username or u.password or u.query or u.fragment or (u.scheme!='https' and not(u.scheme=='http' and u.hostname in {'127.0.0.1','localhost','::1'})):
        raise ValueError('Use an explicit HTTPS/loopback OTLP endpoint without embedded secrets')
    headers={'Content-Type':'application/json'}
    if key_env:
        token=os.environ.get(key_env)
        if not token:raise ValueError('Missing OTLP credential')
        headers['Authorization']='Bearer '+token
    if headers_env:
        extra=json.loads(os.environ.get(headers_env,'{}'))
        if not isinstance(extra,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in extra.items()):raise ValueError('Headers must be a string map')
        headers.update(extra)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):raise ValueError('OTLP redirects are refused')
    request=urllib.request.Request(endpoint,canonical(payload).encode(),headers)
    with urllib.request.build_opener(NoRedirect).open(request,timeout=timeout) as response:
        raw=response.read(1048577)
    if len(raw)>1048576:raise ValueError('OTLP response exceeded budget')
    result=json.loads(raw or b'{}')
    partial=result.get('partialSuccess',{})
    if int(partial.get('rejectedSpans',0)):raise ValueError('Collector reported rejected spans; export was not fully accepted')
    return {'accepted':True,'automatic_upload':False}
